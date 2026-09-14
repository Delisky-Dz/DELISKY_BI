from dataclasses import dataclass
from datetime import date

from django import template

from apps.imports.models import (
    ImportBatch,
    ImportBatchStatus,
    ImportReportType,
)


register = template.Library()


@dataclass(frozen=True, slots=True)
class ItemsSourcePeriod:
    start: date
    end: date


@dataclass(frozen=True, slots=True)
class ItemsPeriodGuidance:
    has_overlapping_sources: bool
    has_partial_overlap: bool
    source_periods: tuple[ItemsSourcePeriod, ...]
    suggested_period: ItemsSourcePeriod | None


def _is_partial_overlap(
    source_period: ItemsSourcePeriod,
    *,
    requested_start: date | None,
    requested_end: date | None,
) -> bool:
    if (
        requested_start is not None
        and source_period.start < requested_start
    ):
        return True

    if (
        requested_end is not None
        and source_period.end > requested_end
    ):
        return True

    return False


@register.simple_tag
def items_period_guidance(
    period_start,
    period_end,
    brand=None,
) -> ItemsPeriodGuidance:
    """Describe approved ITEMS source periods overlapping a filter.

    ITEMS reports are period-level. A source batch can only be used when
    its complete period fits inside the requested analysis period. This
    helper gives manager templates enough context to explain partial
    overlap exclusions without changing analytical calculations.
    """
    queryset = ImportBatch.objects.filter(
        status=ImportBatchStatus.APPROVED,
        report_type=ImportReportType.ITEMS,
    )

    brand_id = getattr(brand, "pk", None)
    if brand_id:
        queryset = queryset.filter(brand_id=brand_id)

    if period_start is not None:
        queryset = queryset.filter(
            period_end__gte=period_start,
        )

    if period_end is not None:
        queryset = queryset.filter(
            period_start__lte=period_end,
        )

    periods = tuple(
        ItemsSourcePeriod(start=start, end=end)
        for start, end in (
            queryset
            .values_list("period_start", "period_end")
            .distinct()
            .order_by("period_start", "period_end")
        )
    )

    has_partial_overlap = any(
        _is_partial_overlap(
            source_period,
            requested_start=period_start,
            requested_end=period_end,
        )
        for source_period in periods
    )

    suggested_period = (
        periods[0]
        if has_partial_overlap and len(periods) == 1
        else None
    )

    return ItemsPeriodGuidance(
        has_overlapping_sources=bool(periods),
        has_partial_overlap=has_partial_overlap,
        source_periods=periods,
        suggested_period=suggested_period,
    )
