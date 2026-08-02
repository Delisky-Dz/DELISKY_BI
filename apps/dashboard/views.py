from time import perf_counter

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.analytics.services.manager_dashboard import (
    build_manager_dashboard,
)
from apps.assistant.audit import (
    AskDeliskyAuditRecord,
    record_ask_delisky_audit_event,
)
from apps.assistant.models import (
    AskDeliskyAuditOutcome,
)
from apps.assistant.ollama_transport import (
    OllamaTransportError,
)
from apps.assistant.provider_factory import (
    AskDeliskyProviderConfigurationError,
    AskDeliskyProviderDisabledError,
)
from apps.assistant.rate_limit import (
    AskDeliskyRateLimitConfigurationError,
    check_ask_delisky_rate_limit,
)
from apps.assistant.runtime import (
    ask_manager_delisky,
)
from apps.imports.models import DistributionBrand
from apps.workforce.models import Worker

from .access import manager_required
from .forms import (
    AskDeliskyForm,
    ManagerDashboardFilterForm,
)
from .presenters import (
    present_analytical_coverage,
    present_brand_sales_chart,
    present_client_visit_ranking,
    present_data_quality,
    present_sales_timeline,
    present_manager_dashboard_summary,
    present_worker_dashboard_card,
    present_worker_ranking,
)


DASHBOARD_PRODUCT_LIMIT = 10
WORKER_RANKING_LIMIT = 10
CLIENT_RANKING_LIMIT = 10
VISIT_MINIMUM_POS_RECORDS = 3
NON_VISIT_MINIMUM_POS_RECORDS = 3

DASHBOARD_TEMPLATE_NAME = (
    "dashboard/manager_dashboard.html"
)


def _ranking_result(method, **kwargs):
    if not callable(method):
        return ()

    return tuple(method(**kwargs))


def _collect_worker_ranking_kpis(
    dashboard_result,
) -> dict[str, tuple]:
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

    highest_visit_kpis = _ranking_result(
        getattr(
            dashboard_result,
            "highest_visit_rate_workers",
            None,
        ),
        limit=WORKER_RANKING_LIMIT,
        minimum_pos_records=(
            VISIT_MINIMUM_POS_RECORDS
        ),
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

    return {
        "top_sales_workers": top_sales_kpis,
        "lowest_sales_workers": lowest_sales_kpis,
        "highest_visit_workers": highest_visit_kpis,
        "highest_non_visit_workers": (
            highest_non_visit_kpis
        ),
        "most_not_sold_workers": (
            most_not_sold_kpis
        ),
    }


def _collect_client_visit_rankings(
    dashboard_result,
) -> dict[str, tuple]:
    visits = getattr(
        dashboard_result,
        "visits",
        None,
    )

    if visits is None:
        return {
            "top_visited_clients": (),
            "top_not_visited_clients": (),
        }

    return {
        "top_visited_clients": _ranking_result(
            getattr(
                visits,
                "top_visited_clients",
                None,
            ),
            limit=CLIENT_RANKING_LIMIT,
        ),
        "top_not_visited_clients": _ranking_result(
            getattr(
                visits,
                "top_not_visited_clients",
                None,
            ),
            limit=CLIENT_RANKING_LIMIT,
        ),
    }


def _collect_worker_ids(
    ranking_kpis: dict[str, tuple],
    worker_cards: tuple,
) -> set[int]:
    worker_ids = {
        kpi.worker_id
        for group in ranking_kpis.values()
        for kpi in group
    }

    worker_ids.update(
        card.worker_id
        for card in worker_cards
    )

    return worker_ids


def _collect_card_brand_ids(
    worker_cards: tuple,
) -> set[int]:
    brand_ids: set[int] = set()

    product_group_names = (
        "not_sold_products",
        "least_sold_products",
        "negative_gap_products",
        "sold_without_supply_context_products",
    )

    for card in worker_cards:
        for group_name in product_group_names:
            products = (
                getattr(card, group_name, ())
                or ()
            )

            brand_ids.update(
                product.brand_id
                for product in products
            )

    return brand_ids



def _collect_client_visit_brand_ids(
    client_visit_rankings: dict[str, tuple],
) -> set[int]:
    return {
        item.brand_id
        for ranking in client_visit_rankings.values()
        for item in ranking
    }


def _collect_sales_brand_ids(
    dashboard_result,
) -> set[int]:
    sales = getattr(
        dashboard_result,
        "sales",
        None,
    )

    brand_totals = (
        getattr(sales, "by_brand", ())
        or ()
    )

    return {
        item.brand_id
        for item in brand_totals
    }


def _load_workers_by_id(
    worker_ids: set[int],
) -> dict[int, Worker]:
    if not worker_ids:
        return {}

    return {
        worker.pk: worker
        for worker in Worker.objects.filter(
            pk__in=worker_ids,
        )
    }


def _load_brands_by_id(
    brand_ids: set[int],
) -> dict[int, DistributionBrand]:
    if not brand_ids:
        return {}

    return {
        brand.pk: brand
        for brand in DistributionBrand.objects.filter(
            pk__in=brand_ids,
        )
    }


def _present_worker_rankings(
    ranking_kpis: dict[str, tuple],
    workers_by_id: dict[int, Worker],
) -> dict[str, tuple]:
    return {
        ranking_name: tuple(
            present_worker_ranking(
                kpi,
                workers_by_id,
            )
            for kpi in kpis
        )
        for ranking_name, kpis
        in ranking_kpis.items()
    }


def _present_client_visit_rankings(
    client_visit_rankings: dict[str, tuple],
    brands_by_id: dict[int, DistributionBrand],
) -> dict[str, tuple]:
    return {
        ranking_name: tuple(
            present_client_visit_ranking(
                item,
                brands_by_id,
            )
            for item in items
        )
        for ranking_name, items
        in client_visit_rankings.items()
    }


def _build_worker_presentations(
    dashboard_result,
) -> dict[str, object]:
    ranking_kpis = (
        _collect_worker_ranking_kpis(
            dashboard_result
        )
    )

    client_visit_rankings = (
        _collect_client_visit_rankings(
            dashboard_result
        )
    )

    raw_worker_cards = tuple(
        getattr(
            dashboard_result,
            "worker_cards",
            (),
        )
        or ()
    )

    worker_ids = _collect_worker_ids(
        ranking_kpis,
        raw_worker_cards,
    )
    brand_ids = _collect_card_brand_ids(
        raw_worker_cards
    )
    brand_ids.update(
        _collect_sales_brand_ids(
            dashboard_result
        )
    )

    brand_ids.update(
        _collect_client_visit_brand_ids(
            client_visit_rankings
        )
    )

    workers_by_id = _load_workers_by_id(
        worker_ids
    )
    brands_by_id = _load_brands_by_id(
        brand_ids
    )

    worker_rankings = _present_worker_rankings(
        ranking_kpis,
        workers_by_id,
    )

    client_visit_presentations = (
        _present_client_visit_rankings(
            client_visit_rankings,
            brands_by_id,
        )
    )

    worker_cards = tuple(
        present_worker_dashboard_card(
            card,
            workers_by_id,
            brands_by_id,
        )
        for card in raw_worker_cards
    )

    sales = getattr(
        dashboard_result,
        "sales",
        None,
    )

    brand_sales_chart = (
        present_brand_sales_chart(
            sales,
            brands_by_id,
        )
        if sales is not None
        else ()
    )

    sales_timeline = (
        present_sales_timeline(sales)
        if sales is not None
        else None
    )

    return {
        **worker_rankings,
        **client_visit_presentations,
        "worker_cards": worker_cards,
        "brand_sales_chart": brand_sales_chart,
        "sales_timeline": sales_timeline,
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
        "filter_form": filter_form,
        "dashboard_result": dashboard_result,
        "summary": summary_presentation,
        "coverage": coverage_presentation,
        "data_quality": data_quality_presentation,
        **worker_presentations,
    }

    return render(
        request,
        DASHBOARD_TEMPLATE_NAME,
        context,
        status=response_status,
    )



def _ask_delisky_error_response(
    *,
    code: str,
    message: str,
    status: int,
    errors=None,
):
    payload = {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
        },
    }

    if errors is not None:
        payload["error"]["fields"] = errors

    return JsonResponse(
        payload,
        status=status,
    )


@manager_required
@require_POST
def ask_delisky_api(request):
    started_at = perf_counter()

    def record_audit(
        *,
        outcome,
        http_status,
        period_start=None,
        period_end=None,
        brand_id=None,
    ):
        duration_ms = max(
            0,
            round(
                (
                    perf_counter()
                    - started_at
                )
                * 1000
            ),
        )

        record_ask_delisky_audit_event(
            user=request.user,
            record=AskDeliskyAuditRecord(
                outcome=outcome,
                http_status=http_status,
                duration_ms=duration_ms,
                period_start=period_start,
                period_end=period_end,
                brand_id=brand_id,
            ),
        )

    form = AskDeliskyForm(
        data=request.POST,
    )

    if not form.is_valid():
        record_audit(
            outcome=(
                AskDeliskyAuditOutcome.INVALID_REQUEST
            ),
            http_status=400,
        )

        return _ask_delisky_error_response(
            code="INVALID_REQUEST",
            message=(
                "\u062a\u062d\u0642\u0642 \u0645\u0646 \u0627\u0644\u0633\u0624\u0627\u0644 "
                "\u0648\u0627\u0644\u0641\u0644\u0627\u062a\u0631 \u062b\u0645 "
                "\u0623\u0639\u062f \u0627\u0644\u0645\u062d\u0627\u0648\u0644\u0629."
            ),
            status=400,
            errors=form.errors.get_json_data(
                escape_html=True
            ),
        )

    selected_brand = form.cleaned_data["brand"]

    period_start = form.cleaned_data[
        "period_start"
    ]
    period_end = form.cleaned_data[
        "period_end"
    ]
    brand_id = (
        selected_brand.pk
        if selected_brand is not None
        else None
    )

    try:
        rate_limit = check_ask_delisky_rate_limit(
            user=request.user,
        )
    except AskDeliskyRateLimitConfigurationError:
        record_audit(
            outcome=(
                AskDeliskyAuditOutcome
                .RATE_LIMIT_CONFIGURATION_ERROR
            ),
            http_status=503,
            period_start=period_start,
            period_end=period_end,
            brand_id=brand_id,
        )

        return _ask_delisky_error_response(
            code="RATE_LIMIT_CONFIGURATION_ERROR",
            message=(
                "\u062a\u0639\u0630\u0631 \u062a\u062d\u0645\u064a\u0644 "
                "\u0625\u0639\u062f\u0627\u062f\u0627\u062a \u0627\u0644\u062d\u0645\u0627\u064a\u0629 "
                "\u0627\u0644\u062e\u0627\u0635\u0629 \u0628\u0640 Ask DELISKY."
            ),
            status=503,
        )

    if not rate_limit.allowed:
        record_audit(
            outcome=(
                AskDeliskyAuditOutcome.RATE_LIMITED
            ),
            http_status=429,
            period_start=period_start,
            period_end=period_end,
            brand_id=brand_id,
        )

        response = _ask_delisky_error_response(
            code="RATE_LIMITED",
            message=(
                "\u062a\u0645 \u0628\u0644\u0648\u063a \u0627\u0644\u062d\u062f \u0627\u0644\u0645\u0624\u0642\u062a "
                "\u0644\u0637\u0644\u0628\u0627\u062a Ask DELISKY. "
                "\u0623\u0639\u062f \u0627\u0644\u0645\u062d\u0627\u0648\u0644\u0629 \u0628\u0639\u062f \u0642\u0644\u064a\u0644."
            ),
            status=429,
        )
        response["Retry-After"] = str(
            rate_limit.retry_after_seconds
        )
        return response

    try:
        response = ask_manager_delisky(
            question=form.cleaned_data["question"],
            period_start=period_start,
            period_end=period_end,
            brand_id=brand_id,
        )
    except AskDeliskyProviderConfigurationError:
        record_audit(
            outcome=(
                AskDeliskyAuditOutcome
                .PROVIDER_CONFIGURATION_ERROR
            ),
            http_status=503,
            period_start=period_start,
            period_end=period_end,
            brand_id=brand_id,
        )

        return _ask_delisky_error_response(
            code="PROVIDER_CONFIGURATION_ERROR",
            message=(
                "\u062a\u0639\u0630\u0631 \u062a\u062d\u0645\u064a\u0644 "
                "\u0625\u0639\u062f\u0627\u062f\u0627\u062a Ask DELISKY."
            ),
            status=503,
        )
    except AskDeliskyProviderDisabledError:
        record_audit(
            outcome=(
                AskDeliskyAuditOutcome.PROVIDER_DISABLED
            ),
            http_status=503,
            period_start=period_start,
            period_end=period_end,
            brand_id=brand_id,
        )

        return _ask_delisky_error_response(
            code="PROVIDER_DISABLED",
            message=(
                "Ask DELISKY "
                "\u063a\u064a\u0631 \u0645\u0641\u0639\u0644 \u062d\u0627\u0644\u064a\u0627."
            ),
            status=503,
        )
    except OllamaTransportError:
        record_audit(
            outcome=(
                AskDeliskyAuditOutcome
                .PROVIDER_UNAVAILABLE
            ),
            http_status=503,
            period_start=period_start,
            period_end=period_end,
            brand_id=brand_id,
        )

        return _ask_delisky_error_response(
            code="PROVIDER_UNAVAILABLE",
            message=(
                "\u062a\u0639\u0630\u0631 \u0627\u0644\u0627\u062a\u0635\u0627\u0644 "
                "\u0628\u0645\u0633\u0627\u0639\u062f Ask DELISKY "
                "\u062d\u0627\u0644\u064a\u0627."
            ),
            status=503,
        )

    record_audit(
        outcome=AskDeliskyAuditOutcome.SUCCESS,
        http_status=200,
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
    )

    return JsonResponse(
        {
            "ok": True,
            "answer": response.answer,
            "provider": response.provider_name,
            "model": response.model_name,
            "context_schema_version": (
                response.context_schema_version
            ),
        }
    )
