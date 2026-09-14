from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from urllib.parse import quote

from django.shortcuts import render

from apps.analytics.services.assignment_resolver import (
    build_assignment_index,
)
from apps.analytics.services.pos_visit_aggregation import (
    aggregate_pos_visits,
)
from apps.analytics.services.sales_aggregation import (
    aggregate_sales,
)
from apps.analytics.services.truck_resolver import (
    build_truck_code_index,
)
from apps.imports.models import DistributionBrand

from .access import can_use_ai_assistants
from .manager_filters import (
    build_filter_form,
    manager_filter_query,
    selected_brand_id,
)


CLIENTS_TEMPLATE_NAME = "dashboard/manager_clients.html"
PERCENT_MULTIPLIER = Decimal("100")
DECLINE_THRESHOLD = Decimal("0.30")
CLIENT_LIMIT = 50


@dataclass(frozen=True, slots=True)
class ClientSalesRow:
    brand_id: int
    brand_name: str
    client_name: str
    client_normalized: str
    total_sales: Decimal
    sale_record_count: int
    visit_record_count: int = 0
    visited_record_count: int = 0
    not_visited_record_count: int = 0

    @property
    def key(self) -> str:
        return f"{self.brand_id}|{self.client_normalized}"

    @property
    def quoted_key(self) -> str:
        return quote(self.key, safe="")


@dataclass(frozen=True, slots=True)
class ClientTrendRow:
    brand_id: int
    brand_name: str
    client_name: str
    client_normalized: str
    previous_sales: Decimal
    current_sales: Decimal
    change_percentage: Decimal | None
    previous_sale_record_count: int
    current_sale_record_count: int

    @property
    def key(self) -> str:
        return f"{self.brand_id}|{self.client_normalized}"


@dataclass(frozen=True, slots=True)
class ClientVisitRow:
    brand_id: int
    brand_name: str
    client_name: str
    total_record_count: int
    visited_record_count: int
    not_visited_record_count: int
    unique_client_day_count: int
    visit_success_percentage: Decimal | None


@dataclass(frozen=True, slots=True)
class ClientOverviewPresentation:
    distinct_client_count: int
    purchasing_client_count: int
    total_visit_records: int
    visited_record_count: int
    not_visited_record_count: int
    visit_success_percentage: Decimal | None


def _brand_names(*results):
    brand_ids = set()

    for result in results:
        if result is None:
            continue

        for attribute in (
            "by_brand_client",
        ):
            for item in (
                getattr(result, attribute, ()) or ()
            ):
                brand_ids.add(item.brand_id)

    brands = DistributionBrand.objects.filter(
        pk__in=brand_ids,
    )

    return {
        brand.pk: (
            brand.name
            or brand.code
        )
        for brand in brands
    }


def _brand_name(brand_id, names):
    return names.get(
        brand_id,
        f"العلامة رقم {brand_id}",
    )


def _visit_success_percentage(metrics):
    if metrics.total_record_count == 0:
        return None

    return (
        Decimal(metrics.visited_record_count)
        / Decimal(metrics.total_record_count)
        * PERCENT_MULTIPLIER
    )


def _client_sales_rows(
    sales,
    *,
    visits=None,
):
    brand_names = _brand_names(sales, visits)
    visit_map = {
        (item.brand_id, item.client_normalized): item.metrics
        for item in (
            getattr(visits, "by_brand_client", ()) or ()
        )
    }
    rows = []

    for item in sales.by_brand_client:
        visit_metrics = visit_map.get(
            (
                item.brand_id,
                item.client_normalized,
            )
        )

        rows.append(
            ClientSalesRow(
                brand_id=item.brand_id,
                brand_name=_brand_name(
                    item.brand_id,
                    brand_names,
                ),
                client_name=item.client,
                client_normalized=(
                    item.client_normalized
                ),
                total_sales=item.metrics.total_sales,
                sale_record_count=(
                    item.metrics.sale_record_count
                ),
                visit_record_count=(
                    visit_metrics.total_record_count
                    if visit_metrics is not None
                    else 0
                ),
                visited_record_count=(
                    visit_metrics.visited_record_count
                    if visit_metrics is not None
                    else 0
                ),
                not_visited_record_count=(
                    visit_metrics.not_visited_record_count
                    if visit_metrics is not None
                    else 0
                ),
            )
        )

    return tuple(rows)


def _top_clients(sales, *, visits=None):
    return tuple(
        sorted(
            _client_sales_rows(
                sales,
                visits=visits,
            ),
            key=lambda row: (
                -row.total_sales,
                -row.sale_record_count,
                row.client_normalized,
                row.brand_id,
            ),
        )[:CLIENT_LIMIT]
    )


def _client_visit_rows(visits):
    brand_names = _brand_names(visits)
    rows = []

    for item in visits.by_brand_client:
        rows.append(
            ClientVisitRow(
                brand_id=item.brand_id,
                brand_name=_brand_name(
                    item.brand_id,
                    brand_names,
                ),
                client_name=item.client,
                total_record_count=(
                    item.metrics.total_record_count
                ),
                visited_record_count=(
                    item.metrics.visited_record_count
                ),
                not_visited_record_count=(
                    item.metrics.not_visited_record_count
                ),
                unique_client_day_count=(
                    item.metrics.unique_client_day_count
                ),
                visit_success_percentage=(
                    _visit_success_percentage(
                        item.metrics
                    )
                ),
            )
        )

    return tuple(rows)


def _previous_period(period_start, period_end):
    if (
        period_start is None
        or period_end is None
    ):
        return None

    day_count = (
        period_end - period_start
    ).days + 1
    previous_end = period_start - timedelta(days=1)
    previous_start = (
        previous_end
        - timedelta(days=day_count - 1)
    )

    return previous_start, previous_end


def _trend_rows(
    *,
    current_sales,
    previous_sales,
):
    brand_names = _brand_names(
        current_sales,
        previous_sales,
    )
    current_map = {
        (item.brand_id, item.client_normalized): item
        for item in current_sales.by_brand_client
    }
    previous_map = {
        (item.brand_id, item.client_normalized): item
        for item in previous_sales.by_brand_client
    }
    keys = set(previous_map)
    keys.update(current_map)
    rows = []

    for key in keys:
        current = current_map.get(key)
        previous = previous_map.get(key)
        current_total = (
            current.metrics.total_sales
            if current is not None
            else Decimal("0")
        )
        previous_total = (
            previous.metrics.total_sales
            if previous is not None
            else Decimal("0")
        )

        if previous_total > 0:
            change_percentage = (
                (current_total - previous_total)
                / previous_total
                * PERCENT_MULTIPLIER
            )
        else:
            change_percentage = None

        source = current or previous

        rows.append(
            ClientTrendRow(
                brand_id=source.brand_id,
                brand_name=_brand_name(
                    source.brand_id,
                    brand_names,
                ),
                client_name=source.client,
                client_normalized=(
                    source.client_normalized
                ),
                previous_sales=previous_total,
                current_sales=current_total,
                change_percentage=(
                    change_percentage
                ),
                previous_sale_record_count=(
                    previous.metrics.sale_record_count
                    if previous is not None
                    else 0
                ),
                current_sale_record_count=(
                    current.metrics.sale_record_count
                    if current is not None
                    else 0
                ),
            )
        )

    return tuple(rows)


def _declining_clients(rows):
    threshold = (
        -DECLINE_THRESHOLD
        * PERCENT_MULTIPLIER
    )

    return tuple(
        sorted(
            (
                row
                for row in rows
                if (
                    row.previous_sales > 0
                    and row.current_sales > 0
                    and row.change_percentage
                    is not None
                    and row.change_percentage
                    <= threshold
                )
            ),
            key=lambda row: (
                row.change_percentage,
                -row.previous_sales,
                row.client_normalized,
            ),
        )
    )


def _stopped_clients(rows):
    return tuple(
        sorted(
            (
                row
                for row in rows
                if (
                    row.previous_sales > 0
                    and row.current_sales == 0
                )
            ),
            key=lambda row: (
                -row.previous_sales,
                row.client_normalized,
            ),
        )
    )


def _visited_without_sales(
    *,
    sales,
    visits,
):
    sales_keys = {
        (item.brand_id, item.client_normalized)
        for item in sales.by_brand_client
        if item.metrics.total_sales > 0
    }
    brand_names = _brand_names(sales, visits)
    rows = []

    for item in visits.by_brand_client:
        key = (
            item.brand_id,
            item.client_normalized,
        )

        if (
            item.metrics.visited_record_count <= 0
            or key in sales_keys
        ):
            continue

        rows.append(
            ClientVisitRow(
                brand_id=item.brand_id,
                brand_name=_brand_name(
                    item.brand_id,
                    brand_names,
                ),
                client_name=item.client,
                total_record_count=(
                    item.metrics.total_record_count
                ),
                visited_record_count=(
                    item.metrics.visited_record_count
                ),
                not_visited_record_count=(
                    item.metrics.not_visited_record_count
                ),
                unique_client_day_count=(
                    item.metrics.unique_client_day_count
                ),
                visit_success_percentage=(
                    _visit_success_percentage(
                        item.metrics
                    )
                ),
            )
        )

    return tuple(
        sorted(
            rows,
            key=lambda row: (
                -row.visited_record_count,
                -row.total_record_count,
                row.client_name.casefold(),
            ),
        )
    )


def _overview(sales, visits):
    return ClientOverviewPresentation(
        distinct_client_count=len(
            visits.by_brand_client
        ),
        purchasing_client_count=sum(
            1
            for item in sales.by_brand_client
            if item.metrics.total_sales > 0
        ),
        total_visit_records=(
            visits.overall.total_record_count
        ),
        visited_record_count=(
            visits.overall.visited_record_count
        ),
        not_visited_record_count=(
            visits.overall.not_visited_record_count
        ),
        visit_success_percentage=(
            _visit_success_percentage(
                visits.overall
            )
        ),
    )


def build_client_section_response(
    request,
    *,
    item,
    item_label,
):
    filter_requested, filter_form = (
        build_filter_form(request)
    )
    response_status = 200
    context_data = {
        "client_overview": None,
        "client_rows": (),
        "trend_rows": (),
        "visit_rows": (),
        "comparison_period": None,
        "comparison_available": True,
        "selected_client": None,
    }

    if filter_requested:
        if filter_form.is_valid():
            period_start = filter_form.cleaned_data[
                "period_start"
            ]
            period_end = filter_form.cleaned_data[
                "period_end"
            ]
            brand_id = selected_brand_id(
                filter_form
            )
            truck_index = build_truck_code_index()
            assignment_index = build_assignment_index()

            current_sales = None
            current_visits = None

            if item in {
                "overview",
                "top",
                "declining",
                "stopped",
                "visited-no-sale",
                "card",
            }:
                current_sales = aggregate_sales(
                    period_start=period_start,
                    period_end=period_end,
                    brand_id=brand_id,
                    truck_index=truck_index,
                    assignment_index=assignment_index,
                )

            if item in {
                "overview",
                "visited-no-sale",
                "visits",
                "card",
            }:
                current_visits = aggregate_pos_visits(
                    period_start=period_start,
                    period_end=period_end,
                    brand_id=brand_id,
                    truck_index=truck_index,
                    assignment_index=assignment_index,
                )

            if item == "overview":
                context_data["client_overview"] = (
                    _overview(
                        current_sales,
                        current_visits,
                    )
                )
                context_data["client_rows"] = (
                    _top_clients(
                        current_sales,
                        visits=current_visits,
                    )[:10]
                )

            elif item == "top":
                context_data["client_rows"] = (
                    _top_clients(current_sales)
                )

            elif item in {"declining", "stopped"}:
                previous_period = _previous_period(
                    period_start,
                    period_end,
                )

                if previous_period is None:
                    context_data[
                        "comparison_available"
                    ] = False
                else:
                    previous_start, previous_end = (
                        previous_period
                    )
                    previous_sales = aggregate_sales(
                        period_start=previous_start,
                        period_end=previous_end,
                        brand_id=brand_id,
                        truck_index=truck_index,
                        assignment_index=assignment_index,
                    )
                    context_data[
                        "comparison_period"
                    ] = previous_period

                    if (
                        previous_sales.included_row_count
                        == 0
                    ):
                        context_data[
                            "comparison_available"
                        ] = False
                    else:
                        trends = _trend_rows(
                            current_sales=current_sales,
                            previous_sales=previous_sales,
                        )
                        context_data["trend_rows"] = (
                            _declining_clients(trends)
                            if item == "declining"
                            else _stopped_clients(trends)
                        )

            elif item == "visited-no-sale":
                context_data["visit_rows"] = (
                    _visited_without_sales(
                        sales=current_sales,
                        visits=current_visits,
                    )
                )

            elif item == "visits":
                context_data["visit_rows"] = tuple(
                    sorted(
                        _client_visit_rows(
                            current_visits
                        ),
                        key=lambda row: (
                            -row.not_visited_record_count,
                            -row.total_record_count,
                            row.client_name.casefold(),
                        ),
                    )[:CLIENT_LIMIT]
                )

            elif item == "card":
                rows = _top_clients(
                    current_sales,
                    visits=current_visits,
                )
                context_data["client_rows"] = rows
                selected_key = request.GET.get(
                    "client"
                )
                context_data["selected_client"] = (
                    next(
                        (
                            row
                            for row in rows
                            if row.key == selected_key
                        ),
                        None,
                    )
                )
        else:
            response_status = 400

    context = {
        "active_section": "clients",
        "active_item": f"clients-{item}",
        "manager_query": manager_filter_query(
            request
        ),
        "filter_reset_url": request.path,
        "filter_requested": filter_requested,
        "filter_form": filter_form,
        "can_use_ai_assistants": can_use_ai_assistants(
            request.user
        ),
        "section_label": "الزبائن",
        "item_label": item_label,
        "client_item": item,
        "decline_threshold_percentage": (
            DECLINE_THRESHOLD
            * PERCENT_MULTIPLIER
        ),
        **context_data,
    }

    return render(
        request,
        CLIENTS_TEMPLATE_NAME,
        context,
        status=response_status,
    )
