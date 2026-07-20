from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from apps.imports.models import ImportReportType

from .assignment_resolver import build_assignment_index
from .items_aggregation import (
    ItemsAggregationResult,
    aggregate_items,
)
from .stock_flow_aggregation import (
    StockFlowAggregationResult,
    aggregate_chargement,
    aggregate_opening_stock,
)
from .truck_resolver import build_truck_code_index


@dataclass(frozen=True, slots=True)
class ProductQuantityContext:
    opening_quantity: Decimal
    chargement_quantity: Decimal
    sold_quantity: Decimal

    @property
    def supplied_quantity(self) -> Decimal:
        return (
            self.opening_quantity
            + self.chargement_quantity
        )

    @property
    def analytical_quantity_gap(self) -> Decimal:
        """
        Analytical difference only.

        This is not asserted to be an exact closing stock because
        the available source reports may not include every stock
        movement, return, transfer or adjustment.
        """
        return (
            self.supplied_quantity
            - self.sold_quantity
        )

    @property
    def is_not_sold(self) -> bool:
        return (
            self.supplied_quantity > 0
            and self.sold_quantity == 0
        )

    @property
    def is_sold(self) -> bool:
        return self.sold_quantity > 0

    @property
    def is_sold_without_supply_context(self) -> bool:
        return (
            self.sold_quantity > 0
            and self.supplied_quantity == 0
        )

    @property
    def has_negative_quantity_gap(self) -> bool:
        return self.analytical_quantity_gap < 0

    @property
    def sold_to_supplied_ratio(
        self,
    ) -> Decimal | None:
        if self.supplied_quantity <= 0:
            return None

        return (
            self.sold_quantity
            / self.supplied_quantity
        )


@dataclass(frozen=True, slots=True)
class WorkerProductPerformance:
    brand_id: int
    worker_id: int
    article: str
    article_normalized: str
    quantities: ProductQuantityContext


@dataclass(frozen=True, slots=True)
class TruckProductPerformance:
    brand_id: int
    truck_id: int
    article: str
    article_normalized: str
    quantities: ProductQuantityContext


@dataclass(frozen=True, slots=True)
class ProductPerformanceResult:
    requested_period_start: date | None
    requested_period_end: date | None
    worker_products: tuple[
        WorkerProductPerformance,
        ...,
    ]
    truck_products: tuple[
        TruckProductPerformance,
        ...,
    ]
    items_attribution_issue_count: int
    opening_stock_attribution_issue_count: int
    chargement_attribution_issue_count: int

    @property
    def worker_not_sold_count(self) -> int:
        return sum(
            1
            for item in self.worker_products
            if item.quantities.is_not_sold
        )

    @property
    def truck_not_sold_count(self) -> int:
        return sum(
            1
            for item in self.truck_products
            if item.quantities.is_not_sold
        )

    @property
    def worker_negative_gap_count(self) -> int:
        return sum(
            1
            for item in self.worker_products
            if item.quantities.has_negative_quantity_gap
        )

    @property
    def truck_negative_gap_count(self) -> int:
        return sum(
            1
            for item in self.truck_products
            if item.quantities.has_negative_quantity_gap
        )

    def not_sold_for_worker(
        self,
        worker_id: int,
        limit: int = 10,
    ) -> tuple[WorkerProductPerformance, ...]:
        _validate_limit(limit)

        ranked = sorted(
            (
                item
                for item in self.worker_products
                if (
                    item.worker_id == worker_id
                    and item.quantities.is_not_sold
                )
            ),
            key=lambda item: (
                -item.quantities.supplied_quantity,
                item.article_normalized,
                item.brand_id,
            ),
        )

        return tuple(ranked[:limit])

    def least_sold_for_worker(
        self,
        worker_id: int,
        limit: int = 10,
    ) -> tuple[WorkerProductPerformance, ...]:
        _validate_limit(limit)

        ranked = sorted(
            (
                item
                for item in self.worker_products
                if (
                    item.worker_id == worker_id
                    and item.quantities.is_sold
                )
            ),
            key=lambda item: (
                item.quantities.sold_quantity,
                item.article_normalized,
                item.brand_id,
            ),
        )

        return tuple(ranked[:limit])

    def not_sold_for_truck(
        self,
        truck_id: int,
        limit: int = 10,
    ) -> tuple[TruckProductPerformance, ...]:
        _validate_limit(limit)

        ranked = sorted(
            (
                item
                for item in self.truck_products
                if (
                    item.truck_id == truck_id
                    and item.quantities.is_not_sold
                )
            ),
            key=lambda item: (
                -item.quantities.supplied_quantity,
                item.article_normalized,
                item.brand_id,
            ),
        )

        return tuple(ranked[:limit])

    def least_sold_for_truck(
        self,
        truck_id: int,
        limit: int = 10,
    ) -> tuple[TruckProductPerformance, ...]:
        _validate_limit(limit)

        ranked = sorted(
            (
                item
                for item in self.truck_products
                if (
                    item.truck_id == truck_id
                    and item.quantities.is_sold
                )
            ),
            key=lambda item: (
                item.quantities.sold_quantity,
                item.article_normalized,
                item.brand_id,
            ),
        )

        return tuple(ranked[:limit])


@dataclass(slots=True)
class _ProductAccumulator:
    display_name: str
    display_priority: int
    opening_quantity: Decimal = field(
        default_factory=lambda: Decimal("0")
    )
    chargement_quantity: Decimal = field(
        default_factory=lambda: Decimal("0")
    )
    sold_quantity: Decimal = field(
        default_factory=lambda: Decimal("0")
    )

    def update_display_name(
        self,
        *,
        display_name: str,
        priority: int,
    ) -> None:
        if priority > self.display_priority:
            self.display_name = display_name
            self.display_priority = priority

    def freeze(self) -> ProductQuantityContext:
        return ProductQuantityContext(
            opening_quantity=self.opening_quantity,
            chargement_quantity=self.chargement_quantity,
            sold_quantity=self.sold_quantity,
        )


def _validate_limit(limit: int) -> None:
    if limit < 0:
        raise ValueError(
            "limit cannot be negative."
        )


def _get_product_accumulator(
    buckets: dict,
    key,
    *,
    display_name: str,
    display_priority: int,
) -> _ProductAccumulator:
    accumulator = buckets.get(key)

    if accumulator is None:
        accumulator = _ProductAccumulator(
            display_name=display_name,
            display_priority=display_priority,
        )
        buckets[key] = accumulator
    else:
        accumulator.update_display_name(
            display_name=display_name,
            priority=display_priority,
        )

    return accumulator


def _validate_source_results(
    *,
    items_result: ItemsAggregationResult,
    opening_stock_result: StockFlowAggregationResult,
    chargement_result: StockFlowAggregationResult,
) -> None:
    if (
        opening_stock_result.report_type
        != ImportReportType.OPENING_STOCK
    ):
        raise ValueError(
            "opening_stock_result must contain "
            "OPENING_STOCK aggregation."
        )

    if (
        chargement_result.report_type
        != ImportReportType.CHARGEMENT
    ):
        raise ValueError(
            "chargement_result must contain "
            "CHARGEMENT aggregation."
        )

    expected_period = (
        items_result.requested_period_start,
        items_result.requested_period_end,
    )

    opening_period = (
        opening_stock_result.requested_period_start,
        opening_stock_result.requested_period_end,
    )
    chargement_period = (
        chargement_result.requested_period_start,
        chargement_result.requested_period_end,
    )

    if (
        opening_period != expected_period
        or chargement_period != expected_period
    ):
        raise ValueError(
            "All source aggregations must use the same "
            "requested period."
        )


def combine_product_performance(
    *,
    items_result: ItemsAggregationResult,
    opening_stock_result: StockFlowAggregationResult,
    chargement_result: StockFlowAggregationResult,
) -> ProductPerformanceResult:
    """
    Combine period-level product quantities.

    A product is considered not sold only when it has a positive
    opening/load supply context and zero sold quantity during the
    selected period. No exact sale day is inferred from ITEMS.
    """
    _validate_source_results(
        items_result=items_result,
        opening_stock_result=opening_stock_result,
        chargement_result=chargement_result,
    )

    worker_buckets: dict[
        tuple[int, int, str],
        _ProductAccumulator,
    ] = {}

    truck_buckets: dict[
        tuple[int, int, str],
        _ProductAccumulator,
    ] = {}

    for item in (
        opening_stock_result
        .by_brand_worker_product
    ):
        accumulator = _get_product_accumulator(
            worker_buckets,
            (
                item.brand_id,
                item.worker_id,
                item.article_normalized,
            ),
            display_name=item.article,
            display_priority=1,
        )
        accumulator.opening_quantity += (
            item.metrics.total_quantity
        )

    for item in (
        opening_stock_result
        .by_brand_truck_product
    ):
        accumulator = _get_product_accumulator(
            truck_buckets,
            (
                item.brand_id,
                item.truck_id,
                item.article_normalized,
            ),
            display_name=item.article,
            display_priority=1,
        )
        accumulator.opening_quantity += (
            item.metrics.total_quantity
        )

    for item in (
        chargement_result
        .by_brand_worker_product
    ):
        accumulator = _get_product_accumulator(
            worker_buckets,
            (
                item.brand_id,
                item.worker_id,
                item.article_normalized,
            ),
            display_name=item.article,
            display_priority=2,
        )
        accumulator.chargement_quantity += (
            item.metrics.total_quantity
        )

    for item in (
        chargement_result
        .by_brand_truck_product
    ):
        accumulator = _get_product_accumulator(
            truck_buckets,
            (
                item.brand_id,
                item.truck_id,
                item.article_normalized,
            ),
            display_name=item.article,
            display_priority=2,
        )
        accumulator.chargement_quantity += (
            item.metrics.total_quantity
        )

    for item in (
        items_result.by_brand_worker_product
    ):
        accumulator = _get_product_accumulator(
            worker_buckets,
            (
                item.brand_id,
                item.worker_id,
                item.article_normalized,
            ),
            display_name=item.article,
            display_priority=3,
        )
        accumulator.sold_quantity += (
            item.metrics.quantity_sold
        )

    for item in (
        items_result.by_brand_truck_product
    ):
        accumulator = _get_product_accumulator(
            truck_buckets,
            (
                item.brand_id,
                item.truck_id,
                item.article_normalized,
            ),
            display_name=item.article,
            display_priority=3,
        )
        accumulator.sold_quantity += (
            item.metrics.quantity_sold
        )

    worker_products = tuple(
        WorkerProductPerformance(
            brand_id=key[0],
            worker_id=key[1],
            article=value.display_name,
            article_normalized=key[2],
            quantities=value.freeze(),
        )
        for key, value in sorted(
            worker_buckets.items()
        )
    )

    truck_products = tuple(
        TruckProductPerformance(
            brand_id=key[0],
            truck_id=key[1],
            article=value.display_name,
            article_normalized=key[2],
            quantities=value.freeze(),
        )
        for key, value in sorted(
            truck_buckets.items()
        )
    )

    return ProductPerformanceResult(
        requested_period_start=(
            items_result.requested_period_start
        ),
        requested_period_end=(
            items_result.requested_period_end
        ),
        worker_products=worker_products,
        truck_products=truck_products,
        items_attribution_issue_count=len(
            items_result.attribution_issues
        ),
        opening_stock_attribution_issue_count=len(
            opening_stock_result.attribution_issues
        ),
        chargement_attribution_issue_count=len(
            chargement_result.attribution_issues
        ),
    )


def calculate_product_performance(
    *,
    period_start: date | None = None,
    period_end: date | None = None,
    brand_id: int | None = None,
) -> ProductPerformanceResult:
    """
    Build product KPIs from approved analytical sources.

    The truck and assignment indexes are built once and shared
    across the three aggregations.
    """
    if (
        period_start is not None
        and period_end is not None
        and period_end < period_start
    ):
        raise ValueError(
            "period_end cannot be before period_start."
        )

    truck_index = build_truck_code_index()
    assignment_index = build_assignment_index()

    items_result = aggregate_items(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
        truck_index=truck_index,
        assignment_index=assignment_index,
    )

    opening_stock_result = aggregate_opening_stock(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
        truck_index=truck_index,
        assignment_index=assignment_index,
    )

    chargement_result = aggregate_chargement(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
        truck_index=truck_index,
        assignment_index=assignment_index,
    )

    return combine_product_performance(
        items_result=items_result,
        opening_stock_result=opening_stock_result,
        chargement_result=chargement_result,
    )
