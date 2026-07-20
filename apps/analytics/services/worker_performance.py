from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .pos_visit_aggregation import (
    PosVisitAggregationResult,
    aggregate_pos_visits,
)
from .product_performance import (
    ProductPerformanceResult,
    calculate_product_performance,
)
from .sales_aggregation import (
    SalesAggregationResult,
    aggregate_sales,
)
from .truck_operational_status import (
    BrandTruckOperationalState,
    TruckOperationalStatus,
    TruckOperationalStatusResult,
    determine_truck_operational_status,
)


@dataclass(frozen=True, slots=True)
class WorkerPerformanceKpi:
    worker_id: int

    total_sales: Decimal
    sale_record_count: int
    positive_sale_record_count: int
    zero_total_record_count: int

    pos_record_count: int
    visited_record_count: int
    not_visited_record_count: int
    unique_client_day_count: int
    distinct_brand_client_count: int

    brand_product_count: int
    sold_product_count: int
    not_sold_product_count: int
    negative_gap_product_count: int
    sold_without_supply_context_count: int

    @property
    def has_sales_measurement(self) -> bool:
        return self.sale_record_count > 0

    @property
    def has_visit_measurement(self) -> bool:
        return self.pos_record_count > 0

    @property
    def has_product_measurement(self) -> bool:
        return self.brand_product_count > 0

    @property
    def has_any_measurement(self) -> bool:
        return (
            self.has_sales_measurement
            or self.has_visit_measurement
            or self.has_product_measurement
        )

    @property
    def average_sale_value(self) -> Decimal | None:
        """
        Average across every accepted sale record, including
        accepted zero-total records.
        """
        if self.sale_record_count == 0:
            return None

        return (
            self.total_sales
            / Decimal(self.sale_record_count)
        )

    @property
    def average_positive_sale_value(
        self,
    ) -> Decimal | None:
        """
        Average value using only positive sale records.
        """
        if self.positive_sale_record_count == 0:
            return None

        return (
            self.total_sales
            / Decimal(
                self.positive_sale_record_count
            )
        )

    @property
    def zero_total_sale_rate(
        self,
    ) -> Decimal | None:
        if self.sale_record_count == 0:
            return None

        return (
            Decimal(self.zero_total_record_count)
            / Decimal(self.sale_record_count)
        )

    @property
    def visit_success_rate(
        self,
    ) -> Decimal | None:
        if self.pos_record_count == 0:
            return None

        return (
            Decimal(self.visited_record_count)
            / Decimal(self.pos_record_count)
        )

    @property
    def non_visit_rate(
        self,
    ) -> Decimal | None:
        if self.pos_record_count == 0:
            return None

        return (
            Decimal(self.not_visited_record_count)
            / Decimal(self.pos_record_count)
        )


@dataclass(frozen=True, slots=True)
class PerformanceDataQualitySummary:
    sales_attribution_issue_count: int
    pos_attribution_issue_count: int
    items_attribution_issue_count: int
    opening_stock_attribution_issue_count: int
    chargement_attribution_issue_count: int
    operational_attribution_issue_count: int

    pos_numeric_message_warning_count: int
    pos_duplicate_same_day_warning_count: int

    @property
    def attribution_issue_count(self) -> int:
        return (
            self.sales_attribution_issue_count
            + self.pos_attribution_issue_count
            + self.items_attribution_issue_count
            + self.opening_stock_attribution_issue_count
            + self.chargement_attribution_issue_count
            + self.operational_attribution_issue_count
        )

    @property
    def warning_count(self) -> int:
        return (
            self.pos_numeric_message_warning_count
            + self.pos_duplicate_same_day_warning_count
        )

    @property
    def total_issue_and_warning_count(self) -> int:
        return (
            self.attribution_issue_count
            + self.warning_count
        )


@dataclass(frozen=True, slots=True)
class WorkerPerformanceResult:
    requested_period_start: date | None
    requested_period_end: date | None
    brand_id: int | None

    workers: tuple[WorkerPerformanceKpi, ...]

    operational_states: tuple[
        BrandTruckOperationalState,
        ...,
    ]

    data_quality: PerformanceDataQualitySummary

    @property
    def worker_count(self) -> int:
        return len(self.workers)

    @property
    def measured_sales_worker_count(self) -> int:
        return sum(
            1
            for worker in self.workers
            if worker.has_sales_measurement
        )

    @property
    def workers_without_sales_measurement(
        self,
    ) -> tuple[WorkerPerformanceKpi, ...]:
        """
        These workers are not labelled as failures.

        They simply have no measurable accepted SALES records in
        the selected analytical period.
        """
        return tuple(
            worker
            for worker in self.workers
            if not worker.has_sales_measurement
        )

    @property
    def confirmed_stopped_trucks(
        self,
    ) -> tuple[BrandTruckOperationalState, ...]:
        return tuple(
            state
            for state in self.operational_states
            if (
                state.status
                == TruckOperationalStatus.CONFIRMED_STOPPED
            )
        )

    @property
    def possible_stopped_trucks(
        self,
    ) -> tuple[BrandTruckOperationalState, ...]:
        return tuple(
            state
            for state in self.operational_states
            if (
                state.status
                == TruckOperationalStatus.POSSIBLE_STOPPED
            )
        )

    @property
    def conflicting_truck_states(
        self,
    ) -> tuple[BrandTruckOperationalState, ...]:
        return tuple(
            state
            for state in self.operational_states
            if (
                state.status
                == TruckOperationalStatus.CONFLICTING_EVIDENCE
            )
        )

    def top_sales_workers(
        self,
        limit: int = 10,
    ) -> tuple[WorkerPerformanceKpi, ...]:
        _validate_limit(limit)

        ranked = sorted(
            (
                worker
                for worker in self.workers
                if worker.has_sales_measurement
            ),
            key=lambda worker: (
                -worker.total_sales,
                -worker.positive_sale_record_count,
                worker.worker_id,
            ),
        )

        return tuple(ranked[:limit])

    def lowest_sales_workers(
        self,
        limit: int = 10,
    ) -> tuple[WorkerPerformanceKpi, ...]:
        """
        Rank only workers with measurable SALES records.

        Workers with no sales measurement are deliberately
        excluded instead of being labelled as the weakest.
        """
        _validate_limit(limit)

        ranked = sorted(
            (
                worker
                for worker in self.workers
                if worker.has_sales_measurement
            ),
            key=lambda worker: (
                worker.total_sales,
                worker.positive_sale_record_count,
                worker.worker_id,
            ),
        )

        return tuple(ranked[:limit])

    def highest_non_visit_rate_workers(
        self,
        limit: int = 10,
        *,
        minimum_pos_records: int = 1,
    ) -> tuple[WorkerPerformanceKpi, ...]:
        _validate_limit(limit)
        _validate_minimum_records(
            minimum_pos_records
        )

        ranked = sorted(
            (
                worker
                for worker in self.workers
                if (
                    worker.pos_record_count
                    >= minimum_pos_records
                )
            ),
            key=lambda worker: (
                -worker.non_visit_rate,
                -worker.not_visited_record_count,
                -worker.pos_record_count,
                worker.worker_id,
            ),
        )

        return tuple(ranked[:limit])

    def most_not_sold_products_workers(
        self,
        limit: int = 10,
    ) -> tuple[WorkerPerformanceKpi, ...]:
        _validate_limit(limit)

        ranked = sorted(
            (
                worker
                for worker in self.workers
                if worker.has_product_measurement
            ),
            key=lambda worker: (
                -worker.not_sold_product_count,
                -worker.brand_product_count,
                worker.worker_id,
            ),
        )

        return tuple(ranked[:limit])

    def most_negative_gap_products_workers(
        self,
        limit: int = 10,
    ) -> tuple[WorkerPerformanceKpi, ...]:
        """
        This is a data/stock-context warning ranking, not a sales
        performance failure ranking.
        """
        _validate_limit(limit)

        ranked = sorted(
            (
                worker
                for worker in self.workers
                if worker.has_product_measurement
            ),
            key=lambda worker: (
                -worker.negative_gap_product_count,
                -worker.sold_without_supply_context_count,
                worker.worker_id,
            ),
        )

        return tuple(ranked[:limit])


@dataclass(slots=True)
class _WorkerAccumulator:
    total_sales: Decimal = field(
        default_factory=lambda: Decimal("0")
    )
    sale_record_count: int = 0
    positive_sale_record_count: int = 0
    zero_total_record_count: int = 0

    pos_record_count: int = 0
    visited_record_count: int = 0
    not_visited_record_count: int = 0
    unique_client_day_count: int = 0

    distinct_brand_clients: set[
        tuple[int, str]
    ] = field(default_factory=set)

    brand_products: set[
        tuple[int, str]
    ] = field(default_factory=set)

    sold_products: set[
        tuple[int, str]
    ] = field(default_factory=set)

    not_sold_products: set[
        tuple[int, str]
    ] = field(default_factory=set)

    negative_gap_products: set[
        tuple[int, str]
    ] = field(default_factory=set)

    sold_without_supply_products: set[
        tuple[int, str]
    ] = field(default_factory=set)

    def freeze(
        self,
        worker_id: int,
    ) -> WorkerPerformanceKpi:
        return WorkerPerformanceKpi(
            worker_id=worker_id,
            total_sales=self.total_sales,
            sale_record_count=(
                self.sale_record_count
            ),
            positive_sale_record_count=(
                self.positive_sale_record_count
            ),
            zero_total_record_count=(
                self.zero_total_record_count
            ),
            pos_record_count=self.pos_record_count,
            visited_record_count=(
                self.visited_record_count
            ),
            not_visited_record_count=(
                self.not_visited_record_count
            ),
            unique_client_day_count=(
                self.unique_client_day_count
            ),
            distinct_brand_client_count=len(
                self.distinct_brand_clients
            ),
            brand_product_count=len(
                self.brand_products
            ),
            sold_product_count=len(
                self.sold_products
            ),
            not_sold_product_count=len(
                self.not_sold_products
            ),
            negative_gap_product_count=len(
                self.negative_gap_products
            ),
            sold_without_supply_context_count=len(
                self.sold_without_supply_products
            ),
        )


def _validate_limit(limit: int) -> None:
    if limit < 0:
        raise ValueError(
            "limit cannot be negative."
        )


def _validate_minimum_records(
    minimum_records: int,
) -> None:
    if minimum_records < 1:
        raise ValueError(
            "minimum_pos_records must be at least 1."
        )


def _get_worker_accumulator(
    buckets: dict[int, _WorkerAccumulator],
    worker_id: int,
) -> _WorkerAccumulator:
    accumulator = buckets.get(worker_id)

    if accumulator is None:
        accumulator = _WorkerAccumulator()
        buckets[worker_id] = accumulator

    return accumulator


def _validate_periods(
    *,
    sales_result: SalesAggregationResult,
    pos_result: PosVisitAggregationResult,
    product_result: ProductPerformanceResult,
    operational_result: TruckOperationalStatusResult,
) -> tuple[date | None, date | None]:
    expected_period = (
        sales_result.requested_period_start,
        sales_result.requested_period_end,
    )

    source_periods = (
        (
            pos_result.requested_period_start,
            pos_result.requested_period_end,
        ),
        (
            product_result.requested_period_start,
            product_result.requested_period_end,
        ),
        (
            operational_result.requested_period_start,
            operational_result.requested_period_end,
        ),
    )

    if any(
        period != expected_period
        for period in source_periods
    ):
        raise ValueError(
            "All performance sources must use the same "
            "requested period."
        )

    return expected_period


def combine_worker_performance(
    *,
    sales_result: SalesAggregationResult,
    pos_result: PosVisitAggregationResult,
    product_result: ProductPerformanceResult,
    operational_result: TruckOperationalStatusResult,
    brand_id: int | None = None,
) -> WorkerPerformanceResult:
    """
    Combine worker KPIs without inventing an arbitrary score.

    Each metric remains separately visible so that management can
    understand whether attention is caused by sales, visits,
    unsold products or data-quality limitations.
    """
    period_start, period_end = _validate_periods(
        sales_result=sales_result,
        pos_result=pos_result,
        product_result=product_result,
        operational_result=operational_result,
    )

    worker_buckets: dict[
        int,
        _WorkerAccumulator,
    ] = {}

    for item in sales_result.by_worker:
        accumulator = _get_worker_accumulator(
            worker_buckets,
            item.worker_id,
        )

        accumulator.total_sales += (
            item.metrics.total_sales
        )
        accumulator.sale_record_count += (
            item.metrics.sale_record_count
        )
        accumulator.positive_sale_record_count += (
            item.metrics
            .positive_sale_record_count
        )
        accumulator.zero_total_record_count += (
            item.metrics.zero_total_record_count
        )

    for item in pos_result.by_worker:
        accumulator = _get_worker_accumulator(
            worker_buckets,
            item.worker_id,
        )

        accumulator.pos_record_count += (
            item.metrics.total_record_count
        )
        accumulator.visited_record_count += (
            item.metrics.visited_record_count
        )
        accumulator.not_visited_record_count += (
            item.metrics.not_visited_record_count
        )
        accumulator.unique_client_day_count += (
            item.metrics.unique_client_day_count
        )

    for item in pos_result.by_brand_worker_client:
        accumulator = _get_worker_accumulator(
            worker_buckets,
            item.worker_id,
        )

        accumulator.distinct_brand_clients.add(
            (
                item.brand_id,
                item.client_normalized,
            )
        )

    for item in product_result.worker_products:
        accumulator = _get_worker_accumulator(
            worker_buckets,
            item.worker_id,
        )

        product_key = (
            item.brand_id,
            item.article_normalized,
        )

        accumulator.brand_products.add(
            product_key
        )

        if item.quantities.is_sold:
            accumulator.sold_products.add(
                product_key
            )

        if item.quantities.is_not_sold:
            accumulator.not_sold_products.add(
                product_key
            )

        if (
            item.quantities
            .has_negative_quantity_gap
        ):
            accumulator.negative_gap_products.add(
                product_key
            )

        if (
            item.quantities
            .is_sold_without_supply_context
        ):
            accumulator.sold_without_supply_products.add(
                product_key
            )

    workers = tuple(
        accumulator.freeze(worker_id)
        for worker_id, accumulator in sorted(
            worker_buckets.items()
        )
    )

    data_quality = PerformanceDataQualitySummary(
        sales_attribution_issue_count=len(
            sales_result.attribution_issues
        ),
        pos_attribution_issue_count=len(
            pos_result.attribution_issues
        ),
        items_attribution_issue_count=(
            product_result
            .items_attribution_issue_count
        ),
        opening_stock_attribution_issue_count=(
            product_result
            .opening_stock_attribution_issue_count
        ),
        chargement_attribution_issue_count=(
            product_result
            .chargement_attribution_issue_count
        ),
        operational_attribution_issue_count=len(
            operational_result.attribution_issues
        ),
        pos_numeric_message_warning_count=(
            pos_result.numeric_message_warning_count
        ),
        pos_duplicate_same_day_warning_count=(
            pos_result
            .duplicate_same_day_warning_count
        ),
    )

    return WorkerPerformanceResult(
        requested_period_start=period_start,
        requested_period_end=period_end,
        brand_id=brand_id,
        workers=workers,
        operational_states=(
            operational_result.states
        ),
        data_quality=data_quality,
    )


def calculate_worker_performance(
    *,
    period_start: date | None = None,
    period_end: date | None = None,
    brand_id: int | None = None,
) -> WorkerPerformanceResult:
    if (
        period_start is not None
        and period_end is not None
        and period_end < period_start
    ):
        raise ValueError(
            "period_end cannot be before period_start."
        )

    sales_result = aggregate_sales(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
    )

    pos_result = aggregate_pos_visits(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
    )

    product_result = calculate_product_performance(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
    )

    operational_result = (
        determine_truck_operational_status(
            period_start=period_start,
            period_end=period_end,
            brand_id=brand_id,
        )
    )

    return combine_worker_performance(
        sales_result=sales_result,
        pos_result=pos_result,
        product_result=product_result,
        operational_result=operational_result,
        brand_id=brand_id,
    )
