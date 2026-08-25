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
from .raw_opening_stock_cleaning_enrichment import (
    enrich_raw_opening_stock_cleaning_result,
)

from .raw_opening_stock_brand_partition import (
    partition_raw_opening_stock_rows_by_brand,
)
from .raw_opening_stock_file import (
    RawOpeningStockFileResult,
    adapt_raw_opening_stock_file,
    to_report_row_read_result,
)
from .raw_opening_stock_review import (
    _coerce_stock_date,
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
class RawOpeningStockDerivedReviewResult:
    source_upload: ImportSourceUpload
    batches: tuple[ImportBatch, ...]


def _logical_opening_stock_scope_batches(
    *,
    brand_code: str,
    stock_date: Any,
) -> tuple[ImportBatch, ...]:
    return tuple(
        ImportBatch.objects
        .select_for_update()
        .filter(
            brand__code__iexact=brand_code,
            report_type="OPENING_STOCK",
            period_start=stock_date,
            period_end=stock_date,
        )
        .order_by("-id")
    )


def create_raw_opening_stock_derived_import_reviews(
    source: Any,
    *,
    source_system_code: str,
    uploaded_by: Any,
    stock_date: Any,
    reviewed_by: Any | None = None,
    original_filename: str | None = None,
) -> RawOpeningStockDerivedReviewResult:
    _validate_user(
        uploaded_by,
        "uploaded_by",
    )

    reviewer = reviewed_by or uploaded_by

    _validate_user(
        reviewer,
        "reviewed_by",
    )

    normalized_stock_date = _coerce_stock_date(
        stock_date
    )

    source_system = ImportSourceSystem.objects.get(
        code__iexact=source_system_code,
        is_active=True,
    )

    truck_mapping = build_source_truck_mapping(
        source_system_code
    )

    adapted = adapt_raw_opening_stock_file(
        source,
        truck_mapping=truck_mapping,
        original_filename=original_filename,
    )

    rows_by_brand = (
        partition_raw_opening_stock_rows_by_brand(
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

            for brand_code in sorted(
                rows_by_brand
            ):
                brand_rows = rows_by_brand[
                    brand_code
                ]

                brand_file_result = (
                    RawOpeningStockFileResult(
                        filename=adapted.filename,
                        worksheet_name=(
                            adapted.worksheet_name
                        ),
                        rows=brand_rows,
                    )
                )

                row_result = (
                    to_report_row_read_result(
                        brand_file_result
                    )
                )

                cleaning_result = (
                    clean_report_rows_from_metadata(
                        row_result,
                        period_start=(
                            normalized_stock_date
                        ),
                        period_end=(
                            normalized_stock_date
                        ),
                    )
                )

                cleaning_result = (
                    enrich_raw_opening_stock_cleaning_result(
                        cleaning_result,
                        source_system=source_system,
                    )
                )

                summary = (
                    build_import_review_summary_from_metadata(
                        brand_code=brand_code,
                        period_start=(
                            normalized_stock_date
                        ),
                        period_end=(
                            normalized_stock_date
                        ),
                        row_result=row_result,
                        cleaning_result=(
                            cleaning_result
                        ),
                    )
                )

                prepared_rows = prepare_import_rows(
                    cleaning_result
                )

                logical_scope_batches = (
                    _logical_opening_stock_scope_batches(
                        brand_code=brand_code,
                        stock_date=(
                            normalized_stock_date
                        ),
                    )
                )

                mutable_batch = next(
                    (
                        candidate
                        for candidate
                        in logical_scope_batches
                        if candidate.status
                        in MUTABLE_BATCH_STATUSES
                    ),
                    None,
                )

                approved_batch = next(
                    (
                        candidate
                        for candidate
                        in logical_scope_batches
                        if candidate.status
                        == ImportBatchStatus.APPROVED
                    ),
                    None,
                )

                if mutable_batch is not None:
                    review_result = (
                        _persist_derived_import_review(
                            source_upload=source_upload,
                            uploaded_by=uploaded_by,
                            reviewer=reviewer,
                            batch=mutable_batch,
                            brand_code=brand_code,
                            report_type=(
                                "OPENING_STOCK"
                            ),
                            period_start=(
                                normalized_stock_date
                            ),
                            period_end=(
                                normalized_stock_date
                            ),
                            worksheet_name=(
                                adapted.worksheet_name
                            ),
                            summary=summary,
                            prepared_rows=prepared_rows,
                        )
                    )

                    batch = review_result.batch

                elif (
                    approved_batch is not None
                    and approved_batch.content_sha256
                    == prepared_rows.content_sha256
                ):
                    batch = approved_batch

                else:
                    replacement_target = (
                        approved_batch
                    )

                    review_result = (
                        _persist_derived_import_review(
                            source_upload=source_upload,
                            uploaded_by=uploaded_by,
                            reviewer=reviewer,
                            batch=None,
                            brand_code=brand_code,
                            report_type=(
                                "OPENING_STOCK"
                            ),
                            period_start=(
                                normalized_stock_date
                            ),
                            period_end=(
                                normalized_stock_date
                            ),
                            worksheet_name=(
                                adapted.worksheet_name
                            ),
                            summary=summary,
                            prepared_rows=prepared_rows,
                        )
                    )

                    batch = review_result.batch

                    if (
                        replacement_target
                        is not None
                    ):
                        batch.replaces_batch = (
                            replacement_target
                        )
                        batch.full_clean()
                        batch.save(
                            update_fields=[
                                "replaces_batch",
                                "updated_at",
                            ]
                        )

                batches.append(batch)

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

    return RawOpeningStockDerivedReviewResult(
        source_upload=source_upload,
        batches=tuple(batches),
    )