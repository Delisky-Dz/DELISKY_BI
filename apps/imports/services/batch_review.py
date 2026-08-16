from dataclasses import dataclass
from hashlib import sha256
from os import PathLike
from pathlib import Path
from typing import Any

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.imports.models import (
    DistributionBrand,
    ImportBatch,
)

from .preflight import run_import_preflight
from .report_row_cleaner import clean_report_rows
from .report_row_reader import read_report_rows
from .row_staging import (
    PreparedImportRows,
    prepare_import_rows,
    replace_import_batch_rows,
)
from .review_summary import (
    ImportReviewSummary,
    build_import_review_summary,
)


MUTABLE_BATCH_STATUSES = {
    "PENDING",
    "REVIEWED",
    "BLOCKED",
    "FAILED",
}


class ImportBatchReviewError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True, slots=True)
class ImportBatchReviewResult:
    batch: ImportBatch
    summary: ImportReviewSummary
    created: bool


def _read_source_bytes(source: Any) -> bytes:
    if isinstance(source, (str, PathLike)):
        try:
            return Path(source).read_bytes()
        except OSError as exc:
            raise ImportBatchReviewError(
                "file_read_failed",
                "The Excel file could not be read.",
            ) from exc

    if not hasattr(source, "read"):
        raise ImportBatchReviewError(
            "unreadable_source",
            "The uploaded file source is not readable.",
        )

    original_position = None

    if hasattr(source, "tell"):
        try:
            original_position = source.tell()
        except (OSError, ValueError):
            original_position = None

    try:
        if hasattr(source, "seek"):
            source.seek(0)

        data = source.read()

        if not isinstance(data, bytes):
            raise ImportBatchReviewError(
                "invalid_file_content",
                "The uploaded file did not return binary data.",
            )

        return data
    finally:
        if (
            original_position is not None
            and hasattr(source, "seek")
        ):
            try:
                source.seek(original_position)
            except (OSError, ValueError):
                pass


def _get_active_brand(
    brand_code: str,
) -> DistributionBrand:
    try:
        brand = DistributionBrand.objects.get(
            code__iexact=brand_code,
        )
    except DistributionBrand.DoesNotExist as exc:
        raise ImportBatchReviewError(
            "unknown_brand",
            (
                "The brand extracted from the filename "
                "does not exist."
            ),
            details={
                "brand_code": brand_code,
            },
        ) from exc

    if not brand.is_active:
        raise ImportBatchReviewError(
            "inactive_brand",
            (
                "The brand extracted from the filename "
                "is inactive."
            ),
            details={
                "brand_code": brand_code,
            },
        )

    return brand


def _validate_user(user: Any, field_name: str) -> None:
    if user is None or getattr(user, "pk", None) is None:
        raise ImportBatchReviewError(
            "unsaved_user",
            (
                f"The {field_name} user must be saved "
                "before reviewing an import."
            ),
        )


def _persist_import_review(
    source: Any,
    *,
    uploaded_by: Any,
    reviewer: Any,
    batch: ImportBatch | None,
    brand_code: str,
    report_type: str,
    period_start: Any,
    period_end: Any,
    worksheet_name: str,
    summary: ImportReviewSummary,
    prepared_rows: PreparedImportRows,
) -> ImportBatchReviewResult:
    brand = _get_active_brand(brand_code)
    file_bytes = _read_source_bytes(source)

    if not file_bytes:
        raise ImportBatchReviewError(
            "empty_file",
            "The Excel file is empty.",
        )

    file_hash = sha256(file_bytes).hexdigest()
    created = batch is None
    saved_file_name = ""
    old_file_name = ""

    try:
        with transaction.atomic():
            if batch is None:
                target = ImportBatch(
                    uploaded_by=uploaded_by,
                )
            else:
                if batch.pk is None:
                    raise ImportBatchReviewError(
                        "unsaved_batch",
                        (
                            "An existing batch must be "
                            "saved before it can be updated."
                        ),
                    )

                target = (
                    ImportBatch.objects
                    .select_for_update()
                    .get(pk=batch.pk)
                )

                if (
                    target.status
                    not in MUTABLE_BATCH_STATUSES
                ):
                    raise ImportBatchReviewError(
                        "immutable_batch",
                        (
                            "Approved or superseded batches "
                            "cannot be reviewed again."
                        ),
                        details={
                            "status": target.status,
                        },
                    )

                old_file_name = (
                    target.source_file.name
                    if target.source_file
                    else ""
                )

            target.brand = brand
            target.report_type = report_type
            target.period_start = period_start
            target.period_end = period_end
            target.original_filename = summary.filename
            target.worksheet_name = worksheet_name
            target.file_size_bytes = len(file_bytes)
            target.file_sha256 = file_hash
            target.content_sha256 = (
                prepared_rows.content_sha256
            )
            target.status = summary.recommended_status
            target.total_rows = summary.total_rows
            target.accepted_rows = summary.accepted_rows
            target.excluded_rows = summary.excluded_rows
            target.stopped_rows = summary.stopped_rows
            target.warning_count = summary.warning_count
            target.error_count = summary.error_count
            target.review_summary = summary.as_dict()
            target.uploaded_by = uploaded_by
            target.reviewed_by = reviewer
            target.reviewed_at = timezone.now()
            target.approved_by = None
            target.approved_at = None

            target.source_file.save(
                summary.filename,
                ContentFile(file_bytes),
                save=False,
            )

            saved_file_name = target.source_file.name

            target.full_clean()
            target.save()

            replace_import_batch_rows(
                target,
                prepared_rows,
            )

            if (
                old_file_name
                and old_file_name != saved_file_name
            ):
                storage = target.source_file.storage

                transaction.on_commit(
                    lambda: storage.delete(old_file_name)
                )

    except Exception:
        if saved_file_name:
            try:
                target.source_file.storage.delete(
                    saved_file_name
                )
            except Exception:
                pass

        raise

    return ImportBatchReviewResult(
        batch=target,
        summary=summary,
        created=created,
    )


def create_or_update_import_review(
    source: Any,
    *,
    uploaded_by: Any,
    reviewed_by: Any | None = None,
    batch: ImportBatch | None = None,
    original_filename: str | None = None,
) -> ImportBatchReviewResult:
    _validate_user(uploaded_by, "uploaded_by")

    reviewer = reviewed_by or uploaded_by
    _validate_user(reviewer, "reviewed_by")

    preflight = run_import_preflight(
        source,
        original_filename=original_filename,
    )

    if not preflight.is_valid:
        raise ImportBatchReviewError(
            "preflight_failed",
            (
                "The file cannot create an ImportBatch "
                "because its preflight contains errors."
            ),
            details={
                "errors": [
                    {
                        "stage": issue.stage,
                        "code": issue.code,
                        "message": issue.message,
                        "details": issue.details,
                    }
                    for issue in preflight.errors
                ],
            },
        )

    parsed = preflight.parsed_filename
    inspection = preflight.inspection

    if parsed is None or inspection is None:
        raise ImportBatchReviewError(
            "incomplete_preflight",
            "The preflight result is incomplete.",
        )

    row_result = read_report_rows(
        source,
        preflight,
    )

    cleaning_result = clean_report_rows(
        row_result,
        preflight,
    )

    summary = build_import_review_summary(
        preflight,
        row_result,
        cleaning_result,
    )

    prepared_rows = prepare_import_rows(
        cleaning_result
    )

    return _persist_import_review(
        source,
        uploaded_by=uploaded_by,
        reviewer=reviewer,
        batch=batch,
        brand_code=parsed.brand_code,
        report_type=parsed.report_type,
        period_start=parsed.period_start,
        period_end=parsed.period_end,
        worksheet_name=inspection.worksheets[0].name,
        summary=summary,
        prepared_rows=prepared_rows,
    )
