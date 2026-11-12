"""Coordinate the accountant's single-source raw sales review and approval."""
from collections import Counter
from hashlib import sha256
import logging
from pathlib import Path

from django.core import signing

from apps.imports.models import ImportSourceUpload

from .bulk_approval import (
    SNAPSHOT_MAX_AGE, approve_ready_snapshot, can_submit_approval,
    make_ready_snapshot, read_ready_snapshot,
)
from .excel_reader import DEFAULT_MAX_FILE_SIZE_BYTES
from .raw_sales_derived_review import create_raw_sales_derived_import_review, RawSalesDerivedReviewError
from .raw_sales_file import RawSalesFileError, source_truck_code_from_filename
from .raw_sales_review import RawSalesImportReviewError
from .source_truck_mapping_store import build_source_truck_exclusions, build_source_truck_mapping

logger = logging.getLogger(__name__)
SALT = "imports.sales.batch.v1"
LABELS = {
    "READY": "جاهز", "BLOCKED": "موقوف", "INVALID": "ملف غير صالح",
    "DUPLICATE": "مكرر", "IMPORTED": "تم الاستيراد", "FAILED": "فشل الاستيراد",
}


def review_files(files, *, source_system, period_start, period_end, user):
    mappings = build_source_truck_mapping(source_system.code)
    exclusions = build_source_truck_exclusions(source_system.code)
    ready, rows, reviewed_trucks = [], [], {}
    for upload in files:
        row = {"name": upload.name, "state": "BLOCKED"}
        rows.append(row)
        if Path(upload.name).suffix.lower() != ".xlsx" or not 0 < upload.size <= DEFAULT_MAX_FILE_SIZE_BYTES:
            row.update(state="INVALID", note="اختر ملف XLSX غير فارغ بحجم لا يتجاوز 25 MiB.")
            continue
        try:
            truck = source_truck_code_from_filename(upload.name)
            row["truck"] = truck
            if truck in exclusions:
                row["note"] = f"كود مستبعد من الاستيراد ({exclusions[truck]})"
                continue
            if truck not in mappings:
                row["note"] = "كود الشاحنة غير مربوط بالمصدر المحدد."
                continue
            digest = sha256()
            for chunk in upload.chunks():
                digest.update(chunk)
            upload.seek(0)
            if truck in reviewed_trucks:
                if reviewed_trucks[truck] == digest.digest():
                    row.update(state="DUPLICATE", note="تكرر الملف في الدفعة.")
                else:
                    row["note"] = "يوجد ملف آخر لنفس الشاحنة والفترة. افحصه بشكل مستقل."
                continue
            stored = ImportSourceUpload.objects.filter(file_sha256=digest.hexdigest()).first()
            if stored and (stored.source_system_id != source_system.pk or
                           source_truck_code_from_filename(stored.original_filename) != truck):
                row["note"] = "الملف محفوظ مسبقًا لمصدر أو شاحنة أخرى."
                continue
            review = create_raw_sales_derived_import_review(
                upload, original_filename=upload.name, source_system_code=source_system.code,
                period_start=period_start, period_end=period_end, uploaded_by=user,
            )
            batch = review.batch
            row.update(batch_id=batch.pk, brand=batch.brand.code, total=batch.total_rows,
                       accepted=batch.accepted_rows, rejected=batch.total_rows - batch.accepted_rows)
            if batch.status == "APPROVED":
                row.update(state="DUPLICATE", note="سبق اعتماد هذه البيانات.")
            elif can_submit_approval(batch):
                row.update(state="READY", note=f"تحذيرات: {batch.warning_count}" if batch.warning_count else "")
                ready.append(batch)
            else:
                row["note"] = f"أخطاء المراجعة: {batch.error_count}. راجع تفاصيل الملف."
            reviewed_trucks[truck] = digest.digest()
        except (RawSalesFileError, RawSalesDerivedReviewError, RawSalesImportReviewError) as exc:
            cause = exc.details.get("cause_code", exc.code)
            if cause == "raw_excel_read_failed":
                row["state"] = "INVALID"
            row["note"] = f"{exc.message} ({cause})"
            if exc.code == "sale_outside_period":
                row["note"] = f"التاريخ {exc.details.get('sale_date')} خارج الفترة في السطر {exc.details.get('excel_row_number')}."
        except Exception:
            logger.exception("Raw sales review failed")
            row.update(state="FAILED", note="تعذر فحص الملف. راجع سجل الأخطاء.")
    snapshot = make_ready_snapshot(ready, user)
    period = {"period_start": str(period_start), "period_end": str(period_end), "source_system": source_system.pk}
    token = signing.dumps([rows, snapshot, period], salt=SALT, compress=True) if ready else None
    return batch_summary(rows, token)


def import_ready(token, user):
    rows, snapshot, period = signing.loads(token, salt=SALT, max_age=SNAPSHOT_MAX_AGE)
    entries = read_ready_snapshot(snapshot, user)
    result = approve_ready_snapshot(entries, approved_by=user)
    failures = {item["id"]: item["reason"] for item in result["failures"]}
    for row in rows:
        if row["state"] == "READY":
            reason = failures.get(row["batch_id"])
            row.update(state="FAILED" if reason else "IMPORTED", note=reason or "")
    return {**batch_summary(rows, None), "period": period}


def batch_summary(rows, token):
    counts = Counter(row["state"] for row in rows)
    return {
        "rows": [dict(row, label=LABELS[row["state"]]) for row in rows], "token": token,
        "ready": counts["READY"], "blocked": counts["BLOCKED"] + counts["INVALID"],
        "duplicate": counts["DUPLICATE"], "imported": counts["IMPORTED"],
        "failed": counts["FAILED"], "total": sum(row.get("total", 0) for row in rows),
    }
