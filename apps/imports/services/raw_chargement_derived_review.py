from dataclasses import dataclass
from typing import Any

from django.db import transaction

from apps.imports.models import (
    ImportBatch,
    ImportSourceUpload,
)

from .batch_review import _validate_user
from .derived_batch_review import (
    _persist_derived_import_review,
)
from .raw_chargement_brand_partition import (
    partition_raw_chargement_rows_by_brand,
)
from .raw_chargement_file import (
    RawChargementFileResult,
    adapt_raw_chargement_file,
    to_report_row_read_result,
)
from .raw_chargement_review import (
    _coerce_period_date,
)
from .report_row_cleaner import (
    clean_report_rows_from_metadata,
)
from .review_summary import (
    build_import_review_summary_from_metadata,
)
from .row_staging import prepare_import_rows
from .source_truck_mapping_store import (
    build_source_truck_mapping,
)
from .source_upload_store import (
    create_import_source_upload,
)


@dataclass(frozen=True, slots=True)
class RawChargementDerivedReviewResult:
    source_upload: ImportSourceUpload
    batches: tuple[ImportBatch, ...]


def create_raw_chargement_derived_import_reviews(
    source: Any,
    *,
    source_system_code: str,
    uploaded_by: Any,
    period_start: Any,
    period_end: Any,
    reviewed_by: Any | None = None,
    original_filename: str | None = None,
) -> RawChargementDerivedReviewResult:
    _validate_user(
        uploaded_by,
        "uploaded_by",
    )

    reviewer = reviewed_by or uploaded_by

    _validate_user(
        reviewer,
        "reviewed_by",
    )

    normalized_period_start = _coerce_period_date(
        period_start,
        field_name="period_start",
    )
    normalized_period_end = _coerce_period_date(
        period_end,
        field_name="period_end",
    )

    if normalized_period_end < normalized_period_start:
        from .raw_chargement_review import (
            RawChargementImportReviewError,
        )

        raise RawChargementImportReviewError(
            "invalid_period_range",
            (
                "period_end cannot be before "
                "period_start."
            ),
        )

    truck_mapping = build_source_truck_mapping(
        source_system_code
    )

    adapted = adapt_raw_chargement_file(
        source,
        truck_mapping=truck_mapping,
        original_filename=original_filename,
    )

    rows_by_brand = (
        partition_raw_chargement_rows_by_brand(
            adapted.rows
        )
    )

    source_upload_result = (
        create_import_source_upload(
            source,
            source_system_code=source_system_code,
            uploaded_by=uploaded_by,
            worksheet_name=adapted.worksheet_name,
            original_filename=adapted.filename,
        )
    )

    source_upload = (
        source_upload_result.source_upload
    )

    batches: list[ImportBatch] = []

    with transaction.atomic():
        for brand_code in sorted(rows_by_brand):
            brand_rows = rows_by_brand[
                brand_code
            ]

            brand_file_result = RawChargementFileResult(
                filename=adapted.filename,
                worksheet_name=adapted.worksheet_name,
                rows=brand_rows,
            )

            row_result = to_report_row_read_result(
                brand_file_result
            )

            cleaning_result = (
                clean_report_rows_from_metadata(
                    row_result
                )
            )

            summary = (
                build_import_review_summary_from_metadata(
                    brand_code=brand_code,
                    period_start=normalized_period_start,
                    period_end=normalized_period_end,
                    row_result=row_result,
                    cleaning_result=cleaning_result,
                )
            )

            prepared_rows = prepare_import_rows(
                cleaning_result
            )

            existing_batch = (
                ImportBatch.objects
                .filter(
                    source_upload=source_upload,
                    brand__code__iexact=brand_code,
                    report_type="CHARGEMENT",
                    period_start=normalized_period_start,
                    period_end=normalized_period_end,
                )
                .first()
            )

            review_result = (
                _persist_derived_import_review(
                    source_upload=source_upload,
                    uploaded_by=uploaded_by,
                    reviewer=reviewer,
                    batch=existing_batch,
                    brand_code=brand_code,
                    report_type="CHARGEMENT",
                    period_start=normalized_period_start,
                    period_end=normalized_period_end,
                    worksheet_name=adapted.worksheet_name,
                    summary=summary,
                    prepared_rows=prepared_rows,
                )
            )

            batches.append(
                review_result.batch
            )

    return RawChargementDerivedReviewResult(
        source_upload=source_upload,
        batches=tuple(batches),
    )
