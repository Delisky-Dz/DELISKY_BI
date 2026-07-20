from django.shortcuts import render

from apps.analytics.services.manager_dashboard import (
    build_manager_dashboard,
)

from .access import manager_required
from .forms import ManagerDashboardFilterForm
from .presenters import (
    present_manager_dashboard_summary,
)


DASHBOARD_PRODUCT_LIMIT = 10
DASHBOARD_TEMPLATE_NAME = (
    "dashboard/manager_dashboard.html"
)


@manager_required
def manager_dashboard(request):
    filter_form = ManagerDashboardFilterForm(
        data=request.GET,
    )

    dashboard_result = None
    summary_presentation = None
    response_status = 200

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

        if dashboard_summary is not None:
            summary_presentation = (
                present_manager_dashboard_summary(
                    dashboard_summary
                )
            )
    else:
        response_status = 400

    context = {
        "filter_form": filter_form,
        "dashboard_result": dashboard_result,
        "summary": summary_presentation,
    }

    return render(
        request,
        DASHBOARD_TEMPLATE_NAME,
        context,
        status=response_status,
    )
