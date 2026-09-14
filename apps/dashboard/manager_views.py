from apps.analytics.services.manager_dashboard import (
    build_manager_dashboard,
)

from .access import (
    can_use_ai_assistants,
    manager_required,
)
from .forms import ManagerDashboardFilterForm
from .presenters import (
    present_analytical_coverage,
    present_data_quality,
    present_manager_dashboard_summary,
)
from .views import (
    DASHBOARD_PRODUCT_LIMIT,
    _build_worker_presentations,
)


DASHBOARD_TEMPLATE_NAME = (
    "dashboard/manager_dashboard.html"
)
FILTER_QUERY_KEYS = frozenset(
    {
        "period_start",
        "period_end",
        "brand",
        "run",
    }
)


def _filter_requested(request) -> bool:
    return any(
        key in request.GET
        for key in FILTER_QUERY_KEYS
    )


@manager_required
def manager_dashboard(request):
    filter_requested = _filter_requested(request)
    filter_form = ManagerDashboardFilterForm(
        data=(
            request.GET
            if filter_requested
            else None
        ),
    )

    dashboard_result = None
    summary_presentation = None
    coverage_presentation = None
    data_quality_presentation = None

    worker_presentations = {
        "top_sales_workers": (),
        "lowest_sales_workers": (),
        "highest_visit_workers": (),
        "highest_non_visit_workers": (),
        "most_not_sold_workers": (),
        "top_visited_clients": (),
        "top_not_visited_clients": (),
        "worker_cards": (),
        "brand_sales_chart": (),
        "sales_timeline": None,
    }

    response_status = 200

    if filter_requested:
        if filter_form.is_valid():
            selected_brand = (
                filter_form.cleaned_data["brand"]
            )

            dashboard_result = build_manager_dashboard(
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
                brand_id=(
                    selected_brand.pk
                    if selected_brand is not None
                    else None
                ),
                product_limit=DASHBOARD_PRODUCT_LIMIT,
            )

            dashboard_summary = getattr(
                dashboard_result,
                "summary",
                None,
            )
            dashboard_coverage = getattr(
                dashboard_result,
                "coverage",
                None,
            )
            dashboard_data_quality = getattr(
                dashboard_result,
                "data_quality",
                None,
            )

            if dashboard_summary is not None:
                summary_presentation = (
                    present_manager_dashboard_summary(
                        dashboard_summary
                    )
                )

            if dashboard_coverage is not None:
                coverage_presentation = (
                    present_analytical_coverage(
                        dashboard_coverage
                    )
                )

            if dashboard_data_quality is not None:
                data_quality_presentation = (
                    present_data_quality(
                        dashboard_data_quality
                    )
                )

            worker_presentations = (
                _build_worker_presentations(
                    dashboard_result
                )
            )
        else:
            response_status = 400

    context = {
        "filter_requested": filter_requested,
        "filter_form": filter_form,
        "dashboard_result": dashboard_result,
        "summary": summary_presentation,
        "coverage": coverage_presentation,
        "data_quality": data_quality_presentation,
        "can_use_ai_assistants": can_use_ai_assistants(
            request.user
        ),
        **worker_presentations,
    }

    from django.shortcuts import render

    return render(
        request,
        DASHBOARD_TEMPLATE_NAME,
        context,
        status=response_status,
    )
