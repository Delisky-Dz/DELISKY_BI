from datetime import date
from typing import Iterable

from django.db.models import QuerySet

from apps.imports.models import (
    ImportBatch,
    ImportBatchStatus,
    ImportReportType,
    ImportRow,
    ImportRowStatus,
)


CALCULATION_ROW_STATUSES = (
    ImportRowStatus.ACCEPTED,
)

ACTIVITY_ROW_STATUSES = (
    ImportRowStatus.ACCEPTED,
    ImportRowStatus.STOPPED,
)


def get_approved_rows(
    *,
    report_type: str | None = None,
    brand_id: int | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    row_statuses: Iterable[str] = CALCULATION_ROW_STATUSES,
) -> QuerySet[ImportRow]:
    """
    Return rows belonging only to currently approved import batches.

    By default, only ACCEPTED rows are returned for calculations.
    STOPPED rows must be explicitly requested when determining
    operational truck status.
    """
    if (
        period_start is not None
        and period_end is not None
        and period_end < period_start
    ):
        raise ValueError(
            "period_end cannot be before period_start."
        )

    statuses = tuple(row_statuses)

    if not statuses:
        return ImportRow.objects.none()

    queryset = (
        ImportRow.objects
        .filter(
            batch__status=ImportBatchStatus.APPROVED,
            status__in=statuses,
        )
        .select_related(
            "batch",
            "batch__brand",
        )
    )

    if report_type is not None:
        if report_type not in ImportReportType.values:
            raise ValueError(
                f"Unsupported report type: {report_type}"
            )

        queryset = queryset.filter(
            batch__report_type=report_type,
        )

    if brand_id is not None:
        queryset = queryset.filter(
            batch__brand_id=brand_id,
        )

    if period_start is not None:
        queryset = queryset.filter(
            batch__period_end__gte=period_start,
        )

    if period_end is not None:
        queryset = queryset.filter(
            batch__period_start__lte=period_end,
        )

    return queryset.order_by(
        "batch__period_start",
        "batch_id",
        "excel_row_number",
    )


def get_approved_calculation_rows(
    **filters,
) -> QuerySet[ImportRow]:
    """
    Return ACCEPTED rows only.

    EXCLUDED and STOPPED rows never enter sales, quantity,
    stock or performance calculations.
    """
    return get_approved_rows(
        row_statuses=CALCULATION_ROW_STATUSES,
        **filters,
    )



def get_approved_opening_stock_baseline_rows(
    *,
    period_start: date | None = None,
    period_end: date | None = None,
    brand_id: int | None = None,
) -> QuerySet[ImportRow]:
    """
    Return ACCEPTED rows from the latest approved opening-stock
    snapshot available on or before the analysis baseline date.

    Snapshot selection is independent per brand.

    period_start is the preferred baseline anchor. When it is not
    supplied, period_end is used. With no requested period, the
    latest approved snapshot available for each brand is selected.
    """
    if (
        period_start is not None
        and period_end is not None
        and period_end < period_start
    ):
        raise ValueError(
            "period_end cannot be before period_start."
        )

    anchor_date = (
        period_start
        if period_start is not None
        else period_end
    )

    batches = ImportBatch.objects.filter(
        status=ImportBatchStatus.APPROVED,
        report_type=ImportReportType.OPENING_STOCK,
    )

    if brand_id is not None:
        batches = batches.filter(
            brand_id=brand_id,
        )

    if anchor_date is not None:
        batches = batches.filter(
            period_start__lte=anchor_date,
        )

    latest_snapshot_by_brand: dict[
        int,
        date,
    ] = {}

    for (
        current_brand_id,
        snapshot_date,
    ) in (
        batches
        .order_by(
            "brand_id",
            "-period_start",
            "-id",
        )
        .values_list(
            "brand_id",
            "period_start",
        )
    ):
        latest_snapshot_by_brand.setdefault(
            current_brand_id,
            snapshot_date,
        )

    if not latest_snapshot_by_brand:
        return ImportRow.objects.none()

    selected_batch_ids = [
        batch_id
        for (
            batch_id,
            current_brand_id,
            snapshot_date,
        ) in batches.values_list(
            "id",
            "brand_id",
            "period_start",
        )
        if (
            latest_snapshot_by_brand.get(
                current_brand_id
            )
            == snapshot_date
        )
    ]

    return get_approved_calculation_rows(
        report_type=ImportReportType.OPENING_STOCK,
        brand_id=brand_id,
    ).filter(
        batch_id__in=selected_batch_ids,
    )


def get_approved_activity_rows(
    **filters,
) -> QuerySet[ImportRow]:
    """
    Return ACCEPTED and STOPPED rows.

    Intended for operational-state analysis where STOPPED rows
    are required without treating them as sales or failures.
    """
    return get_approved_rows(
        row_statuses=ACTIVITY_ROW_STATUSES,
        **filters,
    )
