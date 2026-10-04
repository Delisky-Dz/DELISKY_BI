from dataclasses import dataclass
from decimal import Decimal

from django.http import Http404
from django.shortcuts import render

from apps.analytics.services.sales_aggregation import (
    SalesAggregationResult,
    aggregate_sales,
)
from apps.fleet.models import Truck
from apps.imports.models import DistributionBrand

from .access import (
    can_use_ai_assistants,
    manager_required,
)
from .manager_filters import (
    build_filter_form,
    manager_filter_query,
    selected_brand_id,
)
from .presenters import (
    present_brand_sales_chart,
    present_sales_timeline,
)


SALES_TEMPLATE_NAME = "dashboard/manager_sales.html"
SALES_TABS = {
    "summary": "ملخص المبيعات",
    "timeline": "تطور المبيعات",
    "brands": "حسب العلامة",
    "trucks": "حسب الشاحنة",
    "daily": "التفاصيل اليومية",
}


@dataclass(frozen=True, slots=True)
class SalesSummaryPresentation:
    total_sales: Decimal
    sale_record_count: int
    positive_sale_record_count: int
    zero_total_record_count: int
    average_positive_sale_value: Decimal | None
    recorded_day_count: int


@dataclass(frozen=True, slots=True)
class TruckSalesPresentation:
    truck_id: int
    truck_name: str
    brand_name: str
    total_sales: Decimal
    sale_record_count: int
    positive_sale_record_count: int
    zero_total_record_count: int


def _present_sales_summary(
    sales: SalesAggregationResult,
) -> SalesSummaryPresentation:
    metrics = sales.overall

    if metrics.positive_sale_record_count:
        average_positive_sale_value = (
            metrics.total_sales
            / Decimal(
                metrics.positive_sale_record_count
            )
        )
    else:
        average_positive_sale_value = None

    return SalesSummaryPresentation(
        total_sales=metrics.total_sales,
        sale_record_count=metrics.sale_record_count,
        positive_sale_record_count=(
            metrics.positive_sale_record_count
        ),
        zero_total_record_count=(
            metrics.zero_total_record_count
        ),
        average_positive_sale_value=(
            average_positive_sale_value
        ),
        recorded_day_count=len(sales.by_date or ()),
    )


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


def _present_truck_sales(
    sales: SalesAggregationResult,
) -> tuple[TruckSalesPresentation, ...]:
    truck_ids = {
        item.truck_id
        for item in sales.by_truck
    }

    trucks_by_id = {
        truck.pk: truck
        for truck in Truck.objects.filter(
            pk__in=truck_ids,
        ).select_related(
            "distribution_brand",
        )
    }

    rows = []

    for item in sales.by_truck:
        truck = trucks_by_id.get(item.truck_id)

        if truck is None:
            truck_name = f"الشاحنة رقم {item.truck_id}"
            brand_name = "غير محدد"
        else:
            truck_name = (
                truck.internal_code
                or truck.registration_number
            )
            brand = truck.distribution_brand
            brand_name = (
                brand.name
                if brand is not None
                else "غير محدد"
            )

        rows.append(
            TruckSalesPresentation(
                truck_id=item.truck_id,
                truck_name=truck_name,
                brand_name=brand_name,
                total_sales=item.metrics.total_sales,
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
            )
        )

    return tuple(
        sorted(
            rows,
            key=lambda row: (
                -row.total_sales,
                row.truck_name.casefold(),
                row.truck_id,
            ),
        )
    )


def _build_sales_presentations(
    *,
    sales: SalesAggregationResult,
    tab: str,
    selected_brand,
) -> dict[str, object]:
    context = {
        "sales_summary": None,
        "sales_timeline": None,
        "brand_sales_chart": (),
        "truck_sales": (),
        "daily_sales": (),
        "single_brand_scope": False,
    }

    if tab == "summary":
        context["sales_summary"] = (
            _present_sales_summary(sales)
        )

    elif tab == "timeline":
        context["sales_timeline"] = (
            present_sales_timeline(sales)
        )

    elif tab == "brands":
        if selected_brand is None:
            context["brand_sales_chart"] = (
                present_brand_sales_chart(
                    sales,
                    _load_brands_by_id(sales),
                )
            )
        else:
            context["single_brand_scope"] = True
            context["truck_sales"] = (
                _present_truck_sales(sales)
            )

    elif tab == "trucks":
        context["truck_sales"] = (
            _present_truck_sales(sales)
        )

    elif tab == "daily":
        context["daily_sales"] = tuple(
            sorted(
                sales.by_date or (),
                key=lambda item: item.sale_date,
                reverse=True,
            )
        )

    return context


@manager_required
def manager_sales(request, tab="summary"):
    if tab not in SALES_TABS:
        raise Http404

    filter_requested, filter_form = (
        build_filter_form(request)
    )

    response_status = 200
    sales = None
    presentations = {
        "sales_summary": None,
        "sales_timeline": None,
        "brand_sales_chart": (),
        "truck_sales": (),
        "daily_sales": (),
        "single_brand_scope": False,
    }

    if filter_requested:
        if filter_form.is_valid():
            selected_brand = (
                filter_form.cleaned_data["brand"]
            )

            sales = aggregate_sales(
                period_start=(
                    filter_form.cleaned_data[
                        "period_start"
                    ]
                ),
                period_end=(
                    filter_form.cleaned_data[
                        "period_end"
                    ]
                ),
                brand_id=selected_brand_id(
                    filter_form
                ),
            )

            presentations = (
                _build_sales_presentations(
                    sales=sales,
                    tab=tab,
                    selected_brand=selected_brand,
                )
            )
        else:
            response_status = 400

    context = {
        "active_section": "sales",
        "active_item": f"sales-{tab}",
        "manager_query": manager_filter_query(
            request
        ),
        "filter_reset_url": request.path,
        "filter_requested": filter_requested,
        "filter_form": filter_form,
        "can_use_ai_assistants": can_use_ai_assistants(
            request.user
        ),
        "sales": sales,
        "sales_tab": tab,
        "sales_tab_label": SALES_TABS[tab],
        "sales_tabs": SALES_TABS,
        **presentations,
    }

    return render(
        request,
        SALES_TEMPLATE_NAME,
        context,
        status=response_status,
    )
