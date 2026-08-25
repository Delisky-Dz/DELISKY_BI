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
    quantity_from_total_units,
)
from .source_product_packaging_resolver import (
    PackagingResolutionStatus,
    resolve_source_product_packaging,
)


class ChargementQuantityStatus(StrEnum):
    READY = "READY"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    UNKNOWN_PRODUCT = "UNKNOWN_PRODUCT"
    UNKNOWN_PACKAGING = "UNKNOWN_PACKAGING"
    AMBIGUOUS_PRODUCT = "AMBIGUOUS_PRODUCT"


@dataclass(frozen=True, slots=True)
class ChargementQuantityEnrichment:
    status: ChargementQuantityStatus
    product: SourceProductPackaging | None
    match_method: str | None

    quantity_raw: Any
    units_per_carton: int | None
    total_units: int | None
    carton_quantity: Decimal | None
    cartons: int | None
    pieces: int | None

    error_code: str | None = None


def _parse_total_units(
    value: Any,
) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError(
            "Chargement quantity must be numeric."
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

        if not text:
            raise ValueError(
                "Chargement quantity is missing."
            )

        try:
            parsed = Decimal(text)
        except InvalidOperation as exc:
            raise ValueError(
                "Chargement quantity must be numeric."
            ) from exc

    if parsed != parsed.to_integral_value():
        raise ValueError(
            "Chargement quantity must represent whole units."
        )

    return int(parsed)


def _result_without_packaging(
    *,
    status: ChargementQuantityStatus,
    product: SourceProductPackaging | None,
    match_method: str | None,
    quantity_raw: Any,
    total_units: int | None,
    error_code: str | None,
) -> ChargementQuantityEnrichment:
    return ChargementQuantityEnrichment(
        status=status,
        product=product,
        match_method=match_method,
        quantity_raw=quantity_raw,
        units_per_carton=(
            product.units_per_carton
            if product is not None
            else None
        ),
        total_units=total_units,
        carton_quantity=None,
        cartons=None,
        pieces=None,
        error_code=error_code,
    )


def enrich_raw_chargement_quantity(
    row: dict[str, object],
    *,
    source_system: ImportSourceSystem,
) -> ChargementQuantityEnrichment:
    quantity_raw = row.get(
        "Qt\u00e9"
    )

    try:
        total_units = _parse_total_units(
            quantity_raw
        )
    except ValueError:
        return _result_without_packaging(
            status=(
                ChargementQuantityStatus
                .INVALID_QUANTITY
            ),
            product=None,
            match_method=None,
            quantity_raw=quantity_raw,
            total_units=None,
            error_code="invalid_chargement_quantity",
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
            ChargementQuantityStatus.UNKNOWN_PRODUCT,
        PackagingResolutionStatus.UNKNOWN_PACKAGING:
            ChargementQuantityStatus.UNKNOWN_PACKAGING,
        PackagingResolutionStatus.AMBIGUOUS_PRODUCT:
            ChargementQuantityStatus.AMBIGUOUS_PRODUCT,
    }

    if (
        resolution.status
        != PackagingResolutionStatus.READY
    ):
        return _result_without_packaging(
            status=status_map[
                resolution.status
            ],
            product=resolution.product,
            match_method=(
                resolution.match_method
            ),
            quantity_raw=quantity_raw,
            total_units=total_units,
            error_code=resolution.status.value,
        )

    product = resolution.product

    assert product is not None
    assert product.units_per_carton is not None

    try:
        quantity: ProductQuantity = (
            quantity_from_total_units(
                total_units,
                units_per_carton=(
                    product.units_per_carton
                ),
            )
        )
    except ProductQuantityError as exc:
        status = (
            ChargementQuantityStatus
            .INVALID_QUANTITY
        )

        if (
            exc.code
            == "invalid_units_per_carton"
        ):
            status = (
                ChargementQuantityStatus
                .UNKNOWN_PACKAGING
            )

        return _result_without_packaging(
            status=status,
            product=product,
            match_method=(
                resolution.match_method
            ),
            quantity_raw=quantity_raw,
            total_units=total_units,
            error_code=exc.code,
        )

    return ChargementQuantityEnrichment(
        status=ChargementQuantityStatus.READY,
        product=product,
        match_method=resolution.match_method,
        quantity_raw=quantity_raw,
        units_per_carton=(
            quantity.units_per_carton
        ),
        total_units=quantity.total_units,
        carton_quantity=(
            quantity.carton_quantity
        ),
        cartons=quantity.cartons,
        pieces=quantity.pieces,
        error_code=None,
    )
