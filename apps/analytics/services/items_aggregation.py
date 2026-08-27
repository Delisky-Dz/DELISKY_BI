from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Iterable

from apps.imports.models import ImportReportType, ImportRow

from .approved_data_source import (
    get_approved_calculation_rows,
)
from .assignment_resolver import (
    AssignmentIndex,
    build_assignment_index,
    resolve_worker_for_period,
)
from .report_rows import parse_item_row
from .truck_resolver import (
    TruckCodeIndex,
    build_truck_code_index,
    resolve_truck_by_van,
)


class ItemsAttributionStage(StrEnum):
    TRUCK = "TRUCK"
    WORKER = "WORKER"


class ItemsPeriodStatus(StrEnum):
    INCLUDED = "INCLUDED"
    OUTSIDE = "OUTSIDE"
    PARTIAL_OVERLAP = "PARTIAL_OVERLAP"


@dataclass(frozen=True, slots=True)
class ItemMetrics:
    quantity_sold: Decimal
    item_record_count: int
    positive_quantity_record_count: int
    zero_quantity_record_count: int


@dataclass(frozen=True, slots=True)
class BrandItemTotal:
    brand_id: int
    metrics: ItemMetrics


@dataclass(frozen=True, slots=True)
class TruckItemTotal:
    truck_id: int
    metrics: ItemMetrics


@dataclass(frozen=True, slots=True)
class WorkerItemTotal:
    worker_id: int
    metrics: ItemMetrics


@dataclass(frozen=True, slots=True)
class BrandProductItemTotal:
    brand_id: int
    article: str
    article_normalized: str
    metrics: ItemMetrics


@dataclass(frozen=True, slots=True)
class BrandVanClientItemTotal:
    brand_id: int
    van: str
    van_normalized: str
    client: str
    client_normalized: str
    metrics: ItemMetrics


@dataclass(frozen=True, slots=True)
class BrandVanClientProductItemTotal:
    brand_id: int
    van: str
    van_normalized: str
    client: str
    client_normalized: str
    article: str
    article_normalized: str
    metrics: ItemMetrics


@dataclass(frozen=True, slots=True)
class BrandClientItemTotal:
    brand_id: int
    client: str
    client_normalized: str
    metrics: ItemMetrics


@dataclass(frozen=True, slots=True)
class BrandClientProductItemTotal:
    brand_id: int
    client: str
    client_normalized: str
    article: str
    article_normalized: str
    metrics: ItemMetrics


@dataclass(frozen=True, slots=True)
class BrandTruckProductItemTotal:
    brand_id: int
    truck_id: int
    article: str
    article_normalized: str
    metrics: ItemMetrics


@dataclass(frozen=True, slots=True)
class BrandWorkerProductItemTotal:
    brand_id: int
    worker_id: int
    article: str
    article_normalized: str
    metrics: ItemMetrics


@dataclass(frozen=True, slots=True)
class ItemsAttributionIssue:
    stage: ItemsAttributionStage
    code: str
    import_row_id: int
    batch_id: int
    excel_row_number: int
    brand_id: int
    normalized_van: str
    period_start: date
    period_end: date
    quantity_sold: Decimal
    matching_entity_ids: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class ItemsAggregationResult:
    requested_period_start: date | None
    requested_period_end: date | None
    source_row_count: int
    included_row_count: int
    outside_requested_period_count: int
    partial_overlap_excluded_count: int
    overall: ItemMetrics
    by_brand: tuple[BrandItemTotal, ...]
    by_truck: tuple[TruckItemTotal, ...]
    by_worker: tuple[WorkerItemTotal, ...]
    by_brand_product: tuple[BrandProductItemTotal, ...]
    by_brand_truck_product: tuple[
        BrandTruckProductItemTotal,
        ...,
    ]
    by_brand_worker_product: tuple[
        BrandWorkerProductItemTotal,
        ...,
    ]
    attribution_issues: tuple[ItemsAttributionIssue, ...]
    by_brand_client: tuple[
        BrandClientItemTotal,
        ...,
    ] = ()
    by_brand_client_product: tuple[
        BrandClientProductItemTotal,
        ...,
    ] = ()
    by_brand_van_client: tuple[
        BrandVanClientItemTotal,
        ...,
    ] = ()
    by_brand_van_client_product: tuple[
        BrandVanClientProductItemTotal,
        ...,
    ] = ()

    @property
    def has_attribution_issues(self) -> bool:
        return bool(self.attribution_issues)

    @property
    def has_partial_period_data(self) -> bool:
        return self.partial_overlap_excluded_count > 0


@dataclass(slots=True)
class _ItemAccumulator:
    quantity_sold: Decimal = field(
        default_factory=lambda: Decimal("0")
    )
    item_record_count: int = 0
    positive_quantity_record_count: int = 0
    zero_quantity_record_count: int = 0

    def add(self, quantity: Decimal) -> None:
        self.quantity_sold += quantity
        self.item_record_count += 1

        if quantity > 0:
            self.positive_quantity_record_count += 1
        else:
            self.zero_quantity_record_count += 1

    def freeze(self) -> ItemMetrics:
        return ItemMetrics(
            quantity_sold=self.quantity_sold,
            item_record_count=self.item_record_count,
            positive_quantity_record_count=(
                self.positive_quantity_record_count
            ),
            zero_quantity_record_count=(
                self.zero_quantity_record_count
            ),
        )


@dataclass(slots=True)
class _NamedItemAccumulator:
    display_name: str
    accumulator: _ItemAccumulator = field(
        default_factory=_ItemAccumulator
    )


@dataclass(slots=True)
class _ClientProductItemAccumulator:
    client_display_name: str
    article_display_name: str
    accumulator: _ItemAccumulator = field(
        default_factory=_ItemAccumulator
    )


def _get_accumulator(
    buckets: dict,
    key,
) -> _ItemAccumulator:
    accumulator = buckets.get(key)

    if accumulator is None:
        accumulator = _ItemAccumulator()
        buckets[key] = accumulator

    return accumulator


def _get_named_accumulator(
    buckets: dict,
    key,
    display_name: str,
) -> _NamedItemAccumulator:
    named = buckets.get(key)

    if named is None:
        named = _NamedItemAccumulator(
            display_name=display_name,
        )
        buckets[key] = named

    return named


def _get_client_product_accumulator(
    buckets: dict,
    key,
    client_display_name: str,
    article_display_name: str,
) -> _ClientProductItemAccumulator:
    value = buckets.get(key)

    if value is None:
        value = _ClientProductItemAccumulator(
            client_display_name=client_display_name,
            article_display_name=article_display_name,
        )
        buckets[key] = value

    return value


def _period_status(
    *,
    batch_period_start: date,
    batch_period_end: date,
    requested_period_start: date | None,
    requested_period_end: date | None,
) -> ItemsPeriodStatus:
    if (
        requested_period_start is not None
        and batch_period_end < requested_period_start
    ):
        return ItemsPeriodStatus.OUTSIDE

    if (
        requested_period_end is not None
        and batch_period_start > requested_period_end
    ):
        return ItemsPeriodStatus.OUTSIDE

    if (
        requested_period_start is not None
        and batch_period_start < requested_period_start
    ):
        return ItemsPeriodStatus.PARTIAL_OVERLAP

    if (
        requested_period_end is not None
        and batch_period_end > requested_period_end
    ):
        return ItemsPeriodStatus.PARTIAL_OVERLAP

    return ItemsPeriodStatus.INCLUDED


def aggregate_items(
    *,
    period_start: date | None = None,
    period_end: date | None = None,
    brand_id: int | None = None,
    rows: Iterable[ImportRow] | None = None,
    truck_index: TruckCodeIndex | None = None,
    assignment_index: AssignmentIndex | None = None,
) -> ItemsAggregationResult:
    """
    Aggregate approved and accepted ITEMS rows.

    ITEMS rows have period-level precision only. A row is included
    in a requested period only when its entire batch period is
    contained in that requested period. Partial overlaps are not
    apportioned or assigned to invented dates.
    """
    if (
        period_start is not None
        and period_end is not None
        and period_end < period_start
    ):
        raise ValueError(
            "period_end cannot be before period_start."
        )

    if rows is None:
        rows = get_approved_calculation_rows(
            report_type=ImportReportType.ITEMS,
            brand_id=brand_id,
            period_start=period_start,
            period_end=period_end,
        )

    if truck_index is None:
        truck_index = build_truck_code_index()

    if assignment_index is None:
        assignment_index = build_assignment_index()

    overall = _ItemAccumulator()

    brand_buckets: dict[int, _ItemAccumulator] = {}
    truck_buckets: dict[int, _ItemAccumulator] = {}
    worker_buckets: dict[int, _ItemAccumulator] = {}

    brand_product_buckets: dict[
        tuple[int, str],
        _NamedItemAccumulator,
    ] = {}

    brand_van_client_buckets: dict[
        tuple[int, str, str],
        _NamedItemAccumulator,
    ] = {}

    brand_van_client_product_buckets: dict[
        tuple[int, str, str, str],
        _ClientProductItemAccumulator,
    ] = {}

    brand_client_buckets: dict[
        tuple[int, str],
        _NamedItemAccumulator,
    ] = {}

    brand_client_product_buckets: dict[
        tuple[int, str, str],
        _ClientProductItemAccumulator,
    ] = {}

    brand_truck_product_buckets: dict[
        tuple[int, int, str],
        _NamedItemAccumulator,
    ] = {}

    brand_worker_product_buckets: dict[
        tuple[int, int, str],
        _NamedItemAccumulator,
    ] = {}

    issues: list[ItemsAttributionIssue] = []

    source_row_count = 0
    outside_requested_period_count = 0
    partial_overlap_excluded_count = 0

    for import_row in rows:
        source_row_count += 1
        item = parse_item_row(import_row)

        period_status = _period_status(
            batch_period_start=item.period_start,
            batch_period_end=item.period_end,
            requested_period_start=period_start,
            requested_period_end=period_end,
        )

        if period_status == ItemsPeriodStatus.OUTSIDE:
            outside_requested_period_count += 1
            continue

        if period_status == ItemsPeriodStatus.PARTIAL_OVERLAP:
            partial_overlap_excluded_count += 1
            continue

        overall.add(item.quantity_sold)

        _get_accumulator(
            brand_buckets,
            item.brand_id,
        ).add(item.quantity_sold)

        brand_product = _get_named_accumulator(
            brand_product_buckets,
            (
                item.brand_id,
                item.article_normalized,
            ),
            item.article,
        )
        brand_product.accumulator.add(
            item.quantity_sold
        )

        brand_van_client = _get_named_accumulator(
            brand_van_client_buckets,
            (
                item.brand_id,
                item.van_normalized,
                item.client_normalized,
            ),
            item.client,
        )
        brand_van_client.accumulator.add(
            item.quantity_sold
        )

        brand_van_client_product = (
            _get_client_product_accumulator(
                brand_van_client_product_buckets,
                (
                    item.brand_id,
                    item.van_normalized,
                    item.client_normalized,
                    item.article_normalized,
                ),
                item.client,
                item.article,
            )
        )
        brand_van_client_product.accumulator.add(
            item.quantity_sold
        )

        brand_client = _get_named_accumulator(
            brand_client_buckets,
            (
                item.brand_id,
                item.client_normalized,
            ),
            item.client,
        )
        brand_client.accumulator.add(
            item.quantity_sold
        )

        brand_client_product = (
            _get_client_product_accumulator(
                brand_client_product_buckets,
                (
                    item.brand_id,
                    item.client_normalized,
                    item.article_normalized,
                ),
                item.client,
                item.article,
            )
        )
        brand_client_product.accumulator.add(
            item.quantity_sold
        )

        truck_resolution = resolve_truck_by_van(
            item.van_normalized,
            truck_index=truck_index,
        )

        if not truck_resolution.is_matched:
            issues.append(
                ItemsAttributionIssue(
                    stage=ItemsAttributionStage.TRUCK,
                    code=truck_resolution.status.value,
                    import_row_id=item.import_row_id,
                    batch_id=item.batch_id,
                    excel_row_number=item.excel_row_number,
                    brand_id=item.brand_id,
                    normalized_van=item.van_normalized,
                    period_start=item.period_start,
                    period_end=item.period_end,
                    quantity_sold=item.quantity_sold,
                    matching_entity_ids=(
                        truck_resolution.matching_truck_ids
                    ),
                )
            )
            continue

        truck = truck_resolution.truck
        truck_id = truck.pk

        _get_accumulator(
            truck_buckets,
            truck_id,
        ).add(item.quantity_sold)

        truck_product = _get_named_accumulator(
            brand_truck_product_buckets,
            (
                item.brand_id,
                truck_id,
                item.article_normalized,
            ),
            item.article,
        )
        truck_product.accumulator.add(
            item.quantity_sold
        )

        assignment_resolution = resolve_worker_for_period(
            truck,
            item.period_start,
            item.period_end,
            assignment_index=assignment_index,
        )

        if not assignment_resolution.is_matched:
            issues.append(
                ItemsAttributionIssue(
                    stage=ItemsAttributionStage.WORKER,
                    code=assignment_resolution.status.value,
                    import_row_id=item.import_row_id,
                    batch_id=item.batch_id,
                    excel_row_number=item.excel_row_number,
                    brand_id=item.brand_id,
                    normalized_van=item.van_normalized,
                    period_start=item.period_start,
                    period_end=item.period_end,
                    quantity_sold=item.quantity_sold,
                    matching_entity_ids=(
                        assignment_resolution
                        .matching_assignment_ids
                    ),
                )
            )
            continue

        worker_id = assignment_resolution.worker.pk

        _get_accumulator(
            worker_buckets,
            worker_id,
        ).add(item.quantity_sold)

        worker_product = _get_named_accumulator(
            brand_worker_product_buckets,
            (
                item.brand_id,
                worker_id,
                item.article_normalized,
            ),
            item.article,
        )
        worker_product.accumulator.add(
            item.quantity_sold
        )

    return ItemsAggregationResult(
        requested_period_start=period_start,
        requested_period_end=period_end,
        source_row_count=source_row_count,
        included_row_count=overall.item_record_count,
        outside_requested_period_count=(
            outside_requested_period_count
        ),
        partial_overlap_excluded_count=(
            partial_overlap_excluded_count
        ),
        overall=overall.freeze(),
        by_brand=tuple(
            BrandItemTotal(
                brand_id=key,
                metrics=value.freeze(),
            )
            for key, value in sorted(
                brand_buckets.items()
            )
        ),
        by_truck=tuple(
            TruckItemTotal(
                truck_id=key,
                metrics=value.freeze(),
            )
            for key, value in sorted(
                truck_buckets.items()
            )
        ),
        by_worker=tuple(
            WorkerItemTotal(
                worker_id=key,
                metrics=value.freeze(),
            )
            for key, value in sorted(
                worker_buckets.items()
            )
        ),
        by_brand_product=tuple(
            BrandProductItemTotal(
                brand_id=key[0],
                article=value.display_name,
                article_normalized=key[1],
                metrics=value.accumulator.freeze(),
            )
            for key, value in sorted(
                brand_product_buckets.items()
            )
        ),
        by_brand_van_client=tuple(
            BrandVanClientItemTotal(
                brand_id=key[0],
                van=key[1],
                van_normalized=key[1],
                client=value.display_name,
                client_normalized=key[2],
                metrics=value.accumulator.freeze(),
            )
            for key, value in sorted(
                brand_van_client_buckets.items()
            )
        ),
        by_brand_van_client_product=tuple(
            BrandVanClientProductItemTotal(
                brand_id=key[0],
                van=key[1],
                van_normalized=key[1],
                client=value.client_display_name,
                client_normalized=key[2],
                article=value.article_display_name,
                article_normalized=key[3],
                metrics=value.accumulator.freeze(),
            )
            for key, value in sorted(
                brand_van_client_product_buckets.items()
            )
        ),
        by_brand_client=tuple(
            BrandClientItemTotal(
                brand_id=key[0],
                client=value.display_name,
                client_normalized=key[1],
                metrics=value.accumulator.freeze(),
            )
            for key, value in sorted(
                brand_client_buckets.items()
            )
        ),
        by_brand_client_product=tuple(
            BrandClientProductItemTotal(
                brand_id=key[0],
                client=value.client_display_name,
                client_normalized=key[1],
                article=value.article_display_name,
                article_normalized=key[2],
                metrics=value.accumulator.freeze(),
            )
            for key, value in sorted(
                brand_client_product_buckets.items()
            )
        ),
        by_brand_truck_product=tuple(
            BrandTruckProductItemTotal(
                brand_id=key[0],
                truck_id=key[1],
                article=value.display_name,
                article_normalized=key[2],
                metrics=value.accumulator.freeze(),
            )
            for key, value in sorted(
                brand_truck_product_buckets.items()
            )
        ),
        by_brand_worker_product=tuple(
            BrandWorkerProductItemTotal(
                brand_id=key[0],
                worker_id=key[1],
                article=value.display_name,
                article_normalized=key[2],
                metrics=value.accumulator.freeze(),
            )
            for key, value in sorted(
                brand_worker_product_buckets.items()
            )
        ),
        attribution_issues=tuple(issues),
    )
