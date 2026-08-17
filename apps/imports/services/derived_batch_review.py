from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.imports.models import (
    ImportBatch,
    ImportSourceUpload,
)

from .batch_review import (
    MUTABLE_BATCH_STATUSES,
    ImportBatchReviewError,
    ImportBatchReviewResult,
    _get_active_brand,
)
from .review_summary import ImportReviewSummary
from .row_staging import (
    PreparedImportRows,
    replace_import_batch_rows,
)


def _persist_derived_import_review(
    *,
    source_upload: ImportSourceUpload,
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
    if source_upload.pk is None:
        raise ImportBatchReviewError(
            "unsaved_source_upload",
            (
                "The source upload must be saved before "
                "creating derived import batches."
            ),
        )

    brand = _get_active_brand(
        brand_code
    )

    created = batch is None

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
                        "An existing batch must be saved "
                        "before it can be updated."
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

        target.source_upload = source_upload
        target.brand = brand
        target.report_type = report_type
        target.period_start = period_start
        target.period_end = period_end
        target.original_filename = summary.filename
        target.worksheet_name = worksheet_name

        target.source_file = ""
        target.file_size_bytes = (
            source_upload.file_size_bytes
        )
        target.file_sha256 = ""
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

        target.full_clean()
        target.save()

        replace_import_batch_rows(
            target,
            prepared_rows,
        )

    return ImportBatchReviewResult(
        batch=target,
        summary=summary,
        created=created,
    )
