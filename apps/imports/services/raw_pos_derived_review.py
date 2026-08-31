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
from .raw_pos_file import (
    RawPosFileError,
    source_truck_code_from_filename,
)
from .raw_pos_review import (
    RawPosReviewResult,
    prepare_raw_pos_review,
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


class RawPosDerivedReviewError(Exception):
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
class RawPosDerivedReviewResult:
    source_upload: ImportSourceUpload
    batch: ImportBatch


def _logical_pos_scope_batches(
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
            report_type="POS",
            period_start__lte=period_end,
            period_end__gte=period_start,
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
        except RawPosFileError:
            continue

        if (
            candidate_source_truck
            != source_truck_code
        ):
            continue

        matched.append(candidate)

    return tuple(matched)


def _resolve_pos_brand_code(
    review: RawPosReviewResult,
) -> str:
    if not review.adapted.rows:
        raise RawPosDerivedReviewError(
            "empty_pos_file",
            (
                "The raw POS file contains "
                "no activity rows."
            ),
        )

    vans = {
        row.values.get("VAN")
        for row in review.adapted.rows
    }

    if len(vans) != 1:
        raise RawPosDerivedReviewError(
            "multiple_pos_trucks",
            (
                "A raw POS file must resolve to "
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
        .select_related(
            "distribution_brand"
        )
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
        raise RawPosDerivedReviewError(
            "missing_van",
            "The adapted POS file has no VAN.",
            details={
                "van": van,
            },
        )

    if (
        resolution.status
        == TruckResolutionStatus.TRUCK_NOT_FOUND
    ):
        raise RawPosDerivedReviewError(
            "truck_not_found",
            (
                "The adapted POS VAN does not match "
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
        raise RawPosDerivedReviewError(
            "ambiguous_truck_code",
            (
                "The adapted POS VAN matches more "
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
        raise RawPosDerivedReviewError(
            "truck_resolution_failed",
            (
                "The POS truck resolution "
                "result is invalid."
            ),
            details={
                "van": van,
            },
        )

    brand = truck.distribution_brand

    if brand is None:
        raise RawPosDerivedReviewError(
            "missing_distribution_brand",
            (
                "The resolved POS truck has no "
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
        raise RawPosDerivedReviewError(
            "missing_distribution_brand_code",
            (
                "The resolved POS truck distribution "
                "brand has no code."
            ),
            details={
                "van": van,
                "truck_id": truck.pk,
                "distribution_brand_id": brand.pk,
            },
        )

    if not brand.is_active:
        raise RawPosDerivedReviewError(
            "distribution_brand_inactive",
            (
                "The resolved POS truck distribution "
                "brand is inactive."
            ),
            details={
                "brand_code": brand_code,
                "distribution_brand_id": brand.pk,
            },
        )

    return brand_code


def create_raw_pos_derived_import_review(
    source: Any,
    *,
    source_system_code: str,
    uploaded_by: Any,
    period_start: Any,
    period_end: Any,
    reviewed_by: Any | None = None,
    original_filename: str | None = None,
) -> RawPosDerivedReviewResult:
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

    review = prepare_raw_pos_review(
        source,
        truck_mapping=truck_mapping,
        period_start=period_start,
        period_end=period_end,
        original_filename=original_filename,
    )

    brand_code = _resolve_pos_brand_code(
        review
    )

    summary = (
        build_import_review_summary_from_metadata(
            brand_code=brand_code,
            period_start=review.period_start,
            period_end=review.period_end,
            row_result=review.row_result,
            cleaning_result=review.cleaning_result,
        )
    )

    prepared_rows = prepare_import_rows(
        review.cleaning_result
    )

    source_upload_result = None

    try:
        with transaction.atomic():
            source_upload_result = (
                create_import_source_upload(
                    source,
                    source_system_code=(
                        source_system_code
                    ),
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

            (
                ImportSourceSystem.objects
                .select_for_update()
                .get(
                    pk=source_upload.source_system_id
                )
            )

            logical_scope_batches = (
                _logical_pos_scope_batches(
                    source_system_code=(
                        source_system_code
                    ),
                    source_truck_code=(
                        review.adapted
                        .source_truck_code
                    ),
                    brand_code=brand_code,
                    period_start=(
                        review.period_start
                    ),
                    period_end=(
                        review.period_end
                    ),
                )
            )

            active_batches = [
                candidate
                for candidate
                in logical_scope_batches
                if (
                    candidate.status
                    in MUTABLE_BATCH_STATUSES
                    or candidate.status
                    == ImportBatchStatus.APPROVED
                )
            ]

            exact_batches = [
                candidate
                for candidate
                in active_batches
                if (
                    candidate.period_start
                    == review.period_start
                    and candidate.period_end
                    == review.period_end
                )
            ]

            non_exact_overlaps = [
                candidate
                for candidate
                in active_batches
                if candidate not in exact_batches
            ]

            if non_exact_overlaps:
                raise RawPosDerivedReviewError(
                    "pos_period_overlap_conflict",
                    (
                        "An active POS batch already "
                        "overlaps the requested period "
                        "for this source truck."
                    ),
                    details={
                        "batch_ids": [
                            candidate.pk
                            for candidate
                            in non_exact_overlaps
                        ],
                    },
                )

            mutable_batches = [
                candidate
                for candidate
                in exact_batches
                if candidate.status
                in MUTABLE_BATCH_STATUSES
            ]

            approved_batches = [
                candidate
                for candidate
                in exact_batches
                if candidate.status
                == ImportBatchStatus.APPROVED
            ]

            if len(mutable_batches) > 1:
                raise RawPosDerivedReviewError(
                    "pos_multiple_mutable_batches",
                    (
                        "More than one mutable POS "
                        "batch exists for the same "
                        "source truck and period."
                    ),
                    details={
                        "batch_ids": [
                            candidate.pk
                            for candidate
                            in mutable_batches
                        ],
                    },
                )

            if len(approved_batches) > 1:
                raise RawPosDerivedReviewError(
                    "pos_multiple_approved_batches",
                    (
                        "More than one approved POS "
                        "batch exists for the same "
                        "source truck and period."
                    ),
                    details={
                        "batch_ids": [
                            candidate.pk
                            for candidate
                            in approved_batches
                        ],
                    },
                )

            if (
                mutable_batches
                and approved_batches
            ):
                raise RawPosDerivedReviewError(
                    "pos_approved_mutable_conflict",
                    (
                        "An approved and a mutable POS "
                        "batch both exist for the same "
                        "source truck and period."
                    ),
                    details={
                        "mutable_batch_id": (
                            mutable_batches[0].pk
                        ),
                        "approved_batch_id": (
                            approved_batches[0].pk
                        ),
                    },
                )

            mutable_batch = (
                mutable_batches[0]
                if mutable_batches
                else None
            )

            approved_batch = (
                approved_batches[0]
                if approved_batches
                else None
            )

            if approved_batch is not None:
                if (
                    approved_batch.content_sha256
                    != prepared_rows.content_sha256
                ):
                    raise RawPosDerivedReviewError(
                        "pos_approved_content_conflict",
                        (
                            "A different approved POS "
                            "batch already exists for "
                            "this source truck and period."
                        ),
                        details={
                            "approved_batch_id": (
                                approved_batch.pk
                            ),
                        },
                    )

                batch = approved_batch

            elif mutable_batch is not None:
                review_result = (
                    _persist_derived_import_review(
                        source_upload=source_upload,
                        uploaded_by=uploaded_by,
                        reviewer=reviewer,
                        batch=mutable_batch,
                        brand_code=brand_code,
                        report_type="POS",
                        period_start=(
                            review.period_start
                        ),
                        period_end=(
                            review.period_end
                        ),
                        worksheet_name=(
                            review.adapted
                            .worksheet_name
                        ),
                        summary=summary,
                        prepared_rows=prepared_rows,
                    )
                )

                batch = review_result.batch

            else:
                review_result = (
                    _persist_derived_import_review(
                        source_upload=source_upload,
                        uploaded_by=uploaded_by,
                        reviewer=reviewer,
                        batch=None,
                        brand_code=brand_code,
                        report_type="POS",
                        period_start=(
                            review.period_start
                        ),
                        period_end=(
                            review.period_end
                        ),
                        worksheet_name=(
                            review.adapted
                            .worksheet_name
                        ),
                        summary=summary,
                        prepared_rows=prepared_rows,
                    )
                )

                batch = review_result.batch

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
                    (
                        source_upload
                        .source_file
                        .storage
                        .delete(saved_file_name)
                    )
                except Exception:
                    pass

        raise

    return RawPosDerivedReviewResult(
        source_upload=source_upload,
        batch=batch,
    )
