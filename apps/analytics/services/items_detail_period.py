from dataclasses import dataclass
from datetime import date, datetime

from .items_period_filter import (
    ItemsRowPeriodStatus,
    decide_items_row_period,
)


@dataclass(frozen=True, slots=True)
class ItemsRowPeriodScope:
    status: ItemsRowPeriodStatus
    attribution_period_start: date
    attribution_period_end: date
    uses_exact_sale_date: bool


def resolve_items_row_period_scope(
    *,
    batch_period_start: date,
    batch_period_end: date,
    sale_datetime: datetime | None,
    requested_period_start: date | None,
    requested_period_end: date | None,
) -> ItemsRowPeriodScope:
    """Resolve filtering and worker-attribution dates for one Items row.

    Detail rows use their real sale date both for requested-period
    filtering and worker assignment resolution. Legacy rows without a
    transaction timestamp retain the batch period so historical behaviour
    stays conservative and no synthetic transaction date is introduced.
    """
    decision = decide_items_row_period(
        batch_period_start=batch_period_start,
        batch_period_end=batch_period_end,
        sale_datetime=sale_datetime,
        requested_period_start=requested_period_start,
        requested_period_end=requested_period_end,
    )

    if sale_datetime is not None:
        attribution_date = sale_datetime.date()
        attribution_period_start = attribution_date
        attribution_period_end = attribution_date
    else:
        attribution_period_start = batch_period_start
        attribution_period_end = batch_period_end

    return ItemsRowPeriodScope(
        status=decision.status,
        attribution_period_start=attribution_period_start,
        attribution_period_end=attribution_period_end,
        uses_exact_sale_date=decision.uses_exact_sale_date,
    )
