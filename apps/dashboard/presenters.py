from dataclasses import dataclass
from decimal import Decimal

from apps.analytics.services.manager_dashboard import (
    AnalyticalCoverageSummary,
    ManagerDashboardSummary,
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
