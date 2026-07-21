from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.analytics.services.manager_dashboard import (
    AnalyticalCoverageSummary,
    ManagerDashboardSummary,
    WorkerDashboardCard,
)
from apps.analytics.services.product_performance import (
    WorkerProductPerformance,
)
from apps.analytics.services.sales_aggregation import (
    SalesAggregationResult,
)
from apps.analytics.services.worker_performance import (
    PerformanceDataQualitySummary,
    WorkerPerformanceKpi,
)


PERCENT_MULTIPLIER = Decimal("100")


@dataclass(frozen=True, slots=True)
class ManagerDashboardSummaryPresentation:
    total_sales: Decimal
    sale_record_count: int
    positive_sale_record_count: int
    zero_total_record_count: int

    average_sale_value: Decimal | None
    average_positive_sale_value: Decimal | None

    worker_count: int
    measured_sales_worker_count: int

    pos_record_count: int
    visited_record_count: int
    not_visited_record_count: int

    visit_success_percentage: Decimal | None
    non_visit_percentage: Decimal | None

    distinct_brand_client_count: int

    worker_not_sold_product_count: int
    truck_not_sold_product_count: int

    worker_negative_gap_product_count: int
    truck_negative_gap_product_count: int

    confirmed_stopped_truck_count: int
    possible_stopped_truck_count: int
    conflicting_truck_state_count: int


def _rate_to_percentage(
    value: Decimal | None,
) -> Decimal | None:
    if value is None:
        return None

    return value * PERCENT_MULTIPLIER


def present_manager_dashboard_summary(
    summary: ManagerDashboardSummary,
) -> ManagerDashboardSummaryPresentation:
    return ManagerDashboardSummaryPresentation(
        total_sales=summary.total_sales,
        sale_record_count=summary.sale_record_count,
        positive_sale_record_count=(
            summary.positive_sale_record_count
        ),
        zero_total_record_count=(
            summary.zero_total_record_count
        ),
        average_sale_value=summary.average_sale_value,
        average_positive_sale_value=(
            summary.average_positive_sale_value
        ),
        worker_count=summary.worker_count,
        measured_sales_worker_count=(
            summary.measured_sales_worker_count
        ),
        pos_record_count=summary.pos_record_count,
        visited_record_count=(
            summary.visited_record_count
        ),
        not_visited_record_count=(
            summary.not_visited_record_count
        ),
        visit_success_percentage=(
            _rate_to_percentage(
                summary.visit_success_rate
            )
        ),
        non_visit_percentage=(
            _rate_to_percentage(
                summary.non_visit_rate
            )
        ),
        distinct_brand_client_count=(
            summary.distinct_brand_client_count
        ),
        worker_not_sold_product_count=(
            summary.worker_not_sold_product_count
        ),
        truck_not_sold_product_count=(
            summary.truck_not_sold_product_count
        ),
        worker_negative_gap_product_count=(
            summary.worker_negative_gap_product_count
        ),
        truck_negative_gap_product_count=(
            summary.truck_negative_gap_product_count
        ),
        confirmed_stopped_truck_count=(
            summary.confirmed_stopped_truck_count
        ),
        possible_stopped_truck_count=(
            summary.possible_stopped_truck_count
        ),
        conflicting_truck_state_count=(
            summary.conflicting_truck_state_count
        ),
    )


@dataclass(frozen=True, slots=True)
class AnalyticalCoveragePresentation:
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

    period_excluded_row_count: int
    has_partial_period_exclusions: bool


@dataclass(frozen=True, slots=True)
class DataQualityPresentation:
    sales_attribution_issue_count: int
    pos_attribution_issue_count: int
    items_attribution_issue_count: int
    opening_stock_attribution_issue_count: int
    chargement_attribution_issue_count: int
    operational_attribution_issue_count: int

    pos_numeric_message_warning_count: int
    pos_duplicate_same_day_warning_count: int

    attribution_issue_count: int
    warning_count: int
    total_issue_and_warning_count: int


def present_analytical_coverage(
    coverage: AnalyticalCoverageSummary,
) -> AnalyticalCoveragePresentation:
    return AnalyticalCoveragePresentation(
        sales_source_row_count=(
            coverage.sales_source_row_count
        ),
        sales_included_row_count=(
            coverage.sales_included_row_count
        ),
        sales_outside_period_count=(
            coverage.sales_outside_period_count
        ),
        pos_source_row_count=(
            coverage.pos_source_row_count
        ),
        pos_included_row_count=(
            coverage.pos_included_row_count
        ),
        pos_outside_period_count=(
            coverage.pos_outside_period_count
        ),
        items_source_row_count=(
            coverage.items_source_row_count
        ),
        items_included_row_count=(
            coverage.items_included_row_count
        ),
        items_outside_period_count=(
            coverage.items_outside_period_count
        ),
        items_partial_overlap_count=(
            coverage.items_partial_overlap_count
        ),
        opening_stock_source_row_count=(
            coverage.opening_stock_source_row_count
        ),
        opening_stock_included_row_count=(
            coverage.opening_stock_included_row_count
        ),
        opening_stock_outside_period_count=(
            coverage.opening_stock_outside_period_count
        ),
        opening_stock_partial_overlap_count=(
            coverage.opening_stock_partial_overlap_count
        ),
        chargement_source_row_count=(
            coverage.chargement_source_row_count
        ),
        chargement_included_row_count=(
            coverage.chargement_included_row_count
        ),
        chargement_outside_period_count=(
            coverage.chargement_outside_period_count
        ),
        chargement_partial_overlap_count=(
            coverage.chargement_partial_overlap_count
        ),
        operational_source_row_count=(
            coverage.operational_source_row_count
        ),
        operational_included_row_count=(
            coverage.operational_included_row_count
        ),
        operational_outside_period_count=(
            coverage.operational_outside_period_count
        ),
        operational_partial_overlap_count=(
            coverage.operational_partial_overlap_count
        ),
        period_excluded_row_count=(
            coverage.period_excluded_row_count
        ),
        has_partial_period_exclusions=(
            coverage.has_partial_period_exclusions
        ),
    )


def present_data_quality(
    data_quality: PerformanceDataQualitySummary,
) -> DataQualityPresentation:
    return DataQualityPresentation(
        sales_attribution_issue_count=(
            data_quality.sales_attribution_issue_count
        ),
        pos_attribution_issue_count=(
            data_quality.pos_attribution_issue_count
        ),
        items_attribution_issue_count=(
            data_quality.items_attribution_issue_count
        ),
        opening_stock_attribution_issue_count=(
            data_quality
            .opening_stock_attribution_issue_count
        ),
        chargement_attribution_issue_count=(
            data_quality
            .chargement_attribution_issue_count
        ),
        operational_attribution_issue_count=(
            data_quality
            .operational_attribution_issue_count
        ),
        pos_numeric_message_warning_count=(
            data_quality
            .pos_numeric_message_warning_count
        ),
        pos_duplicate_same_day_warning_count=(
            data_quality
            .pos_duplicate_same_day_warning_count
        ),
        attribution_issue_count=(
            data_quality.attribution_issue_count
        ),
        warning_count=data_quality.warning_count,
        total_issue_and_warning_count=(
            data_quality.total_issue_and_warning_count
        ),
    )



@dataclass(frozen=True, slots=True)
class WorkerRankingPresentation:
    worker_id: int
    worker_name: str
    employee_code: str | None

    total_sales: Decimal
    sale_record_count: int
    positive_sale_record_count: int
    zero_total_record_count: int

    average_positive_sale_value: Decimal | None
    zero_total_sale_percentage: Decimal | None

    pos_record_count: int
    visited_record_count: int
    not_visited_record_count: int
    visit_success_percentage: Decimal | None
    non_visit_percentage: Decimal | None

    distinct_brand_client_count: int

    brand_product_count: int
    sold_product_count: int
    not_sold_product_count: int
    negative_gap_product_count: int
    sold_without_supply_context_count: int

    has_sales_measurement: bool
    has_visit_measurement: bool
    has_product_measurement: bool


def _worker_display_values(
    worker_id: int,
    worker,
) -> tuple[str, str | None]:
    if worker is None:
        return (
            f"البائع رقم {worker_id}",
            None,
        )

    first_name = str(
        getattr(worker, "first_name", "") or ""
    ).strip()
    last_name = str(
        getattr(worker, "last_name", "") or ""
    ).strip()
    employee_code = str(
        getattr(worker, "employee_code", "") or ""
    ).strip()

    full_name = f"{first_name} {last_name}".strip()

    if full_name:
        return (
            full_name,
            employee_code or None,
        )

    if employee_code:
        return (
            employee_code,
            employee_code,
        )

    return (
        f"البائع رقم {worker_id}",
        None,
    )


def present_worker_ranking(
    kpi: WorkerPerformanceKpi,
    workers_by_id: dict[int, object],
) -> WorkerRankingPresentation:
    worker_name, employee_code = (
        _worker_display_values(
            kpi.worker_id,
            workers_by_id.get(kpi.worker_id),
        )
    )

    return WorkerRankingPresentation(
        worker_id=kpi.worker_id,
        worker_name=worker_name,
        employee_code=employee_code,
        total_sales=kpi.total_sales,
        sale_record_count=kpi.sale_record_count,
        positive_sale_record_count=(
            kpi.positive_sale_record_count
        ),
        zero_total_record_count=(
            kpi.zero_total_record_count
        ),
        average_positive_sale_value=(
            kpi.average_positive_sale_value
        ),
        zero_total_sale_percentage=(
            _rate_to_percentage(
                kpi.zero_total_sale_rate
            )
        ),
        pos_record_count=kpi.pos_record_count,
        visited_record_count=(
            kpi.visited_record_count
        ),
        not_visited_record_count=(
            kpi.not_visited_record_count
        ),
        visit_success_percentage=(
            _rate_to_percentage(
                kpi.visit_success_rate
            )
        ),
        non_visit_percentage=(
            _rate_to_percentage(
                kpi.non_visit_rate
            )
        ),
        distinct_brand_client_count=(
            kpi.distinct_brand_client_count
        ),
        brand_product_count=kpi.brand_product_count,
        sold_product_count=kpi.sold_product_count,
        not_sold_product_count=(
            kpi.not_sold_product_count
        ),
        negative_gap_product_count=(
            kpi.negative_gap_product_count
        ),
        sold_without_supply_context_count=(
            kpi.sold_without_supply_context_count
        ),
        has_sales_measurement=(
            kpi.has_sales_measurement
        ),
        has_visit_measurement=(
            kpi.has_visit_measurement
        ),
        has_product_measurement=(
            kpi.has_product_measurement
        ),
    )


@dataclass(frozen=True, slots=True)
class WorkerProductPresentation:
    brand_id: int
    brand_name: str
    article: str

    opening_quantity: Decimal
    chargement_quantity: Decimal
    supplied_quantity: Decimal
    sold_quantity: Decimal

    analytical_quantity_gap: Decimal
    sold_to_supplied_percentage: Decimal | None

    is_not_sold: bool
    is_sold_without_supply_context: bool
    has_negative_quantity_gap: bool


@dataclass(frozen=True, slots=True)
class WorkerDashboardCardPresentation:
    worker_id: int
    worker_name: str
    employee_code: str | None

    metrics: WorkerRankingPresentation

    not_sold_products: tuple[
        WorkerProductPresentation,
        ...,
    ]
    least_sold_products: tuple[
        WorkerProductPresentation,
        ...,
    ]
    negative_gap_products: tuple[
        WorkerProductPresentation,
        ...,
    ]
    sold_without_supply_context_products: tuple[
        WorkerProductPresentation,
        ...,
    ]

    has_product_attention_items: bool
    has_non_visit_attention: bool
    has_sales_measurement: bool
    has_visit_measurement: bool
    has_product_measurement: bool


def _brand_display_name(
    brand_id: int,
    brands_by_id: dict[int, object],
) -> str:
    brand = brands_by_id.get(brand_id)

    if brand is None:
        return f"العلامة رقم {brand_id}"

    brand_name = str(
        getattr(brand, "name", "") or ""
    ).strip()

    if brand_name:
        return brand_name

    brand_code = str(
        getattr(brand, "code", "") or ""
    ).strip()

    if brand_code:
        return brand_code

    return f"العلامة رقم {brand_id}"


def present_worker_product(
    product: WorkerProductPerformance,
    brands_by_id: dict[int, object],
) -> WorkerProductPresentation:
    quantities = product.quantities

    return WorkerProductPresentation(
        brand_id=product.brand_id,
        brand_name=_brand_display_name(
            product.brand_id,
            brands_by_id,
        ),
        article=product.article,
        opening_quantity=(
            quantities.opening_quantity
        ),
        chargement_quantity=(
            quantities.chargement_quantity
        ),
        supplied_quantity=(
            quantities.supplied_quantity
        ),
        sold_quantity=quantities.sold_quantity,
        analytical_quantity_gap=(
            quantities.analytical_quantity_gap
        ),
        sold_to_supplied_percentage=(
            _rate_to_percentage(
                quantities.sold_to_supplied_ratio
            )
        ),
        is_not_sold=quantities.is_not_sold,
        is_sold_without_supply_context=(
            quantities
            .is_sold_without_supply_context
        ),
        has_negative_quantity_gap=(
            quantities.has_negative_quantity_gap
        ),
    )


def present_worker_dashboard_card(
    card: WorkerDashboardCard,
    workers_by_id: dict[int, object],
    brands_by_id: dict[int, object],
) -> WorkerDashboardCardPresentation:
    metrics = present_worker_ranking(
        card.kpi,
        workers_by_id,
    )

    return WorkerDashboardCardPresentation(
        worker_id=card.worker_id,
        worker_name=metrics.worker_name,
        employee_code=metrics.employee_code,
        metrics=metrics,
        not_sold_products=tuple(
            present_worker_product(
                product,
                brands_by_id,
            )
            for product in card.not_sold_products
        ),
        least_sold_products=tuple(
            present_worker_product(
                product,
                brands_by_id,
            )
            for product in card.least_sold_products
        ),
        negative_gap_products=tuple(
            present_worker_product(
                product,
                brands_by_id,
            )
            for product in card.negative_gap_products
        ),
        sold_without_supply_context_products=tuple(
            present_worker_product(
                product,
                brands_by_id,
            )
            for product in (
                card
                .sold_without_supply_context_products
            )
        ),
        has_product_attention_items=(
            card.has_product_attention_items
        ),
        has_non_visit_attention=(
            card.has_non_visit_attention
        ),
        has_sales_measurement=(
            card.has_sales_measurement
        ),
        has_visit_measurement=(
            card.kpi.has_visit_measurement
        ),
        has_product_measurement=(
            card.kpi.has_product_measurement
        ),
    )


@dataclass(frozen=True, slots=True)
class BrandSalesChartPresentation:
    brand_id: int
    brand_name: str

    total_sales: Decimal
    sale_record_count: int
    positive_sale_record_count: int
    zero_total_record_count: int

    contribution_percentage: Decimal | None
    relative_bar_percentage: Decimal


def present_brand_sales_chart(
    sales: SalesAggregationResult,
    brands_by_id: dict[int, object],
) -> tuple[BrandSalesChartPresentation, ...]:
    brand_totals = tuple(
        sales.by_brand or ()
    )

    maximum_positive_total = max(
        (
            item.metrics.total_sales
            for item in brand_totals
            if item.metrics.total_sales > 0
        ),
        default=Decimal("0"),
    )

    overall_total = sales.overall.total_sales
    presentations = []

    for item in brand_totals:
        total_sales = item.metrics.total_sales

        if overall_total > 0:
            contribution_percentage = (
                total_sales
                / overall_total
                * PERCENT_MULTIPLIER
            )
        else:
            contribution_percentage = None

        if (
            maximum_positive_total > 0
            and total_sales > 0
        ):
            relative_bar_percentage = (
                total_sales
                / maximum_positive_total
                * PERCENT_MULTIPLIER
            )
        else:
            relative_bar_percentage = Decimal("0")

        presentations.append(
            BrandSalesChartPresentation(
                brand_id=item.brand_id,
                brand_name=_brand_display_name(
                    item.brand_id,
                    brands_by_id,
                ),
                total_sales=total_sales,
                sale_record_count=(
                    item.metrics.sale_record_count
                ),
                positive_sale_record_count=(
                    item.metrics
                    .positive_sale_record_count
                ),
                zero_total_record_count=(
                    item.metrics.zero_total_record_count
                ),
                contribution_percentage=(
                    contribution_percentage
                ),
                relative_bar_percentage=(
                    relative_bar_percentage
                ),
            )
        )

    return tuple(
        sorted(
            presentations,
            key=lambda item: (
                -item.total_sales,
                item.brand_name.casefold(),
                item.brand_id,
            ),
        )
    )



@dataclass(frozen=True, slots=True)
class SalesTimelinePointPresentation:
    sale_date: date

    total_sales: Decimal
    sale_record_count: int
    positive_sale_record_count: int
    zero_total_record_count: int

    horizontal_percentage: Decimal
    relative_height_percentage: Decimal
    is_peak: bool


@dataclass(frozen=True, slots=True)
class SalesTimelinePresentation:
    points: tuple[
        SalesTimelinePointPresentation,
        ...,
    ]

    total_sales: Decimal
    average_daily_sales: Decimal | None

    recorded_day_count: int
    positive_day_count: int
    zero_total_day_count: int

    first_date: date | None
    last_date: date | None

    peak_date: date | None
    peak_total_sales: Decimal | None


def present_sales_timeline(
    sales: SalesAggregationResult,
) -> SalesTimelinePresentation:
    daily_totals = tuple(
        sorted(
            sales.by_date or (),
            key=lambda item: item.sale_date,
        )
    )

    if not daily_totals:
        return SalesTimelinePresentation(
            points=(),
            total_sales=Decimal("0"),
            average_daily_sales=None,
            recorded_day_count=0,
            positive_day_count=0,
            zero_total_day_count=0,
            first_date=None,
            last_date=None,
            peak_date=None,
            peak_total_sales=None,
        )

    first_date = daily_totals[0].sale_date
    last_date = daily_totals[-1].sale_date
    date_span_days = (
        last_date - first_date
    ).days

    maximum_positive_total = max(
        (
            item.metrics.total_sales
            for item in daily_totals
            if item.metrics.total_sales > 0
        ),
        default=Decimal("0"),
    )

    total_sales = sum(
        (
            item.metrics.total_sales
            for item in daily_totals
        ),
        Decimal("0"),
    )

    points = []

    for item in daily_totals:
        item_total = item.metrics.total_sales

        if date_span_days > 0:
            horizontal_percentage = (
                Decimal(
                    (
                        item.sale_date
                        - first_date
                    ).days
                )
                / Decimal(date_span_days)
                * PERCENT_MULTIPLIER
            )
        else:
            horizontal_percentage = Decimal("50")

        if (
            maximum_positive_total > 0
            and item_total > 0
        ):
            relative_height_percentage = (
                item_total
                / maximum_positive_total
                * PERCENT_MULTIPLIER
            )
        else:
            relative_height_percentage = Decimal("0")

        points.append(
            SalesTimelinePointPresentation(
                sale_date=item.sale_date,
                total_sales=item_total,
                sale_record_count=(
                    item.metrics.sale_record_count
                ),
                positive_sale_record_count=(
                    item.metrics
                    .positive_sale_record_count
                ),
                zero_total_record_count=(
                    item.metrics
                    .zero_total_record_count
                ),
                horizontal_percentage=(
                    horizontal_percentage
                ),
                relative_height_percentage=(
                    relative_height_percentage
                ),
                is_peak=(
                    maximum_positive_total > 0
                    and item_total
                    == maximum_positive_total
                ),
            )
        )

    if maximum_positive_total > 0:
        peak_item = next(
            item
            for item in daily_totals
            if (
                item.metrics.total_sales
                == maximum_positive_total
            )
        )
        peak_date = peak_item.sale_date
        peak_total_sales = maximum_positive_total
    else:
        peak_date = None
        peak_total_sales = None

    recorded_day_count = len(daily_totals)

    return SalesTimelinePresentation(
        points=tuple(points),
        total_sales=total_sales,
        average_daily_sales=(
            total_sales
            / Decimal(recorded_day_count)
        ),
        recorded_day_count=recorded_day_count,
        positive_day_count=sum(
            1
            for item in daily_totals
            if item.metrics.total_sales > 0
        ),
        zero_total_day_count=sum(
            1
            for item in daily_totals
            if item.metrics.total_sales == 0
        ),
        first_date=first_date,
        last_date=last_date,
        peak_date=peak_date,
        peak_total_sales=peak_total_sales,
    )
