from dataclasses import dataclass
from typing import Any

from apps.imports.models import ImportBatch, ImportSourceUpload

from .derived_batch_review import _persist_derived_import_review
from .raw_items_detail_replacement import (
    ItemsDetailReplacementPlan,
    plan_items_detail_replacements,
)
from .raw_items_detail_review import RawItemsDetailBrandReview
from .review_summary import build_import_review_summary_from_metadata
from .row_staging import prepare_import_rows


@dataclass(frozen=True, slots=True)
class RawItemsDetailDerivedReviewResult:
    batch: ImportBatch
    replacement_plan: ItemsDetailReplacementPlan


def _items_detail_metadata(
    *,
    brand_review: RawItemsDetailBrandReview,
    replacement_plan: ItemsDetailReplacementPlan,
) -> dict[str, Any]:
    return {
        "transaction_level": True,
        "covered_trucks": list(brand_review.covered_trucks),
        "replacement_batch_ids": list(
            replacement_plan.replacement_batch_ids
        ),
    }


def persist_raw_items_detail_brand_review(
    *,
    source_upload: ImportSourceUpload,
    brand_review: RawItemsDetailBrandReview,
    uploaded_by: Any,
    reviewer: Any,
    period_start: Any,
    period_end: Any,
) -> RawItemsDetailDerivedReviewResult:
    """Persist one transaction-level Items brand partition for review.

    The replacement plan is calculated before persistence and copied into
    review_summary as audit metadata. Approval must still recalculate the
    plan under database locks; the stored ids are evidence of what the
    reviewer saw, not authority for superseding batches.
    """
    if source_upload.pk is None:
        raise ValueError("source_upload must be saved before derived review.")

    source_system = source_upload.source_system
    replacement_plan = plan_items_detail_replacements(
        source_system_code=source_system.code,
        brand_code=brand_review.brand_code,
        covered_trucks=brand_review.covered_trucks,
        period_start=period_start,
        period_end=period_end,
        current_source_upload_id=source_upload.pk,
    )

    summary = build_import_review_summary_from_metadata(
        brand_code=brand_review.brand_code,
        period_start=period_start,
        period_end=period_end,
        row_result=brand_review.row_result,
        cleaning_result=brand_review.cleaning_result,
    )
    prepared_rows = prepare_import_rows(
        brand_review.cleaning_result
    )

    persisted = _persist_derived_import_review(
        source_upload=source_upload,
        uploaded_by=uploaded_by,
        reviewer=reviewer,
        batch=None,
        brand_code=brand_review.brand_code,
        report_type="ITEMS",
        period_start=period_start,
        period_end=period_end,
        worksheet_name=source_upload.worksheet_name,
        summary=summary,
        prepared_rows=prepared_rows,
    )

    batch = persisted.batch
    review_summary = dict(batch.review_summary or {})
    review_summary["items_detail"] = _items_detail_metadata(
        brand_review=brand_review,
        replacement_plan=replacement_plan,
    )
    batch.review_summary = review_summary
    batch.full_clean()
    batch.save(update_fields=["review_summary", "updated_at"])

    return RawItemsDetailDerivedReviewResult(
        batch=batch,
        replacement_plan=replacement_plan,
    )
