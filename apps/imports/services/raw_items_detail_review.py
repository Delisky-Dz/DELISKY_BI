from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from apps.imports.models import ImportSourceSystem

from .raw_items_cleaning_enrichment import enrich_raw_items_cleaning_result
from .raw_items_detail_brand_partition import partition_raw_items_detail_rows_by_brand
from .raw_items_detail_cleaning import clean_raw_items_detail_rows
from .raw_items_detail_file import (
    ExcludedItemsDetailSourceRow,
    RawItemsDetailFileResult,
    adapt_raw_items_detail_file,
    to_report_row_read_result,
)
from .source_truck_mapping_store import (
    build_source_truck_exclusions,
    build_source_truck_mapping,
)


class RawItemsDetailReviewError(Exception):
    def __init__(self, code: str, message: str, *, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True, slots=True)
class RawItemsDetailBrandReview:
    brand_code: str
    covered_trucks: tuple[str, ...]
    row_result: Any
    cleaning_result: Any


@dataclass(frozen=True, slots=True)
class RawItemsDetailReviewResult:
    adapted: RawItemsDetailFileResult
    brand_reviews: tuple[RawItemsDetailBrandReview, ...]
    excluded_source_rows: tuple[ExcludedItemsDetailSourceRow, ...]
    period_start: date
    period_end: date


def _coerce_period_date(value: Any, *, field_name: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            pass
    raise RawItemsDetailReviewError(
        "invalid_period_date",
        f"{field_name} must be a valid ISO date.",
        details={"field_name": field_name, "value": str(value)},
    )


def prepare_raw_items_detail_review(
    source: Any,
    *,
    source_system_code: str,
    period_start: Any,
    period_end: Any,
    original_filename: str | None = None,
) -> RawItemsDetailReviewResult:
    normalized_start = _coerce_period_date(period_start, field_name="period_start")
    normalized_end = _coerce_period_date(period_end, field_name="period_end")
    if normalized_end < normalized_start:
        raise RawItemsDetailReviewError(
            "invalid_period_range",
            "period_end cannot be before period_start.",
        )

    source_system = ImportSourceSystem.objects.filter(
        code__iexact=str(source_system_code or "").strip(),
        is_active=True,
    ).first()
    if source_system is None:
        raise RawItemsDetailReviewError(
            "source_system_not_found",
            "An active source system is required for Items detail review.",
            details={"source_system_code": source_system_code},
        )

    adapted = adapt_raw_items_detail_file(
        source,
        truck_mapping=build_source_truck_mapping(source_system.code),
        source_exclusions=build_source_truck_exclusions(source_system.code),
        original_filename=original_filename,
    )
    partitions = partition_raw_items_detail_rows_by_brand(adapted.rows)

    brand_reviews = []
    for brand_code in sorted(partitions):
        rows = partitions[brand_code]
        brand_result = RawItemsDetailFileResult(
            filename=adapted.filename,
            worksheet_name=adapted.worksheet_name,
            rows=rows,
        )
        row_result = to_report_row_read_result(brand_result)
        cleaned = clean_raw_items_detail_rows(
            row_result,
            period_start=normalized_start,
            period_end=normalized_end,
        )
        enriched = enrich_raw_items_cleaning_result(
            cleaned,
            source_system=source_system,
        )
        covered_trucks = tuple(sorted({
            str(row.values.get("VAN") or "").strip().upper()
            for row in rows
            if str(row.values.get("VAN") or "").strip()
        }))
        brand_reviews.append(
            RawItemsDetailBrandReview(
                brand_code=brand_code,
                covered_trucks=covered_trucks,
                row_result=row_result,
                cleaning_result=enriched,
            )
        )

    return RawItemsDetailReviewResult(
        adapted=adapted,
        brand_reviews=tuple(brand_reviews),
        excluded_source_rows=adapted.excluded_source_rows,
        period_start=normalized_start,
        period_end=normalized_end,
    )
