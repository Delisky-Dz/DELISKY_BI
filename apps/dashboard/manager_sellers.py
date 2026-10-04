from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from django.shortcuts import render

from apps.analytics.services.assignment_resolver import (
    build_assignment_index,
)
from apps.analytics.services.items_aggregation import (
    aggregate_items,
)
from apps.analytics.services.pos_visit_aggregation import (
    aggregate_pos_visits,
)
from apps.analytics.services.product_performance import (
    combine_product_performance,
)
from apps.analytics.services.sales_aggregation import (
    aggregate_sales,
)
from apps.analytics.services.stock_flow_aggregation import (
    aggregate_chargement,
    aggregate_opening_stock,
)
from apps.analytics.services.truck_resolver import (
    build_truck_code_index,
)
from apps.workforce.models import Worker

from .access import can_use_ai_assistants
from .manager_filters import (
    build_filter_form,
    manager_filter_query,
    selected_brand_id,
)
from .manager_identity import worker_display_identity


SELLERS_TEMPLATE_NAME = "dashboard/manager_sellers.html"
PERCENT_MULTIPLIER = Decimal("100")
VISIT_MINIMUM_POS_RECORDS = 3
PRODUCT_LIMIT_PER_SELLER = 10


@dataclass(frozen=True, slots=True)
class SellerPerformanceRow:
    worker_id: int
    worker_name: str
    subtitle: str | None
    total_sales: Decimal
    sale_record_count: int
    positive_sale_record_count: int
    pos_record_count: int
    visited_record_count: int
    not_visited_record_count: int
    visit_success_percentage: Decimal | None


@dataclass(frozen=True, slots=True)
class SellerNotSoldProductRow:
    article: str
    supplied_quantity: Decimal
    sold_quantity: Decimal


@dataclass(frozen=True, slots=True)
class SellerNotSoldGroup:
    worker_id: int
    worker_name: str
    subtitle: str | None
    product_count: int
    products: tuple[SellerNotSoldProductRow, ...]


def _load_workers(worker_ids):
    if not worker_ids:
        return {}

    return {
        worker.pk: worker
        for worker in Worker.objects.filter(
            pk__in=worker_ids,
        )
    }


def _visit_percentage(metrics):
    if (
        metrics is None
        or metrics.total_record_count == 0
    ):
        return None

    return (
        Decimal(metrics.visited_record_count)
        / Decimal(metrics.total_record_count)
        * PERCENT_MULTIPLIER
    )


def _build_seller_rows(
    *,
    sales=None,
    visits=None,
) -> tuple[SellerPerformanceRow, ...]:
    sales_by_worker = {
        item.worker_id: item.metrics
        for item in (
            getattr(sales, "by_worker", ()) or ()
        )
    }
    visits_by_worker = {
        item.worker_id: item.metrics
        for item in (
            getattr(visits, "by_worker", ()) or ()
        )
    }

    worker_ids = set(sales_by_worker)
    worker_ids.update(visits_by_worker)
    workers_by_id = _load_workers(worker_ids)

    rows = []

    for worker_id in worker_ids:
        sales_metrics = sales_by_worker.get(worker_id)
        visit_metrics = visits_by_worker.get(worker_id)
        worker_name, subtitle = worker_display_identity(
            worker_id,
            workers_by_id.get(worker_id),
        )

        rows.append(
            SellerPerformanceRow(
                worker_id=worker_id,
                worker_name=worker_name,
                subtitle=subtitle,
                total_sales=(
                    sales_metrics.total_sales
                    if sales_metrics is not None
                    else Decimal("0")
                ),
                sale_record_count=(
                    sales_metrics.sale_record_count
                    if sales_metrics is not None
                    else 0
                ),
                positive_sale_record_count=(
                    sales_metrics.positive_sale_record_count
                    if sales_metrics is not None
                    else 0
                ),
                pos_record_count=(
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
                visit_success_percentage=(
                    _visit_percentage(visit_metrics)
                ),
            )
        )

    return tuple(rows)


def _rank_sellers(rows, metric):
    if metric == "visits":
        candidates = [
            row
            for row in rows
            if row.pos_record_count > 0
        ]
        return tuple(
            sorted(
                candidates,
                key=lambda row: (
                    -row.visited_record_count,
                    -row.pos_record_count,
                    row.worker_name.casefold(),
                ),
            )
        )

    if metric == "success":
        candidates = [
            row
            for row in rows
            if (
                row.pos_record_count
                >= VISIT_MINIMUM_POS_RECORDS
                and row.visit_success_percentage
                is not None
            )
        ]
        return tuple(
            sorted(
                candidates,
                key=lambda row: (
                    -row.visit_success_percentage,
                    -row.visited_record_count,
                    row.worker_name.casefold(),
                ),
            )
        )

    candidates = [
        row
        for row in rows
        if row.sale_record_count > 0
    ]
    return tuple(
        sorted(
            candidates,
            key=lambda row: (
                -row.total_sales,
                -row.positive_sale_record_count,
                row.worker_name.casefold(),
            ),
        )
    )


def _lowest_sales(rows):
    return tuple(
        sorted(
            (
                row
                for row in rows
                if row.sale_record_count > 0
            ),
            key=lambda row: (
                row.total_sales,
                row.positive_sale_record_count,
                row.worker_name.casefold(),
            ),
        )
    )


def _build_product_result(
    *,
    period_start,
    period_end,
    brand_id,
):
    truck_index = build_truck_code_index()
    assignment_index = build_assignment_index()

    items = aggregate_items(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
        truck_index=truck_index,
        assignment_index=assignment_index,
    )
    opening_stock = aggregate_opening_stock(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
        truck_index=truck_index,
        assignment_index=assignment_index,
    )
    chargement = aggregate_chargement(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
        truck_index=truck_index,
        assignment_index=assignment_index,
    )

    return combine_product_performance(
        items_result=items,
        opening_stock_result=opening_stock,
        chargement_result=chargement,
    )


def _present_not_sold_groups(product_result):
    grouped = defaultdict(list)

    for item in product_result.worker_products:
        if item.quantities.is_not_sold:
            grouped[item.worker_id].append(item)

    workers_by_id = _load_workers(set(grouped))
    groups = []

    for worker_id, products in grouped.items():
        worker_name, subtitle = worker_display_identity(
            worker_id,
            workers_by_id.get(worker_id),
        )
        ranked_products = sorted(
            products,
            key=lambda item: (
                -item.quantities.supplied_quantity,
                item.article_normalized,
            ),
        )

        groups.append(
            SellerNotSoldGroup(
                worker_id=worker_id,
                worker_name=worker_name,
                subtitle=subtitle,
                product_count=len(ranked_products),
                products=tuple(
                    SellerNotSoldProductRow(
                        article=item.article,
                        supplied_quantity=(
                            item.quantities.supplied_quantity
                        ),
                        sold_quantity=(
                            item.quantities.sold_quantity
                        ),
                    )
                    for item in ranked_products[
                        :PRODUCT_LIMIT_PER_SELLER
                    ]
                ),
            )
        )

    return tuple(
        sorted(
            groups,
            key=lambda group: (
                -group.product_count,
                group.worker_name.casefold(),
            ),
        )
    )


def build_seller_section_response(
    request,
    *,
    item,
    item_label,
):
    filter_requested, filter_form = (
        build_filter_form(request)
    )
    response_status = 200
    rows = ()
    not_sold_groups = ()
    selected_worker_id = None
    selected_worker = None
    ranking_metric = request.GET.get(
        "metric",
        "sales",
    )

    if ranking_metric not in {
        "sales",
        "visits",
        "success",
    }:
        ranking_metric = "sales"

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

            if item in {"rankings", "visits"}:
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
                base_rows = _build_seller_rows(
                    sales=sales,
                    visits=visits,
                )

                if item == "rankings":
                    rows = _rank_sellers(
                        base_rows,
                        ranking_metric,
                    )
                else:
                    rows = _rank_sellers(
                        base_rows,
                        "success",
                    )

            elif item == "lowest-sales":
                sales = aggregate_sales(
                    period_start=period_start,
                    period_end=period_end,
                    brand_id=brand_id,
                )
                rows = _lowest_sales(
                    _build_seller_rows(
                        sales=sales,
                    )
                )

            elif item == "not-sold":
                product_result = _build_product_result(
                    period_start=period_start,
                    period_end=period_end,
                    brand_id=brand_id,
                )
                not_sold_groups = (
                    _present_not_sold_groups(
                        product_result
                    )
                )

            elif item == "card":
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
                rows = _build_seller_rows(
                    sales=sales,
                    visits=visits,
                )

                raw_worker_id = request.GET.get("worker")

                if raw_worker_id:
                    try:
                        selected_worker_id = int(
                            raw_worker_id
                        )
                    except (TypeError, ValueError):
                        selected_worker_id = None

                selected_worker = next(
                    (
                        row
                        for row in rows
                        if row.worker_id
                        == selected_worker_id
                    ),
                    None,
                )
        else:
            response_status = 400

    context = {
        "active_section": "sellers",
        "active_item": f"sellers-{item}",
        "manager_query": manager_filter_query(
            request
        ),
        "filter_reset_url": request.path,
        "filter_requested": filter_requested,
        "filter_form": filter_form,
        "can_use_ai_assistants": can_use_ai_assistants(
            request.user
        ),
        "section_label": "البائعون",
        "item_label": item_label,
        "seller_item": item,
        "seller_rows": rows,
        "ranking_metric": ranking_metric,
        "not_sold_groups": not_sold_groups,
        "selected_worker_id": selected_worker_id,
        "selected_worker": selected_worker,
    }

    return render(
        request,
        SELLERS_TEMPLATE_NAME,
        context,
        status=response_status,
    )
