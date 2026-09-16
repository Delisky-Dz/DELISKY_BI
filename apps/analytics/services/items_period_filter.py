from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class ItemsRowPeriodStatus(StrEnum):
    INCLUDED = "INCLUDED"
    OUTSIDE = "OUTSIDE"
    PARTIAL_OVERLAP = "PARTIAL_OVERLAP"


@dataclass(frozen=True, slots=True)
class ItemsRowPeriodDecision:
    status: ItemsRowPeriodStatus
    uses_exact_sale_date: bool


def decide_items_row_period(
    *,
    batch_period_start: date,
    batch_period_end: date,
    sale_datetime: datetime | None,
    requested_period_start: date | None,
    requested_period_end: date | None,
) -> ItemsRowPeriodDecision:
    """Choose exact transaction-date filtering when available.

    Transaction-level Items rows are filtered by their real sale date.
    Legacy Items rows without ``sale_datetime`` retain the conservative
    batch-period behaviour: partial overlaps are excluded rather than
    apportioned to invented dates.
    """
    if (
        requested_period_start is not None
        and requested_period_end is not None
        and requested_period_end < requested_period_start
    ):
        raise ValueError("requested_period_end cannot be before requested_period_start.")

    if sale_datetime is not None:
        sale_date = sale_datetime.date()
        outside = (
            requested_period_start is not None
            and sale_date < requested_period_start
        ) or (
            requested_period_end is not None
            and sale_date > requested_period_end
        )
        return ItemsRowPeriodDecision(
            status=(
                ItemsRowPeriodStatus.OUTSIDE
                if outside
                else ItemsRowPeriodStatus.INCLUDED
            ),
            uses_exact_sale_date=True,
        )

    if (
        requested_period_start is not None
        and batch_period_end < requested_period_start
    ) or (
        requested_period_end is not None
        and batch_period_start > requested_period_end
    ):
        status = ItemsRowPeriodStatus.OUTSIDE
    elif (
        requested_period_start is not None
        and batch_period_start < requested_period_start
    ) or (
        requested_period_end is not None
        and batch_period_end > requested_period_end
    ):
        status = ItemsRowPeriodStatus.PARTIAL_OVERLAP
    else:
        status = ItemsRowPeriodStatus.INCLUDED

    return ItemsRowPeriodDecision(
        status=status,
        uses_exact_sale_date=False,
    )
