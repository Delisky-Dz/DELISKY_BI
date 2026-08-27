from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Iterable

from apps.imports.models import (
    ImportReportType,
    ImportRow,
)

from .approved_data_source import (
    get_approved_calculation_rows,
)
from .assignment_resolver import (
    AssignmentIndex,
    build_assignment_index,
    resolve_worker_for_date,
)
from .report_rows import parse_sales_row
from .truck_resolver import (
    TruckCodeIndex,
    build_truck_code_index,
    resolve_truck_by_van,
)


class SalesAttributionStage(StrEnum):
    TRUCK = "TRUCK"
    WORKER = "WORKER"


@dataclass(frozen=True, slots=True)
class SalesMetrics:
    total_sales: Decimal
    sale_record_count: int
    positive_sale_record_count: int
    zero_total_record_count: int



@dataclass(frozen=True, slots=True)
class DailySalesTotal:
    sale_date: date
    metrics: SalesMetrics


@dataclass(frozen=True, slots=True)
class BrandSalesTotal:
    brand_id: int
    metrics: SalesMetrics


@dataclass(frozen=True, slots=True)
class TruckSalesTotal:
    truck_id: int
    metrics: SalesMetrics


@dataclass(frozen=True, slots=True)
class WorkerSalesTotal:
    worker_id: int
    metrics: SalesMetrics


@dataclass(frozen=True, slots=True)
class BrandVanClientSalesTotal:
    brand_id: int
    van: str
    van_normalized: str
    client: str
    client_normalized: str
    metrics: SalesMetrics


@dataclass(frozen=True, slots=True)
class BrandClientSalesTotal:
    brand_id: int
    client: str
    client_normalized: str
    metrics: SalesMetrics


@dataclass(frozen=True, slots=True)
class BrandTruckSalesTotal:
    brand_id: int
    truck_id: int
    metrics: SalesMetrics


@dataclass(frozen=True, slots=True)
class BrandWorkerSalesTotal:
    brand_id: int
    worker_id: int
    metrics: SalesMetrics


@dataclass(frozen=True, slots=True)
class BrandTruckWorkerSalesTotal:
    brand_id: int
    truck_id: int
    worker_id: int
    metrics: SalesMetrics


@dataclass(frozen=True, slots=True)
class DailyBrandTruckWorkerSalesTotal:
    sale_date: date
    brand_id: int
    truck_id: int
    worker_id: int
    metrics: SalesMetrics


@dataclass(frozen=True, slots=True)
class SalesAttributionIssue:
    stage: SalesAttributionStage
    code: str
    import_row_id: int
    batch_id: int
    excel_row_number: int
    brand_id: int
    normalized_van: str
    total: Decimal
    matching_entity_ids: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class SalesAggregationResult:
    requested_period_start: date | None
    requested_period_end: date | None
    source_row_count: int
    included_row_count: int
    outside_requested_period_count: int
    overall: SalesMetrics
    by_brand: tuple[BrandSalesTotal, ...]
    by_truck: tuple[TruckSalesTotal, ...]
    by_worker: tuple[WorkerSalesTotal, ...]
    by_brand_truck: tuple[BrandTruckSalesTotal, ...]
    by_brand_worker: tuple[BrandWorkerSalesTotal, ...]
    by_brand_truck_worker: tuple[
        BrandTruckWorkerSalesTotal,
        ...,
    ]
    attribution_issues: tuple[SalesAttributionIssue, ...]
    by_date: tuple[DailySalesTotal, ...] = ()
    by_date_brand_truck_worker: tuple[
        DailyBrandTruckWorkerSalesTotal,
        ...,
    ] = ()
    by_brand_client: tuple[
        BrandClientSalesTotal,
        ...,
    ] = ()
    by_brand_van_client: tuple[
        BrandVanClientSalesTotal,
        ...,
    ] = ()

    @property
    def has_attribution_issues(self) -> bool:
        return bool(self.attribution_issues)


@dataclass(slots=True)
class _SalesAccumulator:
    total_sales: Decimal = field(
        default_factory=lambda: Decimal("0")
    )
    sale_record_count: int = 0
    positive_sale_record_count: int = 0
    zero_total_record_count: int = 0

    def add(self, total: Decimal) -> None:
        self.total_sales += total
        self.sale_record_count += 1

        if total > 0:
            self.positive_sale_record_count += 1
        else:
            self.zero_total_record_count += 1

    def freeze(self) -> SalesMetrics:
        return SalesMetrics(
            total_sales=self.total_sales,
            sale_record_count=self.sale_record_count,
            positive_sale_record_count=(
                self.positive_sale_record_count
            ),
            zero_total_record_count=(
                self.zero_total_record_count
            ),
        )


@dataclass(slots=True)
class _NamedSalesAccumulator:
    display_name: str
    accumulator: _SalesAccumulator = field(
        default_factory=_SalesAccumulator
    )


def _get_accumulator(
    buckets: dict,
    key,
) -> _SalesAccumulator:
    accumulator = buckets.get(key)

    if accumulator is None:
        accumulator = _SalesAccumulator()
        buckets[key] = accumulator

    return accumulator


def _get_named_accumulator(
    buckets: dict,
    key,
    display_name: str,
) -> _NamedSalesAccumulator:
    value = buckets.get(key)

    if value is None:
        value = _NamedSalesAccumulator(
            display_name=display_name,
        )
        buckets[key] = value

    return value


def aggregate_sales(
    *,
    period_start: date | None = None,
    period_end: date | None = None,
    brand_id: int | None = None,
    rows: Iterable[ImportRow] | None = None,
    truck_index: TruckCodeIndex | None = None,
    assignment_index: AssignmentIndex | None = None,
) -> SalesAggregationResult:
    """
    Aggregate approved and accepted SALES rows.

    Batch overlap filters reduce the source query, while exact
    sale dates determine whether a row belongs to the requested
    analytical period.
    """
    if (
        period_start is not None
        and period_end is not None
        and period_end < period_start
    ):
        raise ValueError(
            "period_end cannot be before period_start."
        )

    if rows is None:
        rows = get_approved_calculation_rows(
            report_type=ImportReportType.SALES,
            brand_id=brand_id,
            period_start=period_start,
            period_end=period_end,
        )

    if truck_index is None:
        truck_index = build_truck_code_index()

    if assignment_index is None:
        assignment_index = build_assignment_index()

    overall = _SalesAccumulator()

    brand_buckets: dict[int, _SalesAccumulator] = {}
    brand_van_client_buckets: dict[
        tuple[int, str, str],
        _NamedSalesAccumulator,
    ] = {}

    brand_client_buckets: dict[
        tuple[int, str],
        _NamedSalesAccumulator,
    ] = {}
    date_buckets: dict[date, _SalesAccumulator] = {}
    truck_buckets: dict[int, _SalesAccumulator] = {}
    worker_buckets: dict[int, _SalesAccumulator] = {}

    brand_truck_buckets: dict[
        tuple[int, int],
        _SalesAccumulator,
    ] = {}
    brand_worker_buckets: dict[
        tuple[int, int],
        _SalesAccumulator,
    ] = {}
    brand_truck_worker_buckets: dict[
        tuple[int, int, int],
        _SalesAccumulator,
    ] = {}
    date_brand_truck_worker_buckets: dict[
        tuple[date, int, int, int],
        _SalesAccumulator,
    ] = {}

    issues: list[SalesAttributionIssue] = []

    source_row_count = 0
    outside_requested_period_count = 0

    for import_row in rows:
        source_row_count += 1
        sale = parse_sales_row(import_row)
        sale_date = sale.sale_datetime.date()

        if (
            period_start is not None
            and sale_date < period_start
        ):
            outside_requested_period_count += 1
            continue

        if (
            period_end is not None
            and sale_date > period_end
        ):
            outside_requested_period_count += 1
            continue

        overall.add(sale.total)

        _get_accumulator(
            date_buckets,
            sale_date,
        ).add(sale.total)

        _get_accumulator(
            brand_buckets,
            sale.brand_id,
        ).add(sale.total)

        brand_van_client = _get_named_accumulator(
            brand_van_client_buckets,
            (
                sale.brand_id,
                sale.van_normalized,
                sale.client_normalized,
            ),
            sale.client,
        )
        brand_van_client.accumulator.add(
            sale.total
        )

        brand_client = _get_named_accumulator(
            brand_client_buckets,
            (
                sale.brand_id,
                sale.client_normalized,
            ),
            sale.client,
        )
        brand_client.accumulator.add(
            sale.total
        )

        truck_resolution = resolve_truck_by_van(
            sale.van_normalized,
            truck_index=truck_index,
        )

        if not truck_resolution.is_matched:
            issues.append(
                SalesAttributionIssue(
                    stage=SalesAttributionStage.TRUCK,
                    code=truck_resolution.status.value,
                    import_row_id=sale.import_row_id,
                    batch_id=sale.batch_id,
                    excel_row_number=sale.excel_row_number,
                    brand_id=sale.brand_id,
                    normalized_van=sale.van_normalized,
                    total=sale.total,
                    matching_entity_ids=(
                        truck_resolution.matching_truck_ids
                    ),
                )
            )
            continue

        truck = truck_resolution.truck
        truck_id = truck.pk

        _get_accumulator(
            truck_buckets,
            truck_id,
        ).add(sale.total)

        _get_accumulator(
            brand_truck_buckets,
            (
                sale.brand_id,
                truck_id,
            ),
        ).add(sale.total)

        assignment_resolution = resolve_worker_for_date(
            truck,
            sale_date,
            assignment_index=assignment_index,
        )

        if not assignment_resolution.is_matched:
            issues.append(
                SalesAttributionIssue(
                    stage=SalesAttributionStage.WORKER,
                    code=assignment_resolution.status.value,
                    import_row_id=sale.import_row_id,
                    batch_id=sale.batch_id,
                    excel_row_number=sale.excel_row_number,
                    brand_id=sale.brand_id,
                    normalized_van=sale.van_normalized,
                    total=sale.total,
                    matching_entity_ids=(
                        assignment_resolution
                        .matching_assignment_ids
                    ),
                )
            )
            continue

        worker_id = assignment_resolution.worker.pk

        _get_accumulator(
            worker_buckets,
            worker_id,
        ).add(sale.total)

        _get_accumulator(
            brand_worker_buckets,
            (
                sale.brand_id,
                worker_id,
            ),
        ).add(sale.total)

        _get_accumulator(
            brand_truck_worker_buckets,
            (
                sale.brand_id,
                truck_id,
                worker_id,
            ),
        ).add(sale.total)

        _get_accumulator(
            date_brand_truck_worker_buckets,
            (
                sale_date,
                sale.brand_id,
                truck_id,
                worker_id,
            ),
        ).add(sale.total)

    return SalesAggregationResult(
        requested_period_start=period_start,
        requested_period_end=period_end,
        source_row_count=source_row_count,
        included_row_count=overall.sale_record_count,
        outside_requested_period_count=(
            outside_requested_period_count
        ),
        overall=overall.freeze(),
        by_brand=tuple(
            BrandSalesTotal(
                brand_id=key,
                metrics=value.freeze(),
            )
            for key, value in sorted(
                brand_buckets.items()
            )
        ),
        by_brand_van_client=tuple(
            BrandVanClientSalesTotal(
                brand_id=key[0],
                van=key[1],
                van_normalized=key[1],
                client=value.display_name,
                client_normalized=key[2],
                metrics=value.accumulator.freeze(),
            )
            for key, value in sorted(
                brand_van_client_buckets.items()
            )
        ),
        by_brand_client=tuple(
            BrandClientSalesTotal(
                brand_id=key[0],
                client=value.display_name,
                client_normalized=key[1],
                metrics=value.accumulator.freeze(),
            )
            for key, value in sorted(
                brand_client_buckets.items()
            )
        ),
        by_truck=tuple(
            TruckSalesTotal(
                truck_id=key,
                metrics=value.freeze(),
            )
            for key, value in sorted(
                truck_buckets.items()
            )
        ),
        by_worker=tuple(
            WorkerSalesTotal(
                worker_id=key,
                metrics=value.freeze(),
            )
            for key, value in sorted(
                worker_buckets.items()
            )
        ),
        by_brand_truck=tuple(
            BrandTruckSalesTotal(
                brand_id=key[0],
                truck_id=key[1],
                metrics=value.freeze(),
            )
            for key, value in sorted(
                brand_truck_buckets.items()
            )
        ),
        by_brand_worker=tuple(
            BrandWorkerSalesTotal(
                brand_id=key[0],
                worker_id=key[1],
                metrics=value.freeze(),
            )
            for key, value in sorted(
                brand_worker_buckets.items()
            )
        ),
        by_brand_truck_worker=tuple(
            BrandTruckWorkerSalesTotal(
                brand_id=key[0],
                truck_id=key[1],
                worker_id=key[2],
                metrics=value.freeze(),
            )
            for key, value in sorted(
                brand_truck_worker_buckets.items()
            )
        ),
        attribution_issues=tuple(issues),
        by_date=tuple(
            DailySalesTotal(
                sale_date=key,
                metrics=value.freeze(),
            )
            for key, value in sorted(
                date_buckets.items()
            )
        ),
        by_date_brand_truck_worker=tuple(
            DailyBrandTruckWorkerSalesTotal(
                sale_date=key[0],
                brand_id=key[1],
                truck_id=key[2],
                worker_id=key[3],
                metrics=value.freeze(),
            )
            for key, value in sorted(
                date_brand_truck_worker_buckets.items()
            )
        ),
    )
