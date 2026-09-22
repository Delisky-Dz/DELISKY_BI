from dataclasses import dataclass
from typing import Any, Mapping

from django.db import transaction

from apps.imports.models import (
    ImportBatch,
    ImportSourceUpload,
)

from .batch_review import MUTABLE_BATCH_STATUSES
from .raw_items_detail_derived_review import (
    RawItemsDetailDerivedReviewResult,
    persist_raw_items_detail_brand_review,
)
from .raw_items_detail_review import RawItemsDetailReviewResult


@dataclass(frozen=True, slots=True)
class RawItemsDetailMultiBrandReviewResult:
    source_upload: ImportSourceUpload
    brand_results: tuple[RawItemsDetailDerivedReviewResult, ...]

    @property
    def batches(self):
        return tuple(result.batch for result in self.brand_results)


def _normalized_existing_batches(
    *,
    source_upload: ImportSourceUpload,
    existing_batches_by_brand: (
        Mapping[str, ImportBatch] | None
    ),
) -> dict[str, ImportBatch]:
    normalized: dict[str, ImportBatch] = {}

    for raw_brand, batch in (
        existing_batches_by_brand or {}
    ).items():
        brand_code = str(
            raw_brand or ""
        ).strip().upper()

        if not brand_code:
            raise ValueError(
                "Existing Items detail batch brand is required."
            )

        if batch.pk is None:
            raise ValueError(
                "Existing Items detail batches must be saved."
            )

        if batch.source_upload_id != source_upload.pk:
            raise ValueError(
                (
                    "Existing Items detail batches must "
                    "belong to the same source upload."
                )
            )

        if batch.status not in MUTABLE_BATCH_STATUSES:
            raise ValueError(
                (
                    "Only mutable Items detail batches "
                    "may be refreshed."
                )
            )

        if brand_code in normalized:
            raise ValueError(
                (
                    "Only one mutable Items detail batch "
                    "per brand may be refreshed."
                )
            )

        normalized[brand_code] = batch

    return normalized


def persist_raw_items_detail_review(
    *,
    source_upload: ImportSourceUpload,
    review: RawItemsDetailReviewResult,
    uploaded_by: Any,
    reviewer: Any,
    existing_batches_by_brand: (
        Mapping[str, ImportBatch] | None
    ) = None,
) -> RawItemsDetailMultiBrandReviewResult:
    """Persist every brand partition from one Items detail export atomically.

    A single source export may contain BIFA, DELISKY and NITA rows. Either
    every derived brand batch is persisted, or none is. Existing mutable
    batches from the same immutable raw source are refreshed in place. If a
    reference-data change removes a brand partition, its stale mutable batch
    is deleted in the same transaction so the source cannot become partially
    visible.
    """
    if source_upload.pk is None:
        raise ValueError(
            "source_upload must be saved before multi-brand derived review."
        )

    if not review.brand_reviews:
        raise ValueError(
            "Items detail review must contain at least one brand partition."
        )

    results: list[
        RawItemsDetailDerivedReviewResult
    ] = []

    with transaction.atomic():
        locked_upload = (
            ImportSourceUpload.objects
            .select_for_update()
            .select_related("source_system")
            .get(pk=source_upload.pk)
        )

        existing = _normalized_existing_batches(
            source_upload=locked_upload,
            existing_batches_by_brand=(
                existing_batches_by_brand
            ),
        )

        reviewed_brand_codes: set[str] = set()

        for brand_review in review.brand_reviews:
            brand_code = str(
                brand_review.brand_code or ""
            ).strip().upper()

            if not brand_code:
                raise ValueError(
                    "Items detail brand code is required."
                )

            if brand_code in reviewed_brand_codes:
                raise ValueError(
                    (
                        "Items detail review contains "
                        "the same brand more than once."
                    )
                )

            reviewed_brand_codes.add(brand_code)

            results.append(
                persist_raw_items_detail_brand_review(
                    source_upload=locked_upload,
                    brand_review=brand_review,
                    uploaded_by=uploaded_by,
                    reviewer=reviewer,
                    period_start=review.period_start,
                    period_end=review.period_end,
                    batch=existing.get(brand_code),
                )
            )

        stale_brand_codes = (
            set(existing)
            - reviewed_brand_codes
        )

        for brand_code in sorted(
            stale_brand_codes
        ):
            existing[brand_code].delete()

    return RawItemsDetailMultiBrandReviewResult(
        source_upload=locked_upload,
        brand_results=tuple(results),
    )
