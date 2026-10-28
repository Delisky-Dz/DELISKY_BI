"""Coordinate individually validated approvals of a signed, visible ready set."""
from hashlib import sha256
import json
import logging

from django.core import signing
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import FileField

from apps.imports.models import ImportBatch, ImportBatchStatus, ImportSourceSystem
from apps.imports.presenters import approval_error_message
from .approval_dispatch import approve_reviewed_batch, _source_system_id_for_source_items
from .batch_approval import ImportBatchApprovalError

logger = logging.getLogger(__name__)
SNAPSHOT_SALT = "imports.accountant.approve-ready.v1"
SNAPSHOT_MAX_AGE = 15 * 60


def can_submit_approval(batch):
    # The individual review screen uses this same readiness predicate.
    # The domain service remains authoritative for all approval validation.
    return batch.status == ImportBatchStatus.REVIEWED and batch.error_count == 0


def approval_version(batch):
    values = {
        field.attname: str(field.value_from_object(batch)) if isinstance(field, FileField)
        else field.value_from_object(batch)
        for field in batch._meta.concrete_fields
    }
    # Preserve the full revision timestamp; DjangoJSONEncoder rounds datetimes.
    values["updated_at"] = batch.updated_at.isoformat()
    return sha256(json.dumps(values, cls=DjangoJSONEncoder, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def make_ready_snapshot(batches, user):
    entries = [{
        "id": batch.pk, "version": approval_version(batch),
        "brand": batch.brand.code, "report_type": batch.get_report_type_display(),
        "period_start": batch.period_start.isoformat(), "period_end": batch.period_end.isoformat(),
    } for batch in batches if can_submit_approval(batch)]
    return signing.dumps({"user_id": user.pk, "batches": entries}, salt=SNAPSHOT_SALT, compress=True)


def read_ready_snapshot(token, user):
    payload = signing.loads(token, salt=SNAPSHOT_SALT, max_age=SNAPSHOT_MAX_AGE)
    if not isinstance(payload, dict) or payload.get("user_id") != user.pk:
        raise signing.BadSignature("Snapshot belongs to another user.")
    entries = payload.get("batches")
    if not isinstance(entries, list) or any(
        not isinstance(entry, dict) or type(entry.get("id")) is not int
        or entry["id"] <= 0 or not isinstance(entry.get("version"), str)
        for entry in entries
    ) or len({entry["id"] for entry in entries}) != len(entries):
        raise signing.BadSignature("Invalid ready set.")
    return entries


def approve_ready_snapshot(entries, *, approved_by):
    succeeded, failures = [], []
    for entry in entries:
        try:
            with transaction.atomic():
                # Match the existing Items domain lock order: source, then batch.
                source_id = _source_system_id_for_source_items(entry["id"])
                if source_id is not None:
                    ImportSourceSystem.objects.select_for_update().get(pk=source_id)
                batch = ImportBatch.objects.select_for_update().get(pk=entry["id"])
                if not can_submit_approval(batch) or approval_version(batch) != entry["version"]:
                    raise ImportBatchApprovalError(
                        "bulk_batch_changed", "تغيرت الدفعة منذ عرض الصفحة؛ أعد مراجعتها قبل الاعتماد.",
                    )
                approve_reviewed_batch(batch.pk, approved_by=approved_by)
        except ImportBatch.DoesNotExist:
            failures.append({"id": entry["id"], "reason": "الدفعة لم تعد موجودة."})
        except ImportBatchApprovalError as exc:
            failures.append({"id": entry["id"], "reason": exc.message if exc.code == "bulk_batch_changed" else approval_error_message(exc)})
        except Exception:
            logger.exception("Bulk accountant approval failed for batch %s", entry["id"])
            failures.append({"id": entry["id"], "reason": "تعذر اعتماد الدفعة؛ راجعها وحاول مجددًا."})
        else:
            succeeded.append(entry["id"])
    return {"succeeded_ids": succeeded, "success_count": len(succeeded), "failures": failures, "failure_count": len(failures)}
