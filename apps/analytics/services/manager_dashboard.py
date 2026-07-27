from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .assignment_resolver import build_assignment_index
from .items_aggregation import (
    ItemsAggregationResult,
    aggregate_items,
)
from .pos_visit_aggregation import (
    PosVisitAggregationResult,
    aggregate_pos_visits,
)
from .product_performance import (
    ProductPerformanceResult,
    WorkerProductPerformance,
    combine_product_performance,
)
from .sales_aggregation import (
    SalesAggregationResult,
    aggregate_sales,
)
from .stock_flow_aggregation import (
    StockFlowAggregationResult,
    aggregate_chargement,
    aggregate_opening_stock,
)
from .truck_operational_status import (
    TruckOperationalStatusResult,
    determine_truck_operational_status,
)
from .truck_resolver import build_truck_code_index
from .worker_performance import (
    PerformanceDataQualitySummary,
    WorkerPerformanceKpi,
    WorkerPerformanceResult,
    combine_worker_performance,
)


@dataclass(frozen=True, slots=True)
class ManagerDashboardSummary:
    total_sales: Decimal
    sale_record_count: int
    positive_sale_record_count: int
    zero_total_record_count: int

    worker_count: int
    measured_sales_worker_count: int

    pos_record_count: int
    visited_record_count: int
    not_visited_record_count: int
    distinct_brand_client_count: int

    worker_not_sold_product_count: int
    truck_not_sold_product_count: int
    worker_negative_gap_product_count: int
    truck_negative_gap_product_count: int

    confirmed_stopped_truck_count: int
    possible_stopped_truck_count: int
    conflicting_truck_state_count: int

    @property
    def average_sale_value(self) -> Decimal | None:
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
        if self.positive_sale_record_count == 0:
            return None

        return (
            self.total_sales
            / Decimal(
                self.positive_sale_record_count
            )
        )

    @property
    def visit_success_rate(self) -> Decimal | None:
        if self.pos_record_count == 0:
            return None

        return (
            Decimal(self.visited_record_count)
            / Decimal(self.pos_record_count)
        )

    @property
    def non_visit_rate(self) -> Decimal | None:
        if self.pos_record_count == 0:
            return None

        return (
            Decimal(self.not_visited_record_count)
            / Decimal(self.pos_record_count)
        )


@dataclass(frozen=True, slots=True)
class AnalyticalCoverageSummary:
    sales_source_row_count: int
    sales_included_row_count: int
    sales_outside_period_count: int

    pos_source_row_count: int
    pos_included_row_count: int
    pos_outside_period_count: int

    items_source_row_count: int
    items_included_row_count: int
    items_outside_period_count: int
    items_partial_overlap_count: int

    opening_stock_source_row_count: int
    opening_stock_included_row_count: int
    opening_stock_outside_period_count: int
    opening_stock_partial_overlap_count: int

    chargement_source_row_count: int
    chargement_included_row_count: int
    chargement_outside_period_count: int
    chargement_partial_overlap_count: int

    operational_source_row_count: int
    operational_included_row_count: int
    operational_outside_period_count: int
    operational_partial_overlap_count: int

    @property
    def period_excluded_row_count(self) -> int:
        return (
            self.sales_outside_period_count
            + self.pos_outside_period_count
            + self.items_outside_period_count
            + self.items_partial_overlap_count
            + self.opening_stock_outside_period_count
            + self.opening_stock_partial_overlap_count
            + self.chargement_outside_period_count
            + self.chargement_partial_overlap_count
            + self.operational_outside_period_count
            + self.operational_partial_overlap_count
        )

    @property
    def has_partial_period_exclusions(self) -> bool:
        return (
            self.items_partial_overlap_count > 0
            or self.opening_stock_partial_overlap_count > 0
            or self.chargement_partial_overlap_count > 0
            or self.operational_partial_overlap_count > 0
        )


@dataclass(frozen=True, slots=True)
class WorkerDashboardCard:
    kpi: WorkerPerformanceKpi

    not_sold_products: tuple[
        WorkerProductPerformance,
        ...,
    ]
    least_sold_products: tuple[
        WorkerProductPerformance,
        ...,
    ]
    negative_gap_products: tuple[
        WorkerProductPerformance,
        ...,
    ]
    sold_without_supply_context_products: tuple[
        WorkerProductPerformance,
        ...,
    ]

    @property
    def worker_id(self) -> int:
        return self.kpi.worker_id

    @property
    def has_product_attention_items(self) -> bool:
        return bool(
            self.not_sold_products
            or self.negative_gap_products
            or self.sold_without_supply_context_products
        )

    @property
    def has_non_visit_attention(self) -> bool:
        return self.kpi.not_visited_record_count > 0

    @property
    def has_sales_measurement(self) -> bool:
        return self.kpi.has_sales_measurement


@dataclass(frozen=True, slots=True)
class ManagerDashboardResult:
    requested_period_start: date | None
    requested_period_end: date | None
    brand_id: int | None

    summary: ManagerDashboardSummary
    coverage: AnalyticalCoverageSummary
    data_quality: PerformanceDataQualitySummary

    worker_cards: tuple[
        WorkerDashboardCard,
        ...,
    ]

    sales: SalesAggregationResult
    visits: PosVisitAggregationResult
    products: ProductPerformanceResult
    operational: TruckOperationalStatusResult
    worker_performance: WorkerPerformanceResult

    def worker_card(
        self,
        worker_id: int,
    ) -> WorkerDashboardCard | None:
        for card in self.worker_cards:
            if card.worker_id == worker_id:
                return card

        return None

    def top_sales_workers(
        self,
        limit: int = 10,
    ) -> tuple[WorkerPerformanceKpi, ...]:
        return self.worker_performance.top_sales_workers(
            limit
        )

    def lowest_sales_workers(
        self,
        limit: int = 10,
    ) -> tuple[WorkerPerformanceKpi, ...]:
        return (
            self.worker_performance
            .lowest_sales_workers(limit)
        )

    def highest_visit_rate_workers(
        self,
        limit: int = 10,
        *,
        minimum_pos_records: int = 1,
    ) -> tuple[WorkerPerformanceKpi, ...]:
        return (
            self.worker_performance
            .highest_visit_rate_workers(
                limit,
                minimum_pos_records=(
                    minimum_pos_records
                ),
            )
        )

    def highest_non_visit_rate_workers(
        self,
        limit: int = 10,
        *,
        minimum_pos_records: int = 1,
    ) -> tuple[WorkerPerformanceKpi, ...]:
        return (
            self.worker_performance
            .highest_non_visit_rate_workers(
                limit,
                minimum_pos_records=(
                    minimum_pos_records
                ),
            )
        )


def _validate_limit(limit: int) -> None:
    if limit < 0:
        raise ValueError(
            "product_limit cannot be negative."
        )


def _validate_periods(
    *,
    sales: SalesAggregationResult,
    visits: PosVisitAggregationResult,
    items: ItemsAggregationResult,
    opening_stock: StockFlowAggregationResult,
    chargement: StockFlowAggregationResult,
    products: ProductPerformanceResult,
    operational: TruckOperationalStatusResult,
    worker_performance: WorkerPerformanceResult,
) -> tuple[date | None, date | None]:
    expected_period = (
        sales.requested_period_start,
        sales.requested_period_end,
    )

    source_periods = (
        (
            visits.requested_period_start,
            visits.requested_period_end,
        ),
        (
            items.requested_period_start,
            items.requested_period_end,
        ),
        (
            opening_stock.requested_period_start,
            opening_stock.requested_period_end,
        ),
        (
            chargement.requested_period_start,
            chargement.requested_period_end,
        ),
        (
            products.requested_period_start,
            products.requested_period_end,
        ),
        (
            operational.requested_period_start,
            operational.requested_period_end,
        ),
        (
            worker_performance.requested_period_start,
            worker_performance.requested_period_end,
        ),
    )

    if any(
        period != expected_period
        for period in source_periods
    ):
        raise ValueError(
            "All dashboard sources must use the same "
            "requested period."
        )

    return expected_period


def _build_worker_cards(
    *,
    worker_performance: WorkerPerformanceResult,
    products: ProductPerformanceResult,
    product_limit: int,
) -> tuple[WorkerDashboardCard, ...]:
    cards: list[WorkerDashboardCard] = []

    for kpi in worker_performance.workers:
        worker_products = tuple(
            item
            for item in products.worker_products
            if item.worker_id == kpi.worker_id
        )

        negative_gap_products = tuple(
            sorted(
                (
                    item
                    for item in worker_products
                    if (
                        item.quantities
                        .has_negative_quantity_gap
                    )
                ),
                key=lambda item: (
                    item.quantities
                    .analytical_quantity_gap,
                    item.article_normalized,
                    item.brand_id,
                ),
            )[:product_limit]
        )

        sold_without_supply_products = tuple(
            sorted(
                (
                    item
                    for item in worker_products
                    if (
                        item.quantities
                        .is_sold_without_supply_context
                    )
                ),
                key=lambda item: (
                    -item.quantities.sold_quantity,
                    item.article_normalized,
                    item.brand_id,
                ),
            )[:product_limit]
        )

        cards.append(
            WorkerDashboardCard(
                kpi=kpi,
                not_sold_products=(
                    products.not_sold_for_worker(
                        kpi.worker_id,
                        product_limit,
                    )
                ),
                least_sold_products=(
                    products.least_sold_for_worker(
                        kpi.worker_id,
                        product_limit,
                    )
                ),
                negative_gap_products=(
                    negative_gap_products
                ),
                sold_without_supply_context_products=(
                    sold_without_supply_products
                ),
            )
        )

    return tuple(cards)


def combine_manager_dashboard(
    *,
    sales: SalesAggregationResult,
    visits: PosVisitAggregationResult,
    items: ItemsAggregationResult,
    opening_stock: StockFlowAggregationResult,
    chargement: StockFlowAggregationResult,
    products: ProductPerformanceResult,
    operational: TruckOperationalStatusResult,
    worker_performance: WorkerPerformanceResult,
    brand_id: int | None = None,
    product_limit: int = 10,
) -> ManagerDashboardResult:
    """
    Combine analytical services into a UI-independent read model.

    This service does not assign an arbitrary global performance
    score. Sales, visits, product weaknesses, truck status and
    data-quality limitations remain separately visible.
    """
    _validate_limit(product_limit)

    period_start, period_end = _validate_periods(
        sales=sales,
        visits=visits,
        items=items,
        opening_stock=opening_stock,
        chargement=chargement,
        products=products,
        operational=operational,
        worker_performance=worker_performance,
    )

    summary = ManagerDashboardSummary(
        total_sales=sales.overall.total_sales,
        sale_record_count=(
            sales.overall.sale_record_count
        ),
        positive_sale_record_count=(
            sales.overall
            .positive_sale_record_count
        ),
        zero_total_record_count=(
            sales.overall.zero_total_record_count
        ),
        worker_count=(
            worker_performance.worker_count
        ),
        measured_sales_worker_count=(
            worker_performance
            .measured_sales_worker_count
        ),
        pos_record_count=(
            visits.overall.total_record_count
        ),
        visited_record_count=(
            visits.overall.visited_record_count
        ),
        not_visited_record_count=(
            visits.overall
            .not_visited_record_count
        ),
        distinct_brand_client_count=len(
            visits.by_brand_client
        ),
        worker_not_sold_product_count=(
            products.worker_not_sold_count
        ),
        truck_not_sold_product_count=(
            products.truck_not_sold_count
        ),
        worker_negative_gap_product_count=(
            products.worker_negative_gap_count
        ),
        truck_negative_gap_product_count=(
            products.truck_negative_gap_count
        ),
        confirmed_stopped_truck_count=len(
            operational.confirmed_stopped
        ),
        possible_stopped_truck_count=len(
            operational.possible_stopped
        ),
        conflicting_truck_state_count=len(
            operational.conflicting
        ),
    )

    coverage = AnalyticalCoverageSummary(
        sales_source_row_count=(
            sales.source_row_count
        ),
        sales_included_row_count=(
            sales.included_row_count
        ),
        sales_outside_period_count=(
            sales.outside_requested_period_count
        ),
        pos_source_row_count=(
            visits.source_row_count
        ),
        pos_included_row_count=(
            visits.included_row_count
        ),
        pos_outside_period_count=(
            visits.outside_requested_period_count
        ),
        items_source_row_count=(
            items.source_row_count
        ),
        items_included_row_count=(
            items.included_row_count
        ),
        items_outside_period_count=(
            items.outside_requested_period_count
        ),
        items_partial_overlap_count=(
            items.partial_overlap_excluded_count
        ),
        opening_stock_source_row_count=(
            opening_stock.source_row_count
        ),
        opening_stock_included_row_count=(
            opening_stock.included_row_count
        ),
        opening_stock_outside_period_count=(
            opening_stock
            .outside_requested_period_count
        ),
        opening_stock_partial_overlap_count=(
            opening_stock
            .partial_overlap_excluded_count
        ),
        chargement_source_row_count=(
            chargement.source_row_count
        ),
        chargement_included_row_count=(
            chargement.included_row_count
        ),
        chargement_outside_period_count=(
            chargement
            .outside_requested_period_count
        ),
        chargement_partial_overlap_count=(
            chargement
            .partial_overlap_excluded_count
        ),
        operational_source_row_count=(
            operational.source_row_count
        ),
        operational_included_row_count=(
            operational
            .included_evidence_row_count
        ),
        operational_outside_period_count=(
            operational
            .outside_requested_period_count
        ),
        operational_partial_overlap_count=(
            operational
            .partial_overlap_excluded_count
        ),
    )

    worker_cards = _build_worker_cards(
        worker_performance=worker_performance,
        products=products,
        product_limit=product_limit,
    )

    return ManagerDashboardResult(
        requested_period_start=period_start,
        requested_period_end=period_end,
        brand_id=brand_id,
        summary=summary,
        coverage=coverage,
        data_quality=(
            worker_performance.data_quality
        ),
        worker_cards=worker_cards,
        sales=sales,
        visits=visits,
        products=products,
        operational=operational,
        worker_performance=worker_performance,
    )


def build_manager_dashboard(
    *,
    period_start: date | None = None,
    period_end: date | None = None,
    brand_id: int | None = None,
    product_limit: int = 10,
) -> ManagerDashboardResult:
    """
    Build the complete manager analytical read model.

    Truck and assignment indexes are created once and shared
    across all compatible analytical services.
    """
    if (
        period_start is not None
        and period_end is not None
        and period_end < period_start
    ):
        raise ValueError(
            "period_end cannot be before period_start."
        )

    _validate_limit(product_limit)

    truck_index = build_truck_code_index()
    assignment_index = build_assignment_index()

    sales = aggregate_sales(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
        truck_index=truck_index,
        assignment_index=assignment_index,
    )

    visits = aggregate_pos_visits(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
        truck_index=truck_index,
        assignment_index=assignment_index,
    )

    items = aggregate_items(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
        truck_index=truck_index,
        assignment_index=assignment_index,
    )

    opening_stock = aggregate_opening_stock(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
        truck_index=truck_index,
        assignment_index=assignment_index,
    )

    chargement = aggregate_chargement(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
        truck_index=truck_index,
        assignment_index=assignment_index,
    )

    products = combine_product_performance(
        items_result=items,
        opening_stock_result=opening_stock,
        chargement_result=chargement,
    )

    operational = determine_truck_operational_status(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
        truck_index=truck_index,
    )

    worker_performance = combine_worker_performance(
        sales_result=sales,
        pos_result=visits,
        product_result=products,
        operational_result=operational,
        brand_id=brand_id,
    )

    return combine_manager_dashboard(
        sales=sales,
        visits=visits,
        items=items,
        opening_stock=opening_stock,
        chargement=chargement,
        products=products,
        operational=operational,
        worker_performance=worker_performance,
        brand_id=brand_id,
        product_limit=product_limit,
    )
