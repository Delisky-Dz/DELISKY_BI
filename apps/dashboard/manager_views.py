from dataclasses import dataclass
from decimal import Decimal

from django.shortcuts import render

from apps.analytics.services.assignment_resolver import (
    build_assignment_index,
)
from apps.analytics.services.pos_visit_aggregation import (
    aggregate_pos_visits,
)
from apps.analytics.services.sales_aggregation import (
    SalesAggregationResult,
    aggregate_sales,
)
from apps.analytics.services.truck_resolver import (
    build_truck_code_index,
)
from apps.imports.models import DistributionBrand
from apps.workforce.models import Worker

from .access import (
    can_use_ai_assistants,
    manager_required,
)
from .manager_filters import (
    build_filter_form,
    manager_filter_query,
    selected_brand_id,
)
from .manager_identity import worker_display_identity
from .presenters import (
    present_brand_sales_chart,
    present_sales_timeline,
)


DASHBOARD_TEMPLATE_NAME = (
    "dashboard/manager_dashboard.html"
)
PERCENT_MULTIPLIER = Decimal("100")
CLIENT_FOLLOW_UP_MINIMUM_NON_VISITS = 3
OVERVIEW_TOP_SELLERS_LIMIT = 5


@dataclass(frozen=True, slots=True)
class OverviewSummaryPresentation:
    total_sales: Decimal
    sale_record_count: int
    positive_sale_record_count: int
    pos_record_count: int
    visited_record_count: int
    not_visited_record_count: int
    visit_success_percentage: Decimal | None
    measured_sales_worker_count: int
    distinct_brand_client_count: int
    client_follow_up_count: int


@dataclass(frozen=True, slots=True)
class OverviewSellerPresentation:
    worker_id: int
    worker_name: str
    subtitle: str | None
    total_sales: Decimal
    relative_bar_percentage: Decimal


def _load_brands_by_id(
    sales: SalesAggregationResult,
) -> dict[int, DistributionBrand]:
    brand_ids = {
        item.brand_id
        for item in sales.by_brand
    }

    if not brand_ids:
        return {}

    return {
        brand.pk: brand
        for brand in DistributionBrand.objects.filter(
            pk__in=brand_ids,
        )
    }


def _present_top_sellers(
    sales: SalesAggregationResult,
) -> tuple[OverviewSellerPresentation, ...]:
    ranked = tuple(
        sorted(
            sales.by_worker or (),
            key=lambda item: (
                -item.metrics.total_sales,
                item.worker_id,
            ),
        )[:OVERVIEW_TOP_SELLERS_LIMIT]
    )

    worker_ids = {
        item.worker_id
        for item in ranked
    }
    workers_by_id = {
        worker.pk: worker
        for worker in Worker.objects.filter(
            pk__in=worker_ids,
        )
    }

    maximum_total = max(
        (
            item.metrics.total_sales
            for item in ranked
            if item.metrics.total_sales > 0
        ),
        default=Decimal("0"),
    )

    rows = []

    for item in ranked:
        worker_name, subtitle = worker_display_identity(
            item.worker_id,
            workers_by_id.get(item.worker_id),
        )
        total_sales = item.metrics.total_sales

        if maximum_total > 0 and total_sales > 0:
            relative_bar_percentage = (
                total_sales
                / maximum_total
                * PERCENT_MULTIPLIER
            )
        else:
            relative_bar_percentage = Decimal("0")

        rows.append(
            OverviewSellerPresentation(
                worker_id=item.worker_id,
                worker_name=worker_name,
                subtitle=subtitle,
                total_sales=total_sales,
                relative_bar_percentage=(
                    relative_bar_percentage
                ),
            )
        )

    return tuple(rows)


def _present_overview_summary(
    sales,
    visits,
) -> OverviewSummaryPresentation:
    if visits.overall.total_record_count:
        visit_success_percentage = (
            Decimal(visits.overall.visited_record_count)
            / Decimal(visits.overall.total_record_count)
            * PERCENT_MULTIPLIER
        )
    else:
        visit_success_percentage = None

    client_follow_up_count = sum(
        1
        for item in visits.by_brand_client
        if (
            item.metrics.not_visited_record_count
            >= CLIENT_FOLLOW_UP_MINIMUM_NON_VISITS
        )
    )

    return OverviewSummaryPresentation(
        total_sales=sales.overall.total_sales,
        sale_record_count=(
            sales.overall.sale_record_count
        ),
        positive_sale_record_count=(
            sales.overall.positive_sale_record_count
        ),
        pos_record_count=(
            visits.overall.total_record_count
        ),
        visited_record_count=(
            visits.overall.visited_record_count
        ),
        not_visited_record_count=(
            visits.overall.not_visited_record_count
        ),
        visit_success_percentage=(
            visit_success_percentage
        ),
        measured_sales_worker_count=len(
            sales.by_worker or ()
        ),
        distinct_brand_client_count=len(
            visits.by_brand_client or ()
        ),
        client_follow_up_count=(
            client_follow_up_count
        ),
    )


@manager_required
def manager_dashboard(request):
    filter_requested, filter_form = (
        build_filter_form(request)
    )

    overview_summary = None
    top_sales_workers = ()
    sales_timeline = None
    brand_sales_chart = ()
    response_status = 200

    if filter_requested:
        if filter_form.is_valid():
            brand_id = selected_brand_id(
                filter_form
            )
            period_start = filter_form.cleaned_data[
                "period_start"
            ]
            period_end = filter_form.cleaned_data[
                "period_end"
            ]

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

            overview_summary = (
                _present_overview_summary(
                    sales,
                    visits,
                )
            )
            top_sales_workers = (
                _present_top_sellers(sales)
            )
            sales_timeline = present_sales_timeline(
                sales
            )

            if brand_id is None:
                brand_sales_chart = (
                    present_brand_sales_chart(
                        sales,
                        _load_brands_by_id(sales),
                    )
                )
        else:
            response_status = 400

    context = {
        "active_section": "overview",
        "active_item": "overview",
        "manager_query": manager_filter_query(
            request
        ),
        "filter_reset_url": request.path,
        "filter_requested": filter_requested,
        "filter_form": filter_form,
        "can_use_ai_assistants": can_use_ai_assistants(
            request.user
        ),
        "overview_summary": overview_summary,
        "top_sales_workers": top_sales_workers,
        "sales_timeline": sales_timeline,
        "brand_sales_chart": brand_sales_chart,
    }

    return render(
        request,
        DASHBOARD_TEMPLATE_NAME,
        context,
        status=response_status,
    )
