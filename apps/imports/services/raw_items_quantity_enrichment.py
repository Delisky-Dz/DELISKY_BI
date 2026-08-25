from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from apps.imports.models import (
    ImportSourceSystem,
    SourceProductPackaging,
)

from .product_quantity import (
    ProductQuantity,
    ProductQuantityError,
    quantity_from_carton_value,
)
from .source_product_packaging_resolver import (
    PackagingResolutionStatus,
    resolve_source_product_packaging,
)


class ItemsQuantityStatus(StrEnum):
    READY = "READY"
    SOURCE_QUANTITY_MISMATCH = (
        "SOURCE_QUANTITY_MISMATCH"
    )
    INVALID_SOURCE_QUANTITY = (
        "INVALID_SOURCE_QUANTITY"
    )
    MISSING_BUSINESS_QUANTITY = (
        "MISSING_BUSINESS_QUANTITY"
    )
    INVALID_BUSINESS_QUANTITY = (
        "INVALID_BUSINESS_QUANTITY"
    )
    UNKNOWN_PRODUCT = "UNKNOWN_PRODUCT"
    UNKNOWN_PACKAGING = "UNKNOWN_PACKAGING"
    AMBIGUOUS_PRODUCT = "AMBIGUOUS_PRODUCT"


@dataclass(frozen=True, slots=True)
class ItemsQuantityEnrichment:
    status: ItemsQuantityStatus
    product: SourceProductPackaging | None
    match_method: str | None

    source_quantity_raw: Any
    business_quantity_raw: Any

    units_per_carton: int | None
    total_units: int | None
    carton_quantity: Decimal | None
    cartons: int | None
    pieces: int | None

    source_total_units: int | None
    quantity_matches_source: bool | None

    error_code: str | None = None


def _is_blank(value: Any) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        return not value.strip()

    return False


def _parse_source_total_units(
    value: Any,
) -> int | None:
    if _is_blank(value):
        return None

    if isinstance(value, bool):
        raise ValueError(
            "Source quantity cannot be boolean."
        )

    if isinstance(value, Decimal):
        parsed = value
    else:
        text = (
            str(value)
            .strip()
            .replace("\xa0", "")
            .replace(" ", "")
            .replace(",", ".")
        )

        try:
            parsed = Decimal(text)
        except InvalidOperation as exc:
            raise ValueError(
                "Source quantity is not numeric."
            ) from exc

    if parsed != parsed.to_integral_value():
        raise ValueError(
            "Source quantity must represent whole units."
        )

    return int(parsed)


def _without_quantity(
    *,
    status: ItemsQuantityStatus,
    product: SourceProductPackaging | None,
    match_method: str | None,
    source_quantity_raw: Any,
    business_quantity_raw: Any,
    error_code: str | None = None,
) -> ItemsQuantityEnrichment:
    return ItemsQuantityEnrichment(
        status=status,
        product=product,
        match_method=match_method,
        source_quantity_raw=source_quantity_raw,
        business_quantity_raw=business_quantity_raw,
        units_per_carton=(
            product.units_per_carton
            if product is not None
            else None
        ),
        total_units=None,
        carton_quantity=None,
        cartons=None,
        pieces=None,
        source_total_units=None,
        quantity_matches_source=None,
        error_code=error_code,
    )


def enrich_raw_items_quantity(
    row: dict[str, object],
    *,
    source_system: ImportSourceSystem,
) -> ItemsQuantityEnrichment:
    source_quantity_raw = row.get(
        "Qté vendue"
    )
    business_quantity_raw = row.get(
        "Nbre carton"
    )

    if _is_blank(business_quantity_raw):
        return _without_quantity(
            status=(
                ItemsQuantityStatus
                .MISSING_BUSINESS_QUANTITY
            ),
            product=None,
            match_method=None,
            source_quantity_raw=(
                source_quantity_raw
            ),
            business_quantity_raw=(
                business_quantity_raw
            ),
            error_code=(
                "missing_nbre_carton"
            ),
        )

    resolution = (
        resolve_source_product_packaging(
            source_system=source_system,
            barcode=row.get("Barcode"),
            designation=row.get("Article"),
        )
    )

    status_map = {
        PackagingResolutionStatus.UNKNOWN_PRODUCT:
            ItemsQuantityStatus.UNKNOWN_PRODUCT,
        PackagingResolutionStatus.UNKNOWN_PACKAGING:
            ItemsQuantityStatus.UNKNOWN_PACKAGING,
        PackagingResolutionStatus.AMBIGUOUS_PRODUCT:
            ItemsQuantityStatus.AMBIGUOUS_PRODUCT,
    }

    if (
        resolution.status
        != PackagingResolutionStatus.READY
    ):
        return _without_quantity(
            status=status_map[
                resolution.status
            ],
            product=resolution.product,
            match_method=(
                resolution.match_method
            ),
            source_quantity_raw=(
                source_quantity_raw
            ),
            business_quantity_raw=(
                business_quantity_raw
            ),
            error_code=(
                resolution.status.value
            ),
        )

    product = resolution.product

    assert product is not None
    assert product.units_per_carton is not None

    try:
        quantity: ProductQuantity = (
            quantity_from_carton_value(
                business_quantity_raw,
                units_per_carton=(
                    product.units_per_carton
                ),
            )
        )
    except ProductQuantityError as exc:
        return _without_quantity(
            status=(
                ItemsQuantityStatus
                .INVALID_BUSINESS_QUANTITY
            ),
            product=product,
            match_method=(
                resolution.match_method
            ),
            source_quantity_raw=(
                source_quantity_raw
            ),
            business_quantity_raw=(
                business_quantity_raw
            ),
            error_code=exc.code,
        )

    if quantity.total_units < 0:
        return _without_quantity(
            status=(
                ItemsQuantityStatus
                .INVALID_BUSINESS_QUANTITY
            ),
            product=product,
            match_method=(
                resolution.match_method
            ),
            source_quantity_raw=(
                source_quantity_raw
            ),
            business_quantity_raw=(
                business_quantity_raw
            ),
            error_code=(
                "negative_business_quantity"
            ),
        )

    try:
        source_total_units = (
            _parse_source_total_units(
                source_quantity_raw
            )
        )
    except ValueError:
        return ItemsQuantityEnrichment(
            status=(
                ItemsQuantityStatus
                .INVALID_SOURCE_QUANTITY
            ),
            product=product,
            match_method=(
                resolution.match_method
            ),
            source_quantity_raw=(
                source_quantity_raw
            ),
            business_quantity_raw=(
                business_quantity_raw
            ),
            units_per_carton=(
                quantity.units_per_carton
            ),
            total_units=quantity.total_units,
            carton_quantity=(
                quantity.carton_quantity
            ),
            cartons=quantity.cartons,
            pieces=quantity.pieces,
            source_total_units=None,
            quantity_matches_source=None,
            error_code=(
                "invalid_source_quantity"
            ),
        )

    quantity_matches_source = (
        source_total_units is None
        or source_total_units
        == quantity.total_units
    )

    status = ItemsQuantityStatus.READY

    if not quantity_matches_source:
        status = (
            ItemsQuantityStatus
            .SOURCE_QUANTITY_MISMATCH
        )

    return ItemsQuantityEnrichment(
        status=status,
        product=product,
        match_method=resolution.match_method,
        source_quantity_raw=source_quantity_raw,
        business_quantity_raw=(
            business_quantity_raw
        ),
        units_per_carton=(
            quantity.units_per_carton
        ),
        total_units=quantity.total_units,
        carton_quantity=(
            quantity.carton_quantity
        ),
        cartons=quantity.cartons,
        pieces=quantity.pieces,
        source_total_units=source_total_units,
        quantity_matches_source=(
            quantity_matches_source
        ),
        error_code=None,
    )