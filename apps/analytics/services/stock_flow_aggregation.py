from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Iterable

from apps.imports.models import ImportReportType, ImportRow

from .approved_data_source import (
    get_approved_calculation_rows,
)
from .assignment_resolver import (
    AssignmentIndex,
    build_assignment_index,
    resolve_worker_for_period,
)
from .report_rows import (
    parse_chargement_row,
    parse_opening_stock_row,
)
from .truck_resolver import (
    TruckCodeIndex,
    build_truck_code_index,
    resolve_truck_by_van,
)


SUPPORTED_STOCK_FLOW_REPORT_TYPES = {
    ImportReportType.OPENING_STOCK,
    ImportReportType.CHARGEMENT,
}


class StockFlowAttributionStage(StrEnum):
    TRUCK = "TRUCK"
    WORKER = "WORKER"


class StockFlowPeriodStatus(StrEnum):
    INCLUDED = "INCLUDED"
    OUTSIDE = "OUTSIDE"
    PARTIAL_OVERLAP = "PARTIAL_OVERLAP"


@dataclass(frozen=True, slots=True)
class QuantityMetrics:
    total_quantity: Decimal
    record_count: int
    positive_quantity_record_count: int
    zero_quantity_record_count: int


@dataclass(frozen=True, slots=True)
class BrandQuantityTotal:
    brand_id: int
    metrics: QuantityMetrics


@dataclass(frozen=True, slots=True)
class TruckQuantityTotal:
    truck_id: int
    metrics: QuantityMetrics


@dataclass(frozen=True, slots=True)
class WorkerQuantityTotal:
    worker_id: int
    metrics: QuantityMetrics


@dataclass(frozen=True, slots=True)
class BrandProductQuantityTotal:
    brand_id: int
    article: str
    article_normalized: str
    metrics: QuantityMetrics


@dataclass(frozen=True, slots=True)
class BrandTruckProductQuantityTotal:
    brand_id: int
    truck_id: int
    article: str
    article_normalized: str
    metrics: QuantityMetrics


@dataclass(frozen=True, slots=True)
class BrandWorkerProductQuantityTotal:
    brand_id: int
    worker_id: int
    article: str
    article_normalized: str
    metrics: QuantityMetrics


@dataclass(frozen=True, slots=True)
class StockFlowAttributionIssue:
    stage: StockFlowAttributionStage
    code: str
    import_row_id: int
    batch_id: int
    excel_row_number: int
    brand_id: int
    normalized_van: str
    period_start: date
    period_end: date
    quantity: Decimal
    matching_entity_ids: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class StockFlowAggregationResult:
    report_type: str
    requested_period_start: date | None
    requested_period_end: date | None
    source_row_count: int
    included_row_count: int
    outside_requested_period_count: int
    partial_overlap_excluded_count: int
    overall: QuantityMetrics
    by_brand: tuple[BrandQuantityTotal, ...]
    by_truck: tuple[TruckQuantityTotal, ...]
    by_worker: tuple[WorkerQuantityTotal, ...]
    by_brand_product: tuple[
        BrandProductQuantityTotal,
        ...,
    ]
    by_brand_truck_product: tuple[
        BrandTruckProductQuantityTotal,
        ...,
    ]
    by_brand_worker_product: tuple[
        BrandWorkerProductQuantityTotal,
        ...,
    ]
    attribution_issues: tuple[
        StockFlowAttributionIssue,
        ...,
    ]

    @property
    def has_attribution_issues(self) -> bool:
        return bool(self.attribution_issues)

    @property
    def has_partial_period_data(self) -> bool:
        return self.partial_overlap_excluded_count > 0


@dataclass(slots=True)
class _QuantityAccumulator:
    total_quantity: Decimal = field(
        default_factory=lambda: Decimal("0")
    )
    record_count: int = 0
    positive_quantity_record_count: int = 0
    zero_quantity_record_count: int = 0

    def add(self, quantity: Decimal) -> None:
        self.total_quantity += quantity
        self.record_count += 1

        if quantity > 0:
            self.positive_quantity_record_count += 1
        else:
            self.zero_quantity_record_count += 1

    def freeze(self) -> QuantityMetrics:
        return QuantityMetrics(
            total_quantity=self.total_quantity,
            record_count=self.record_count,
            positive_quantity_record_count=(
                self.positive_quantity_record_count
            ),
            zero_quantity_record_count=(
                self.zero_quantity_record_count
            ),
        )


@dataclass(slots=True)
class _NamedQuantityAccumulator:
    display_name: str
    accumulator: _QuantityAccumulator = field(
        default_factory=_QuantityAccumulator
    )


def _get_accumulator(
    buckets: dict,
    key,
) -> _QuantityAccumulator:
    accumulator = buckets.get(key)

    if accumulator is None:
        accumulator = _QuantityAccumulator()
        buckets[key] = accumulator

    return accumulator


def _get_named_accumulator(
    buckets: dict,
    key,
    display_name: str,
) -> _NamedQuantityAccumulator:
    named = buckets.get(key)

    if named is None:
        named = _NamedQuantityAccumulator(
            display_name=display_name,
        )
        buckets[key] = named

    return named


def _period_status(
    *,
    batch_period_start: date,
    batch_period_end: date,
    requested_period_start: date | None,
    requested_period_end: date | None,
) -> StockFlowPeriodStatus:
    if (
        requested_period_start is not None
        and batch_period_end < requested_period_start
    ):
        return StockFlowPeriodStatus.OUTSIDE

    if (
        requested_period_end is not None
        and batch_period_start > requested_period_end
    ):
        return StockFlowPeriodStatus.OUTSIDE

    if (
        requested_period_start is not None
        and batch_period_start < requested_period_start
    ):
        return StockFlowPeriodStatus.PARTIAL_OVERLAP

    if (
        requested_period_end is not None
        and batch_period_end > requested_period_end
    ):
        return StockFlowPeriodStatus.PARTIAL_OVERLAP

    return StockFlowPeriodStatus.INCLUDED


def _parse_stock_flow_row(
    row: ImportRow,
    report_type: str,
):
    if report_type == ImportReportType.OPENING_STOCK:
        return parse_opening_stock_row(row)

    if report_type == ImportReportType.CHARGEMENT:
        return parse_chargement_row(row)

    raise ValueError(
        f"Unsupported stock-flow report type: {report_type}"
    )


def aggregate_stock_flow(
    report_type: str,
    *,
    period_start: date | None = None,
    period_end: date | None = None,
    brand_id: int | None = None,
    rows: Iterable[ImportRow] | None = None,
    truck_index: TruckCodeIndex | None = None,
    assignment_index: AssignmentIndex | None = None,
) -> StockFlowAggregationResult:
    """
    Aggregate OPENING_STOCK or CHARGEMENT quantities.

    These reports have batch-level temporal precision. A row is
    included only when its complete batch period is contained in
    the requested analytical period. Partial overlaps are never
    apportioned across invented dates.
    """
    if report_type not in SUPPORTED_STOCK_FLOW_REPORT_TYPES:
        raise ValueError(
            f"Unsupported stock-flow report type: {report_type}"
        )

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
            report_type=report_type,
            brand_id=brand_id,
            period_start=period_start,
            period_end=period_end,
        )

    if truck_index is None:
        truck_index = build_truck_code_index()

    if assignment_index is None:
        assignment_index = build_assignment_index()

    overall = _QuantityAccumulator()

    brand_buckets: dict[
        int,
        _QuantityAccumulator,
    ] = {}
    truck_buckets: dict[
        int,
        _QuantityAccumulator,
    ] = {}
    worker_buckets: dict[
        int,
        _QuantityAccumulator,
    ] = {}

    brand_product_buckets: dict[
        tuple[int, str],
        _NamedQuantityAccumulator,
    ] = {}

    brand_truck_product_buckets: dict[
        tuple[int, int, str],
        _NamedQuantityAccumulator,
    ] = {}

    brand_worker_product_buckets: dict[
        tuple[int, int, str],
        _NamedQuantityAccumulator,
    ] = {}

    issues: list[StockFlowAttributionIssue] = []

    source_row_count = 0
    outside_requested_period_count = 0
    partial_overlap_excluded_count = 0

    for import_row in rows:
        source_row_count += 1

        analytical_row = _parse_stock_flow_row(
            import_row,
            report_type,
        )

        period_status = _period_status(
            batch_period_start=(
                analytical_row.period_start
            ),
            batch_period_end=(
                analytical_row.period_end
            ),
            requested_period_start=period_start,
            requested_period_end=period_end,
        )

        if period_status == StockFlowPeriodStatus.OUTSIDE:
            outside_requested_period_count += 1
            continue

        if (
            period_status
            == StockFlowPeriodStatus.PARTIAL_OVERLAP
        ):
            partial_overlap_excluded_count += 1
            continue

        quantity = analytical_row.quantity

        overall.add(quantity)

        _get_accumulator(
            brand_buckets,
            analytical_row.brand_id,
        ).add(quantity)

        brand_product = _get_named_accumulator(
            brand_product_buckets,
            (
                analytical_row.brand_id,
                analytical_row.article_normalized,
            ),
            analytical_row.article,
        )
        brand_product.accumulator.add(quantity)

        truck_resolution = resolve_truck_by_van(
            analytical_row.van_normalized,
            truck_index=truck_index,
        )

        if not truck_resolution.is_matched:
            issues.append(
                StockFlowAttributionIssue(
                    stage=StockFlowAttributionStage.TRUCK,
                    code=truck_resolution.status.value,
                    import_row_id=(
                        analytical_row.import_row_id
                    ),
                    batch_id=analytical_row.batch_id,
                    excel_row_number=(
                        analytical_row.excel_row_number
                    ),
                    brand_id=analytical_row.brand_id,
                    normalized_van=(
                        analytical_row.van_normalized
                    ),
                    period_start=(
                        analytical_row.period_start
                    ),
                    period_end=(
                        analytical_row.period_end
                    ),
                    quantity=quantity,
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
        ).add(quantity)

        truck_product = _get_named_accumulator(
            brand_truck_product_buckets,
            (
                analytical_row.brand_id,
                truck_id,
                analytical_row.article_normalized,
            ),
            analytical_row.article,
        )
        truck_product.accumulator.add(quantity)

        assignment_resolution = resolve_worker_for_period(
            truck,
            analytical_row.period_start,
            analytical_row.period_end,
            assignment_index=assignment_index,
        )

        if not assignment_resolution.is_matched:
            issues.append(
                StockFlowAttributionIssue(
                    stage=StockFlowAttributionStage.WORKER,
                    code=assignment_resolution.status.value,
                    import_row_id=(
                        analytical_row.import_row_id
                    ),
                    batch_id=analytical_row.batch_id,
                    excel_row_number=(
                        analytical_row.excel_row_number
                    ),
                    brand_id=analytical_row.brand_id,
                    normalized_van=(
                        analytical_row.van_normalized
                    ),
                    period_start=(
                        analytical_row.period_start
                    ),
                    period_end=(
                        analytical_row.period_end
                    ),
                    quantity=quantity,
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
        ).add(quantity)

        worker_product = _get_named_accumulator(
            brand_worker_product_buckets,
            (
                analytical_row.brand_id,
                worker_id,
                analytical_row.article_normalized,
            ),
            analytical_row.article,
        )
        worker_product.accumulator.add(quantity)

    return StockFlowAggregationResult(
        report_type=report_type,
        requested_period_start=period_start,
        requested_period_end=period_end,
        source_row_count=source_row_count,
        included_row_count=overall.record_count,
        outside_requested_period_count=(
            outside_requested_period_count
        ),
        partial_overlap_excluded_count=(
            partial_overlap_excluded_count
        ),
        overall=overall.freeze(),
        by_brand=tuple(
            BrandQuantityTotal(
                brand_id=key,
                metrics=value.freeze(),
            )
            for key, value in sorted(
                brand_buckets.items()
            )
        ),
        by_truck=tuple(
            TruckQuantityTotal(
                truck_id=key,
                metrics=value.freeze(),
            )
            for key, value in sorted(
                truck_buckets.items()
            )
        ),
        by_worker=tuple(
            WorkerQuantityTotal(
                worker_id=key,
                metrics=value.freeze(),
            )
            for key, value in sorted(
                worker_buckets.items()
            )
        ),
        by_brand_product=tuple(
            BrandProductQuantityTotal(
                brand_id=key[0],
                article=value.display_name,
                article_normalized=key[1],
                metrics=value.accumulator.freeze(),
            )
            for key, value in sorted(
                brand_product_buckets.items()
            )
        ),
        by_brand_truck_product=tuple(
            BrandTruckProductQuantityTotal(
                brand_id=key[0],
                truck_id=key[1],
                article=value.display_name,
                article_normalized=key[2],
                metrics=value.accumulator.freeze(),
            )
            for key, value in sorted(
                brand_truck_product_buckets.items()
            )
        ),
        by_brand_worker_product=tuple(
            BrandWorkerProductQuantityTotal(
                brand_id=key[0],
                worker_id=key[1],
                article=value.display_name,
                article_normalized=key[2],
                metrics=value.accumulator.freeze(),
            )
            for key, value in sorted(
                brand_worker_product_buckets.items()
            )
        ),
        attribution_issues=tuple(issues),
    )


def aggregate_opening_stock(
    **kwargs,
) -> StockFlowAggregationResult:
    return aggregate_stock_flow(
        ImportReportType.OPENING_STOCK,
        **kwargs,
    )


def aggregate_chargement(
    **kwargs,
) -> StockFlowAggregationResult:
    return aggregate_stock_flow(
        ImportReportType.CHARGEMENT,
        **kwargs,
    )
