from dataclasses import dataclass
from typing import Any

from django.db import transaction

from apps.imports.models import (
    ImportBatch,
    ImportBatchStatus,
    ImportSourceSystem,
    ImportSourceUpload,
)

from .batch_review import (
    MUTABLE_BATCH_STATUSES,
    _validate_user,
)
from .derived_batch_review import (
    _persist_derived_import_review,
)
from .raw_chargement_cleaning_enrichment import (
    enrich_raw_chargement_cleaning_result,
)
from .raw_chargement_brand_partition import (
    partition_raw_chargement_rows_by_brand,
)
from .raw_chargement_file import (
    AdaptedChargementRow,
    RawChargementFileResult,
    adapt_raw_chargement_file,
    to_report_row_read_result,
)
from .raw_chargement_review import (
    RawChargementImportReviewError,
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
from .value_normalizers import (
    ValueNormalizationError,
    is_blank_value,
    parse_datetime_value,
    parse_decimal_value,
)

def _validate_raw_chargement_period(
    rows: tuple[AdaptedChargementRow, ...],
    *,
    period_start: Any,
    period_end: Any,
) -> None:
    for row in rows:
        if "Date&Heure" not in row.values:
            continue

        raw_datetime = row.values[
            "Date&Heure"
        ]

        if is_blank_value(raw_datetime):
            quantity_raw = row.values.get(
                "Qt\u00e9"
            )
            article_is_blank = is_blank_value(
                row.values.get("Article")
            )

            try:
                quantity = parse_decimal_value(
                    quantity_raw
                )
            except ValueNormalizationError:
                quantity = None
                quantity_is_invalid = True
            else:
                quantity_is_invalid = False

            is_stopped_candidate = (
                article_is_blank
                and not quantity_is_invalid
                and (
                    is_blank_value(quantity_raw)
                    or quantity == 0
                )
            )

            if is_stopped_candidate:
                continue

            raise RawChargementImportReviewError(
                "missing_datetime",
                (
                    "The raw Chargement Date&Heure "
                    "value is required for an active row."
                ),
                details={
                    "excel_row_number": (
                        row.excel_row_number
                    ),
                },
            )

        try:
            parsed_datetime = parse_datetime_value(
                raw_datetime
            )
        except ValueNormalizationError as exc:
            raise RawChargementImportReviewError(
                "invalid_datetime",
                (
                    "The raw Chargement Date&Heure "
                    "value is invalid."
                ),
                details={
                    "excel_row_number": (
                        row.excel_row_number
                    ),
                    "raw_value": str(
                        raw_datetime
                    ),
                },
            ) from exc

        if parsed_datetime is None:
            raise RawChargementImportReviewError(
                "invalid_datetime",
                (
                    "The raw Chargement Date&Heure "
                    "value is invalid."
                ),
                details={
                    "excel_row_number": (
                        row.excel_row_number
                    ),
                    "raw_value": str(
                        raw_datetime
                    ),
                },
            )

        row_date = parsed_datetime.date()

        if (
            row_date < period_start
            or row_date > period_end
        ):
            raise RawChargementImportReviewError(
                "date_outside_period",
                (
                    "The raw Chargement row date is "
                    "outside the declared period."
                ),
                details={
                    "excel_row_number": (
                        row.excel_row_number
                    ),
                    "row_date": (
                        row_date.isoformat()
                    ),
                    "period_start": (
                        period_start.isoformat()
                    ),
                    "period_end": (
                        period_end.isoformat()
                    ),
                },
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

    source_system = (
        ImportSourceSystem.objects.get(
            code__iexact=source_system_code,
            is_active=True,
        )
    )

    adapted = adapt_raw_chargement_file(
        source,
        truck_mapping=truck_mapping,
        original_filename=original_filename,
    )

    _validate_raw_chargement_period(
        adapted.rows,
        period_start=normalized_period_start,
        period_end=normalized_period_end,
    )

    rows_by_brand = (
        partition_raw_chargement_rows_by_brand(
            adapted.rows
        )
    )

    source_upload_result = None
    batches: list[ImportBatch] = []

    try:
        with transaction.atomic():
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

                cleaning_result = (
                    enrich_raw_chargement_cleaning_result(
                        cleaning_result,
                        source_system=source_system,
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

                scoped_batches = (
                    ImportBatch.objects
                    .filter(
                        source_upload=source_upload,
                        brand__code__iexact=brand_code,
                        report_type="CHARGEMENT",
                        period_start=normalized_period_start,
                        period_end=normalized_period_end,
                    )
                )

                existing_batch = (
                    scoped_batches
                    .filter(
                        status__in=MUTABLE_BATCH_STATUSES,
                    )
                    .first()
                )

                replacement_target = None

                if existing_batch is None:
                    existing_batch = (
                        scoped_batches.first()
                    )

                    if (
                        existing_batch is not None
                        and existing_batch.status
                        == ImportBatchStatus.APPROVED
                        and existing_batch.content_sha256
                        != prepared_rows.content_sha256
                    ):
                        replacement_target = (
                            existing_batch
                        )
                        existing_batch = None

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

                if replacement_target is not None:
                    replacement_batch = (
                        review_result.batch
                    )
                    replacement_batch.replaces_batch = (
                        replacement_target
                    )
                    replacement_batch.full_clean()
                    replacement_batch.save(
                        update_fields=[
                            "replaces_batch",
                            "updated_at",
                        ]
                    )

                batches.append(
                    review_result.batch
                )

    except Exception:
        if (
            source_upload_result is not None
            and source_upload_result.created
        ):
            source_upload = (
                source_upload_result.source_upload
            )
            saved_file_name = (
                source_upload.source_file.name
            )

            if saved_file_name:
                try:
                    source_upload.source_file.storage.delete(
                        saved_file_name
                    )
                except Exception:
                    pass

        raise

    return RawChargementDerivedReviewResult(
        source_upload=source_upload,
        batches=tuple(batches),
    )
