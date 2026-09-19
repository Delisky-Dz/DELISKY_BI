from dataclasses import dataclass
from typing import Any

from django.db import transaction

from apps.imports.models import ImportSourceUpload

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


def persist_raw_items_detail_review(
    *,
    source_upload: ImportSourceUpload,
    review: RawItemsDetailReviewResult,
    uploaded_by: Any,
    reviewer: Any,
) -> RawItemsDetailMultiBrandReviewResult:
    """Persist every brand partition from one Items detail export atomically.

    A single source export may contain BIFA, DELISKY and NITA rows. Either
    every derived brand batch is persisted, or none is. This prevents an
    upload from becoming only partially visible when a later brand fails
    validation or replacement planning.
    """
    if source_upload.pk is None:
        raise ValueError(
            "source_upload must be saved before multi-brand derived review."
        )

    if not review.brand_reviews:
        raise ValueError(
            "Items detail review must contain at least one brand partition."
        )

    results: list[RawItemsDetailDerivedReviewResult] = []

    with transaction.atomic():
        # Serialize derived review creation for the shared source upload.
        locked_upload = (
            ImportSourceUpload.objects
            .select_for_update()
            .select_related("source_system")
            .get(pk=source_upload.pk)
        )

        for brand_review in review.brand_reviews:
            results.append(
                persist_raw_items_detail_brand_review(
                    source_upload=locked_upload,
                    brand_review=brand_review,
                    uploaded_by=uploaded_by,
                    reviewer=reviewer,
                    period_start=review.period_start,
                    period_end=review.period_end,
                )
            )

    return RawItemsDetailMultiBrandReviewResult(
        source_upload=locked_upload,
        brand_results=tuple(results),
    )
