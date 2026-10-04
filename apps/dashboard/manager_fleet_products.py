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
from apps.analytics.services.truck_operational_status import (
    determine_truck_operational_status,
)
from apps.analytics.services.truck_resolver import (
    build_truck_code_index,
)
from apps.fleet.models import Truck

from .access import can_use_ai_assistants
from .manager_filters import (
    build_filter_form,
    manager_filter_query,
    selected_brand_id,
)


FLEET_PRODUCTS_TEMPLATE_NAME = (
    "dashboard/manager_fleet_products.html"
)
SLOW_MOVING_RATIO = Decimal("0.25")
PRODUCT_LIMIT_PER_TRUCK = 10
TABLE_LIMIT = 100


@dataclass(frozen=True, slots=True)
class ProductMovementRow:
    brand_id: int
    truck_id: int
    truck_name: str
    article: str
    article_normalized: str
    supplied_quantity: Decimal
    sold_quantity: Decimal
    quantity_gap: Decimal
    sold_to_supplied_percentage: Decimal | None
    has_sales_coverage: bool


@dataclass(frozen=True, slots=True)
class TruckProductGroup:
    truck_id: int
    truck_name: str
    product_count: int
    products: tuple[ProductMovementRow, ...]


@dataclass(frozen=True, slots=True)
class TruckStatusRow:
    truck_id: int
    truck_name: str
    status: str
    status_label: str
    sales_activity_count: int
    sales_total: Decimal
    authoritative_stopped_count: int
    possible_stopped_count: int


@dataclass(frozen=True, slots=True)
class TruckDetailPresentation:
    truck_id: int
    truck_name: str
    total_sales: Decimal
    sale_record_count: int
    supplied_quantity: Decimal
    sold_quantity: Decimal
    not_sold_product_count: int
    slow_moving_product_count: int
    has_sales_coverage: bool


@dataclass(frozen=True, slots=True)
class ProductTruckRow:
    truck_id: int
    truck_name: str
    supplied_quantity: Decimal
    sold_quantity: Decimal
    quantity_gap: Decimal
    sold_to_supplied_percentage: Decimal | None
    has_sales_coverage: bool


def _load_trucks(truck_ids):
    if not truck_ids:
        return {}

    return {
        truck.pk: truck
        for truck in Truck.objects.filter(
            pk__in=truck_ids,
        ).select_related("distribution_brand")
    }


def _truck_name(truck_id, trucks):
    truck = trucks.get(truck_id)

    if truck is None:
        return f"الشاحنة رقم {truck_id}"

    return (
        truck.internal_code
        or truck.registration_number
        or f"الشاحنة رقم {truck_id}"
    )


def _percentage_ratio(quantities):
    if not quantities.has_sales_coverage:
        return None

    ratio = quantities.sold_to_supplied_ratio

    if ratio is None:
        return None

    return ratio * Decimal("100")


def _movement_row(item, trucks):
    quantities = item.quantities

    return ProductMovementRow(
        brand_id=item.brand_id,
        truck_id=item.truck_id,
        truck_name=_truck_name(
            item.truck_id,
            trucks,
        ),
        article=item.article,
        article_normalized=item.article_normalized,
        supplied_quantity=quantities.supplied_quantity,
        sold_quantity=quantities.sold_quantity,
        quantity_gap=quantities.analytical_quantity_gap,
        sold_to_supplied_percentage=(
            _percentage_ratio(quantities)
        ),
        has_sales_coverage=(
            quantities.has_sales_coverage
        ),
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


def _not_sold_groups(product_result):
    grouped = defaultdict(list)

    for item in product_result.truck_products:
        if item.quantities.is_not_sold:
            grouped[item.truck_id].append(item)

    trucks = _load_trucks(set(grouped))
    groups = []

    for truck_id, products in grouped.items():
        ranked = sorted(
            products,
            key=lambda item: (
                -item.quantities.supplied_quantity,
                item.article_normalized,
            ),
        )
        groups.append(
            TruckProductGroup(
                truck_id=truck_id,
                truck_name=_truck_name(
                    truck_id,
                    trucks,
                ),
                product_count=len(ranked),
                products=tuple(
                    _movement_row(item, trucks)
                    for item in ranked[
                        :PRODUCT_LIMIT_PER_TRUCK
                    ]
                ),
            )
        )

    return tuple(
        sorted(
            groups,
            key=lambda group: (
                -group.product_count,
                group.truck_name.casefold(),
            ),
        )
    )


def _slow_moving_rows(product_result):
    candidates = [
        item
        for item in product_result.truck_products
        if (
            item.quantities.has_sales_coverage
            and item.quantities.supplied_quantity > 0
            and item.quantities.sold_quantity > 0
            and item.quantities.sold_to_supplied_ratio
            is not None
            and item.quantities.sold_to_supplied_ratio
            <= SLOW_MOVING_RATIO
        )
    ]
    trucks = _load_trucks(
        {item.truck_id for item in candidates}
    )

    return tuple(
        _movement_row(item, trucks)
        for item in sorted(
            candidates,
            key=lambda item: (
                item.quantities.sold_to_supplied_ratio,
                -item.quantities.supplied_quantity,
                item.article_normalized,
                item.truck_id,
            ),
        )[:TABLE_LIMIT]
    )


def _load_vs_sales_rows(product_result):
    candidates = [
        item
        for item in product_result.truck_products
        if item.quantities.supplied_quantity > 0
    ]
    trucks = _load_trucks(
        {item.truck_id for item in candidates}
    )

    return tuple(
        _movement_row(item, trucks)
        for item in sorted(
            candidates,
            key=lambda item: (
                not item.quantities.has_sales_coverage,
                (
                    item.quantities.sold_to_supplied_ratio
                    if (
                        item.quantities.has_sales_coverage
                        and item.quantities.sold_to_supplied_ratio
                        is not None
                    )
                    else Decimal("999999")
                ),
                -item.quantities.supplied_quantity,
                item.article_normalized,
                item.truck_id,
            ),
        )[:TABLE_LIMIT]
    )


def _status_rows(
    *,
    period_start,
    period_end,
    brand_id,
):
    truck_index = build_truck_code_index()
    result = determine_truck_operational_status(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
        truck_index=truck_index,
    )
    trucks = _load_trucks(
        {state.truck_id for state in result.states}
    )
    labels = {
        "ACTIVE": "نشطة",
        "CONFIRMED_STOPPED": "متوقفة مؤكدة",
        "POSSIBLE_STOPPED": "توقف محتمل",
        "CONFLICTING_EVIDENCE": "أدلة متعارضة",
    }

    return tuple(
        TruckStatusRow(
            truck_id=state.truck_id,
            truck_name=_truck_name(
                state.truck_id,
                trucks,
            ),
            status=str(state.status),
            status_label=labels.get(
                str(state.status),
                str(state.status),
            ),
            sales_activity_count=(
                state.sales_activity_count
            ),
            sales_total=state.sales_total,
            authoritative_stopped_count=(
                state.authoritative_stopped_count
            ),
            possible_stopped_count=(
                state.possible_stopped_count
            ),
        )
        for state in result.states
    )


def _truck_detail(
    *,
    product_result,
    period_start,
    period_end,
    brand_id,
    selected_truck_id,
):
    products = tuple(
        item
        for item in product_result.truck_products
        if item.truck_id == selected_truck_id
    )
    trucks = _load_trucks({selected_truck_id})
    sales = aggregate_sales(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
    )
    sales_item = next(
        (
            item
            for item in sales.by_truck
            if item.truck_id == selected_truck_id
        ),
        None,
    )
    has_sales_coverage = bool(products) and all(
        item.quantities.has_sales_coverage
        for item in products
    )

    return TruckDetailPresentation(
        truck_id=selected_truck_id,
        truck_name=_truck_name(
            selected_truck_id,
            trucks,
        ),
        total_sales=(
            sales_item.metrics.total_sales
            if sales_item is not None
            else Decimal("0")
        ),
        sale_record_count=(
            sales_item.metrics.sale_record_count
            if sales_item is not None
            else 0
        ),
        supplied_quantity=sum(
            (
                item.quantities.supplied_quantity
                for item in products
            ),
            Decimal("0"),
        ),
        sold_quantity=sum(
            (
                item.quantities.sold_quantity
                for item in products
            ),
            Decimal("0"),
        ),
        not_sold_product_count=sum(
            1
            for item in products
            if item.quantities.is_not_sold
        ),
        slow_moving_product_count=sum(
            1
            for item in products
            if (
                item.quantities.has_sales_coverage
                and item.quantities.supplied_quantity > 0
                and item.quantities.sold_quantity > 0
                and item.quantities.sold_to_supplied_ratio
                is not None
                and item.quantities.sold_to_supplied_ratio
                <= SLOW_MOVING_RATIO
            )
        ),
        has_sales_coverage=has_sales_coverage,
    )


def _product_rows(
    *,
    product_result,
    article_normalized,
):
    matches = tuple(
        item
        for item in product_result.truck_products
        if item.article_normalized == article_normalized
    )
    trucks = _load_trucks(
        {item.truck_id for item in matches}
    )

    return tuple(
        ProductTruckRow(
            truck_id=item.truck_id,
            truck_name=_truck_name(
                item.truck_id,
                trucks,
            ),
            supplied_quantity=(
                item.quantities.supplied_quantity
            ),
            sold_quantity=(
                item.quantities.sold_quantity
            ),
            quantity_gap=(
                item.quantities.analytical_quantity_gap
            ),
            sold_to_supplied_percentage=(
                _percentage_ratio(item.quantities)
            ),
            has_sales_coverage=(
                item.quantities.has_sales_coverage
            ),
        )
        for item in sorted(
            matches,
            key=lambda item: (
                not item.quantities.has_sales_coverage,
                -item.quantities.sold_quantity,
                item.truck_id,
            ),
        )
    )


def build_fleet_product_section_response(
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
        "not_sold_groups": (),
        "movement_rows": (),
        "truck_status_rows": (),
        "truck_choices": (),
        "selected_truck_id": None,
        "truck_detail": None,
        "product_choices": (),
        "selected_product": None,
        "product_rows": (),
    }

    if filter_requested:
        if filter_form.is_valid():
            period_start = filter_form.cleaned_data[
                "period_start"
            ]
            period_end = filter_form.cleaned_data[
                "period_end"
            ]
            brand_id = selected_brand_id(filter_form)

            if item == "truck-status":
                context_data["truck_status_rows"] = (
                    _status_rows(
                        period_start=period_start,
                        period_end=period_end,
                        brand_id=brand_id,
                    )
                )
            else:
                product_result = _build_product_result(
                    period_start=period_start,
                    period_end=period_end,
                    brand_id=brand_id,
                )

                if item == "not-sold":
                    context_data["not_sold_groups"] = (
                        _not_sold_groups(product_result)
                    )

                elif item == "slow-moving":
                    context_data["movement_rows"] = (
                        _slow_moving_rows(product_result)
                    )

                elif item == "load-vs-sales":
                    context_data["movement_rows"] = (
                        _load_vs_sales_rows(product_result)
                    )

                elif item == "truck":
                    truck_ids = sorted({
                        product.truck_id
                        for product in product_result.truck_products
                    })
                    trucks = _load_trucks(set(truck_ids))
                    context_data["truck_choices"] = tuple(
                        (
                            truck_id,
                            _truck_name(truck_id, trucks),
                        )
                        for truck_id in truck_ids
                    )
                    raw_truck_id = request.GET.get("truck")

                    if raw_truck_id:
                        try:
                            selected_truck_id = int(
                                raw_truck_id
                            )
                        except (TypeError, ValueError):
                            selected_truck_id = None

                        if selected_truck_id in truck_ids:
                            context_data[
                                "selected_truck_id"
                            ] = selected_truck_id
                            context_data["truck_detail"] = (
                                _truck_detail(
                                    product_result=product_result,
                                    period_start=period_start,
                                    period_end=period_end,
                                    brand_id=brand_id,
                                    selected_truck_id=(
                                        selected_truck_id
                                    ),
                                )
                            )

                elif item == "product":
                    products = {}

                    for product in product_result.truck_products:
                        products.setdefault(
                            product.article_normalized,
                            product.article,
                        )

                    context_data["product_choices"] = tuple(
                        sorted(
                            products.items(),
                            key=lambda entry: (
                                entry[1].casefold(),
                                entry[0],
                            ),
                        )
                    )
                    selected_product = request.GET.get(
                        "product"
                    )

                    if selected_product in products:
                        context_data["selected_product"] = (
                            products[selected_product]
                        )
                        context_data["product_rows"] = (
                            _product_rows(
                                product_result=product_result,
                                article_normalized=(
                                    selected_product
                                ),
                            )
                        )
        else:
            response_status = 400

    context = {
        "active_section": "fleet-products",
        "active_item": f"fleet-products-{item}",
        "manager_query": manager_filter_query(request),
        "filter_reset_url": request.path,
        "filter_requested": filter_requested,
        "filter_form": filter_form,
        "can_use_ai_assistants": can_use_ai_assistants(
            request.user
        ),
        "section_label": "الشاحنات والمنتجات",
        "item_label": item_label,
        "fleet_product_item": item,
        "slow_moving_percentage": (
            SLOW_MOVING_RATIO * Decimal("100")
        ),
        **context_data,
    }

    return render(
        request,
        FLEET_PRODUCTS_TEMPLATE_NAME,
        context,
        status=response_status,
    )
