import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum

from .items_aggregation import (
    ItemsAggregationResult,
    aggregate_items,
)
from .sales_aggregation import (
    SalesAggregationResult,
    aggregate_sales,
)


_SALES_CLIENT_CODE_RE = re.compile(
    r"^(?P<code>\d+)\s+(?P<name>.+)$"
)


class ClientIdentityStatus(StrEnum):
    UNAMBIGUOUS = "UNAMBIGUOUS"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True, slots=True)
class ClientIdentityIssue:
    brand_id: int
    van_normalized: str
    client_normalized: str
    sale_client_codes: tuple[str, ...]
    sale_client_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ClientPurchaseMetrics:
    total_sales: Decimal
    sale_record_count: int
    quantity_sold: Decimal
    item_record_count: int
    distinct_product_count: int

    @property
    def has_sales_data(self) -> bool:
        return self.sale_record_count > 0

    @property
    def has_items_data(self) -> bool:
        return self.item_record_count > 0

    @property
    def average_sale_value(self) -> Decimal | None:
        if self.sale_record_count == 0:
            return None

        return (
            self.total_sales
            / Decimal(self.sale_record_count)
        )

    @property
    def average_quantity_per_sale(
        self,
    ) -> Decimal | None:
        if (
            self.sale_record_count == 0
            or self.item_record_count == 0
        ):
            return None

        return (
            self.quantity_sold
            / Decimal(self.sale_record_count)
        )


@dataclass(frozen=True, slots=True)
class ClientProductPurchase:
    brand_id: int
    van: str
    van_normalized: str
    client: str
    client_normalized: str
    article: str
    article_normalized: str
    quantity_sold: Decimal
    item_record_count: int


@dataclass(frozen=True, slots=True)
class ClientPurchasePerformance:
    brand_id: int
    van: str
    van_normalized: str
    client: str
    client_normalized: str
    customer_code: str | None
    identity_status: ClientIdentityStatus
    metrics: ClientPurchaseMetrics
    products: tuple[
        ClientProductPurchase,
        ...,
    ]


@dataclass(frozen=True, slots=True)
class ClientPurchasePerformanceResult:
    requested_period_start: date | None
    requested_period_end: date | None
    clients: tuple[
        ClientPurchasePerformance,
        ...,
    ]
    identity_issues: tuple[
        ClientIdentityIssue,
        ...,
    ]
    items_source_row_count: int
    items_included_row_count: int
    items_partial_overlap_count: int
    sales_source_row_count: int
    sales_included_row_count: int

    @property
    def has_identity_issues(self) -> bool:
        return bool(self.identity_issues)

    def products_for_client(
        self,
        *,
        brand_id: int,
        client_normalized: str,
        van_normalized: str | None = None,
    ) -> tuple[ClientProductPurchase, ...]:
        for client in self.clients:
            if (
                client.brand_id == brand_id
                and client.client_normalized
                == client_normalized
                and (
                    van_normalized is None
                    or client.van_normalized
                    == van_normalized
                )
            ):
                return client.products

        return ()


@dataclass(slots=True)
class _ClientAccumulator:
    display_name: str
    van_normalized: str
    customer_code: str | None = None
    identity_status: ClientIdentityStatus = (
        ClientIdentityStatus.UNAMBIGUOUS
    )
    total_sales: Decimal = field(
        default_factory=lambda: Decimal("0")
    )
    sale_record_count: int = 0
    quantity_sold: Decimal = field(
        default_factory=lambda: Decimal("0")
    )
    item_record_count: int = 0
    products: dict[
        str,
        ClientProductPurchase,
    ] = field(default_factory=dict)


def _split_sales_client_identity(
    *,
    client: str,
    client_normalized: str,
) -> tuple[str | None, str, str]:
    normalized = client_normalized.strip()
    display = client.strip()

    normalized_match = (
        _SALES_CLIENT_CODE_RE.match(normalized)
    )

    if normalized_match is None:
        return (
            None,
            display,
            normalized,
        )

    code = normalized_match.group("code")
    canonical_normalized = (
        normalized_match.group("name").strip()
    )

    display_match = (
        _SALES_CLIENT_CODE_RE.match(display)
    )

    if display_match is not None:
        canonical_display = (
            display_match.group("name").strip()
        )
    else:
        canonical_display = display

    return (
        code,
        canonical_display,
        canonical_normalized,
    )


def _validate_periods(
    *,
    items_result: ItemsAggregationResult,
    sales_result: SalesAggregationResult,
) -> None:
    items_period = (
        items_result.requested_period_start,
        items_result.requested_period_end,
    )

    sales_period = (
        sales_result.requested_period_start,
        sales_result.requested_period_end,
    )

    if items_period != sales_period:
        raise ValueError(
            "Items and Sales analytical periods "
            "must match."
        )


def _get_client_accumulator(
    buckets: dict[
        tuple[int, str, str, str],
        _ClientAccumulator,
    ],
    *,
    brand_id: int,
    van_normalized: str,
    client: str,
    client_normalized: str,
    identity_discriminator: str = "",
) -> _ClientAccumulator:
    key = (
        brand_id,
        van_normalized,
        client_normalized,
        identity_discriminator,
    )

    value = buckets.get(key)

    if value is None:
        value = _ClientAccumulator(
            display_name=client,
            van_normalized=van_normalized,
        )
        buckets[key] = value

    return value


def combine_client_purchase_performance(
    *,
    items_result: ItemsAggregationResult,
    sales_result: SalesAggregationResult,
) -> ClientPurchasePerformanceResult:
    """
    Combine route-aware client Sales and Items analytics.

    Client identity is scoped by brand and VAN.

    A leading numeric Sales customer code is extracted from
    the Sales display value before matching with ITEMS.

    If more than one distinct Sales identity maps to the same
    brand + VAN + cleaned client name, the identity is marked
    ambiguous and ITEMS are not automatically merged into one
    of those Sales identities.
    """

    _validate_periods(
        items_result=items_result,
        sales_result=sales_result,
    )

    buckets: dict[
        tuple[int, str, str, str],
        _ClientAccumulator,
    ] = {}

    issues: list[ClientIdentityIssue] = []

    for item in items_result.by_brand_van_client:
        accumulator = _get_client_accumulator(
            buckets,
            brand_id=item.brand_id,
            van_normalized=item.van_normalized,
            client=item.client,
            client_normalized=(
                item.client_normalized
            ),
        )

        accumulator.quantity_sold += (
            item.metrics.quantity_sold
        )

        accumulator.item_record_count += (
            item.metrics.item_record_count
        )

    for item in (
        items_result.by_brand_van_client_product
    ):
        accumulator = _get_client_accumulator(
            buckets,
            brand_id=item.brand_id,
            van_normalized=item.van_normalized,
            client=item.client,
            client_normalized=(
                item.client_normalized
            ),
        )

        accumulator.products[
            item.article_normalized
        ] = ClientProductPurchase(
            brand_id=item.brand_id,
            van=item.van,
            van_normalized=item.van_normalized,
            client=item.client,
            client_normalized=(
                item.client_normalized
            ),
            article=item.article,
            article_normalized=(
                item.article_normalized
            ),
            quantity_sold=(
                item.metrics.quantity_sold
            ),
            item_record_count=(
                item.metrics.item_record_count
            ),
        )

    sales_groups: dict[
        tuple[int, str, str],
        list,
    ] = {}

    for sale in sales_result.by_brand_van_client:
        (
            customer_code,
            canonical_display,
            canonical_normalized,
        ) = _split_sales_client_identity(
            client=sale.client,
            client_normalized=(
                sale.client_normalized
            ),
        )

        key = (
            sale.brand_id,
            sale.van_normalized,
            canonical_normalized,
        )

        sales_groups.setdefault(
            key,
            [],
        ).append(
            (
                sale,
                customer_code,
                canonical_display,
            )
        )

    for key, entries in sales_groups.items():
        brand_id = key[0]
        van_normalized = key[1]
        canonical_normalized = key[2]

        raw_identities = {
            entry[0].client_normalized
            for entry in entries
        }

        is_ambiguous = (
            len(raw_identities) > 1
        )

        if not is_ambiguous:
            (
                sale,
                customer_code,
                canonical_display,
            ) = entries[0]

            accumulator = _get_client_accumulator(
                buckets,
                brand_id=brand_id,
                van_normalized=van_normalized,
                client=canonical_display,
                client_normalized=(
                    canonical_normalized
                ),
            )

            accumulator.total_sales += (
                sale.metrics.total_sales
            )

            accumulator.sale_record_count += (
                sale.metrics.sale_record_count
            )

            accumulator.customer_code = (
                customer_code
            )

            continue

        codes = tuple(
            sorted(
                {
                    code
                    for _, code, _ in entries
                    if code is not None
                }
            )
        )

        names = tuple(
            sorted(
                {
                    sale.client
                    for sale, _, _ in entries
                }
            )
        )

        issues.append(
            ClientIdentityIssue(
                brand_id=brand_id,
                van_normalized=van_normalized,
                client_normalized=(
                    canonical_normalized
                ),
                sale_client_codes=codes,
                sale_client_names=names,
            )
        )

        item_key = (
            brand_id,
            van_normalized,
            canonical_normalized,
            "",
        )

        item_accumulator = buckets.get(
            item_key
        )

        if item_accumulator is not None:
            item_accumulator.identity_status = (
                ClientIdentityStatus.AMBIGUOUS
            )

        for (
            sale,
            customer_code,
            _,
        ) in entries:
            accumulator = _get_client_accumulator(
                buckets,
                brand_id=brand_id,
                van_normalized=van_normalized,
                client=sale.client,
                client_normalized=(
                    canonical_normalized
                ),
                identity_discriminator=(
                    "sales:"
                    + sale.client_normalized
                ),
            )

            accumulator.customer_code = (
                customer_code
            )

            accumulator.identity_status = (
                ClientIdentityStatus.AMBIGUOUS
            )

            accumulator.total_sales += (
                sale.metrics.total_sales
            )

            accumulator.sale_record_count += (
                sale.metrics.sale_record_count
            )

    clients = tuple(
        ClientPurchasePerformance(
            brand_id=key[0],
            van=key[1],
            van_normalized=key[1],
            client=value.display_name,
            client_normalized=key[2],
            customer_code=(
                value.customer_code
            ),
            identity_status=(
                value.identity_status
            ),
            metrics=ClientPurchaseMetrics(
                total_sales=value.total_sales,
                sale_record_count=(
                    value.sale_record_count
                ),
                quantity_sold=(
                    value.quantity_sold
                ),
                item_record_count=(
                    value.item_record_count
                ),
                distinct_product_count=len(
                    value.products
                ),
            ),
            products=tuple(
                value.products[
                    product_key
                ]
                for product_key
                in sorted(value.products)
            ),
        )
        for key, value in sorted(
            buckets.items()
        )
    )

    return ClientPurchasePerformanceResult(
        requested_period_start=(
            items_result.requested_period_start
        ),
        requested_period_end=(
            items_result.requested_period_end
        ),
        clients=clients,
        identity_issues=tuple(issues),
        items_source_row_count=(
            items_result.source_row_count
        ),
        items_included_row_count=(
            items_result.included_row_count
        ),
        items_partial_overlap_count=(
            items_result
            .partial_overlap_excluded_count
        ),
        sales_source_row_count=(
            sales_result.source_row_count
        ),
        sales_included_row_count=(
            sales_result.included_row_count
        ),
    )


def calculate_client_purchase_performance(
    *,
    period_start: date | None = None,
    period_end: date | None = None,
    brand_id: int | None = None,
) -> ClientPurchasePerformanceResult:
    items_result = aggregate_items(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
    )

    sales_result = aggregate_sales(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
    )

    return combine_client_purchase_performance(
        items_result=items_result,
        sales_result=sales_result,
    )
