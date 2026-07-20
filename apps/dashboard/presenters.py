from dataclasses import dataclass
from decimal import Decimal

from apps.analytics.services.manager_dashboard import (
    ManagerDashboardSummary,
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
