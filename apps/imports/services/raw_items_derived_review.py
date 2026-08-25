from dataclasses import dataclass
from typing import Any

from django.db import transaction

from apps.analytics.services.truck_resolver import (
    TruckResolutionStatus,
    build_truck_code_index,
    resolve_truck_by_van,
)
from apps.fleet.models import Truck
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
from .raw_items_cleaning_enrichment import (
    enrich_raw_items_cleaning_result,
)
from .raw_items_file import (
    RawItemsFileError,
    source_truck_code_from_filename,
)
from .raw_items_review import (
    RawItemsReviewResult,
    prepare_raw_items_review,
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


class RawItemsDerivedReviewError(Exception):
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
class RawItemsDerivedReviewResult:
    source_upload: ImportSourceUpload
    batch: ImportBatch


def _logical_items_scope_batches(
    *,
    source_system_code: str,
    source_truck_code: str,
    brand_code: str,
    period_start: Any,
    period_end: Any,
) -> tuple[ImportBatch, ...]:
    candidates = (
        ImportBatch.objects
        .select_related(
            "source_upload",
            "source_upload__source_system",
        )
        .filter(
            source_upload__isnull=False,
            source_upload__source_system__code__iexact=(
                source_system_code
            ),
            brand__code__iexact=brand_code,
            report_type="ITEMS",
            period_start=period_start,
            period_end=period_end,
        )
        .order_by("-id")
    )

    matched: list[ImportBatch] = []

    for candidate in candidates:
        source_upload = candidate.source_upload

        if source_upload is None:
            continue

        try:
            candidate_source_truck = (
                source_truck_code_from_filename(
                    source_upload.original_filename
                )
            )
        except RawItemsFileError:
            continue

        if candidate_source_truck != source_truck_code:
            continue

        matched.append(candidate)

    return tuple(matched)


def _resolve_items_brand_code(
    review: RawItemsReviewResult,
) -> str:
    if not review.adapted.rows:
        raise RawItemsDerivedReviewError(
            "empty_items_file",
            "The raw Items file contains no items rows.",
        )

    vans = {
        row.values.get("VAN")
        for row in review.adapted.rows
    }

    if len(vans) != 1:
        raise RawItemsDerivedReviewError(
            "multiple_items_trucks",
            (
                "A raw Items file must resolve to "
                "exactly one DELISKY BI truck."
            ),
            details={
                "vans": sorted(
                    str(value)
                    for value in vans
                ),
            },
        )

    van = next(iter(vans))

    trucks = (
        Truck.objects
        .select_related("distribution_brand")
        .all()
    )

    truck_index = build_truck_code_index(
        trucks
    )

    resolution = resolve_truck_by_van(
        van,
        truck_index=truck_index,
    )

    if (
        resolution.status
        == TruckResolutionStatus.MISSING_VAN
    ):
        raise RawItemsDerivedReviewError(
            "missing_van",
            "The adapted Items file has no VAN.",
            details={
                "van": van,
            },
        )

    if (
        resolution.status
        == TruckResolutionStatus.TRUCK_NOT_FOUND
    ):
        raise RawItemsDerivedReviewError(
            "truck_not_found",
            (
                "The adapted Items VAN does not match "
                "a DELISKY BI truck."
            ),
            details={
                "van": van,
            },
        )

    if (
        resolution.status
        == TruckResolutionStatus.AMBIGUOUS_TRUCK_CODE
    ):
        raise RawItemsDerivedReviewError(
            "ambiguous_truck_code",
            (
                "The adapted Items VAN matches more "
                "than one DELISKY BI truck."
            ),
            details={
                "van": van,
                "matching_truck_ids": (
                    resolution.matching_truck_ids
                ),
            },
        )

    truck = resolution.truck

    if truck is None:
        raise RawItemsDerivedReviewError(
            "truck_resolution_failed",
            "The Items truck resolution result is invalid.",
            details={
                "van": van,
            },
        )

    brand = truck.distribution_brand

    if brand is None:
        raise RawItemsDerivedReviewError(
            "missing_distribution_brand",
            (
                "The resolved Items truck has no "
                "distribution brand."
            ),
            details={
                "van": van,
                "truck_id": truck.pk,
            },
        )

    brand_code = str(
        brand.code or ""
    ).strip().upper()

    if not brand_code:
        raise RawItemsDerivedReviewError(
            "missing_distribution_brand_code",
            (
                "The resolved Items truck distribution "
                "brand has no code."
            ),
            details={
                "van": van,
                "truck_id": truck.pk,
                "distribution_brand_id": brand.pk,
            },
        )

    if not brand.is_active:
        raise RawItemsDerivedReviewError(
            "distribution_brand_inactive",
            (
                "The resolved Items truck distribution "
                "brand is inactive."
            ),
            details={
                "brand_code": brand_code,
                "distribution_brand_id": brand.pk,
            },
        )

    return brand_code


def create_raw_items_derived_import_review(
    source: Any,
    *,
    source_system_code: str,
    uploaded_by: Any,
    period_start: Any,
    period_end: Any,
    reviewed_by: Any | None = None,
    original_filename: str | None = None,
) -> RawItemsDerivedReviewResult:
    _validate_user(
        uploaded_by,
        "uploaded_by",
    )

    reviewer = reviewed_by or uploaded_by

    _validate_user(
        reviewer,
        "reviewed_by",
    )

    truck_mapping = build_source_truck_mapping(
        source_system_code
    )

    review = prepare_raw_items_review(
        source,
        truck_mapping=truck_mapping,
        period_start=period_start,
        period_end=period_end,
        original_filename=original_filename,
    )

    brand_code = _resolve_items_brand_code(
        review
    )

    source_system = (
        ImportSourceSystem.objects.get(
            code__iexact=source_system_code,
            is_active=True,
        )
    )

    cleaning_result = (
        enrich_raw_items_cleaning_result(
            review.cleaning_result,
            source_system=source_system,
        )
    )

    summary = (
        build_import_review_summary_from_metadata(
            brand_code=brand_code,
            period_start=review.period_start,
            period_end=review.period_end,
            row_result=review.row_result,
            cleaning_result=cleaning_result,
        )
    )

    prepared_rows = prepare_import_rows(
        cleaning_result
    )

    source_upload_result = None

    try:
        with transaction.atomic():
            source_upload_result = (
                create_import_source_upload(
                    source,
                    source_system_code=source_system_code,
                    uploaded_by=uploaded_by,
                    worksheet_name=(
                        review.adapted.worksheet_name
                    ),
                    original_filename=(
                        review.adapted.filename
                    ),
                )
            )

            source_upload = (
                source_upload_result.source_upload
            )

            ImportSourceSystem.objects.select_for_update().get(
                pk=source_upload.source_system_id
            )

            logical_scope_batches = (
                _logical_items_scope_batches(
                    source_system_code=source_system_code,
                    source_truck_code=(
                        review.adapted.source_truck_code
                    ),
                    brand_code=brand_code,
                    period_start=review.period_start,
                    period_end=review.period_end,
                )
            )

            mutable_batch = next(
                (
                    candidate
                    for candidate in logical_scope_batches
                    if candidate.status
                    in MUTABLE_BATCH_STATUSES
                ),
                None,
            )

            approved_batch = next(
                (
                    candidate
                    for candidate in logical_scope_batches
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
                        report_type="ITEMS",
                        period_start=review.period_start,
                        period_end=review.period_end,
                        worksheet_name=(
                            review.adapted.worksheet_name
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
                replacement_target = approved_batch

                review_result = (
                    _persist_derived_import_review(
                        source_upload=source_upload,
                        uploaded_by=uploaded_by,
                        reviewer=reviewer,
                        batch=None,
                        brand_code=brand_code,
                        report_type="ITEMS",
                        period_start=review.period_start,
                        period_end=review.period_end,
                        worksheet_name=(
                            review.adapted.worksheet_name
                        ),
                        summary=summary,
                        prepared_rows=prepared_rows,
                    )
                )

                batch = review_result.batch

                if replacement_target is not None:
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

    return RawItemsDerivedReviewResult(
        source_upload=source_upload,
        batch=batch,
    )
