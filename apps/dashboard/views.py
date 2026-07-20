from django.shortcuts import render

from apps.analytics.services.manager_dashboard import (
    build_manager_dashboard,
)
from apps.workforce.models import Worker

from .access import manager_required
from .forms import ManagerDashboardFilterForm
from .presenters import (
    present_analytical_coverage,
    present_data_quality,
    present_manager_dashboard_summary,
    present_worker_ranking,
)


DASHBOARD_PRODUCT_LIMIT = 10
WORKER_RANKING_LIMIT = 10
NON_VISIT_MINIMUM_POS_RECORDS = 3

DASHBOARD_TEMPLATE_NAME = (
    "dashboard/manager_dashboard.html"
)


def _ranking_result(method, **kwargs):
    if not callable(method):
        return ()

    return tuple(method(**kwargs))


def _build_worker_rankings(dashboard_result):
    top_sales_kpis = _ranking_result(
        getattr(
            dashboard_result,
            "top_sales_workers",
            None,
        ),
        limit=WORKER_RANKING_LIMIT,
    )

    lowest_sales_kpis = _ranking_result(
        getattr(
            dashboard_result,
            "lowest_sales_workers",
            None,
        ),
        limit=WORKER_RANKING_LIMIT,
    )

    highest_non_visit_kpis = _ranking_result(
        getattr(
            dashboard_result,
            "highest_non_visit_rate_workers",
            None,
        ),
        limit=WORKER_RANKING_LIMIT,
        minimum_pos_records=(
            NON_VISIT_MINIMUM_POS_RECORDS
        ),
    )

    worker_performance = getattr(
        dashboard_result,
        "worker_performance",
        None,
    )

    most_not_sold_kpis = _ranking_result(
        getattr(
            worker_performance,
            "most_not_sold_products_workers",
            None,
        ),
        limit=WORKER_RANKING_LIMIT,
    )

    ranking_groups = (
        top_sales_kpis,
        lowest_sales_kpis,
        highest_non_visit_kpis,
        most_not_sold_kpis,
    )

    worker_ids = {
        kpi.worker_id
        for group in ranking_groups
        for kpi in group
    }

    if worker_ids:
        workers_by_id = {
            worker.pk: worker
            for worker in Worker.objects.filter(
                pk__in=worker_ids,
            )
        }
    else:
        workers_by_id = {}

    return {
        "top_sales_workers": tuple(
            present_worker_ranking(
                kpi,
                workers_by_id,
            )
            for kpi in top_sales_kpis
        ),
        "lowest_sales_workers": tuple(
            present_worker_ranking(
                kpi,
                workers_by_id,
            )
            for kpi in lowest_sales_kpis
        ),
        "highest_non_visit_workers": tuple(
            present_worker_ranking(
                kpi,
                workers_by_id,
            )
            for kpi in highest_non_visit_kpis
        ),
        "most_not_sold_workers": tuple(
            present_worker_ranking(
                kpi,
                workers_by_id,
            )
            for kpi in most_not_sold_kpis
        ),
    }


@manager_required
def manager_dashboard(request):
    filter_form = ManagerDashboardFilterForm(
        data=request.GET,
    )

    dashboard_result = None
    summary_presentation = None
    coverage_presentation = None
    data_quality_presentation = None

    worker_rankings = {
        "top_sales_workers": (),
        "lowest_sales_workers": (),
        "highest_non_visit_workers": (),
        "most_not_sold_workers": (),
    }

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

        worker_rankings = _build_worker_rankings(
            dashboard_result
        )
    else:
        response_status = 400

    context = {
        "filter_form": filter_form,
        "dashboard_result": dashboard_result,
        "summary": summary_presentation,
        "coverage": coverage_presentation,
        "data_quality": data_quality_presentation,
        **worker_rankings,
    }

    return render(
        request,
        DASHBOARD_TEMPLATE_NAME,
        context,
        status=response_status,
    )
