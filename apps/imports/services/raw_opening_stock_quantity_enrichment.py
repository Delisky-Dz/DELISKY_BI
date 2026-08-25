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


class OpeningStockQuantityStatus(StrEnum):
    READY = "READY"

    SOURCE_QUANTITY_MISMATCH = (
        "SOURCE_QUANTITY_MISMATCH"
    )
    SOURCE_PACKAGING_MISMATCH = (
        "SOURCE_PACKAGING_MISMATCH"
    )
    SOURCE_QUANTITY_AND_PACKAGING_MISMATCH = (
        "SOURCE_QUANTITY_AND_PACKAGING_MISMATCH"
    )

    INVALID_SOURCE_QUANTITY = (
        "INVALID_SOURCE_QUANTITY"
    )
    INVALID_SOURCE_PACKAGING = (
        "INVALID_SOURCE_PACKAGING"
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
class OpeningStockQuantityEnrichment:
    status: OpeningStockQuantityStatus

    product: SourceProductPackaging | None
    match_method: str | None

    source_quantity_raw: Any
    source_packaging_raw: Any
    business_quantity_raw: Any

    units_per_carton: int | None
    total_units: int | None
    carton_quantity: Decimal | None
    cartons: int | None
    pieces: int | None

    source_total_units: int | None
    source_units_per_carton: int | None

    quantity_matches_source: bool | None
    packaging_matches_product: bool | None

    error_code: str | None = None


def _is_blank(value: Any) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        return not value.strip()

    return False


def _parse_whole_number(
    value: Any,
    *,
    field_name: str,
) -> int | None:
    if _is_blank(value):
        return None

    if isinstance(value, bool):
        raise ValueError(
            f"{field_name} cannot be boolean."
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
                f"{field_name} is not numeric."
            ) from exc

    if parsed != parsed.to_integral_value():
        raise ValueError(
            f"{field_name} must be a whole number."
        )

    return int(parsed)


def _without_quantity(
    *,
    status: OpeningStockQuantityStatus,
    product: SourceProductPackaging | None,
    match_method: str | None,
    source_quantity_raw: Any,
    source_packaging_raw: Any,
    business_quantity_raw: Any,
    error_code: str | None = None,
) -> OpeningStockQuantityEnrichment:
    return OpeningStockQuantityEnrichment(
        status=status,
        product=product,
        match_method=match_method,
        source_quantity_raw=source_quantity_raw,
        source_packaging_raw=source_packaging_raw,
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
        source_units_per_carton=None,
        quantity_matches_source=None,
        packaging_matches_product=None,
        error_code=error_code,
    )


def _with_business_quantity(
    *,
    status: OpeningStockQuantityStatus,
    product: SourceProductPackaging,
    match_method: str | None,
    source_quantity_raw: Any,
    source_packaging_raw: Any,
    business_quantity_raw: Any,
    quantity: ProductQuantity,
    source_total_units: int | None,
    source_units_per_carton: int | None,
    quantity_matches_source: bool | None,
    packaging_matches_product: bool | None,
    error_code: str | None = None,
) -> OpeningStockQuantityEnrichment:
    return OpeningStockQuantityEnrichment(
        status=status,
        product=product,
        match_method=match_method,
        source_quantity_raw=source_quantity_raw,
        source_packaging_raw=source_packaging_raw,
        business_quantity_raw=business_quantity_raw,
        units_per_carton=quantity.units_per_carton,
        total_units=quantity.total_units,
        carton_quantity=quantity.carton_quantity,
        cartons=quantity.cartons,
        pieces=quantity.pieces,
        source_total_units=source_total_units,
        source_units_per_carton=source_units_per_carton,
        quantity_matches_source=quantity_matches_source,
        packaging_matches_product=packaging_matches_product,
        error_code=error_code,
    )


def enrich_raw_opening_stock_quantity(
    row: dict[str, object],
    *,
    source_system: ImportSourceSystem,
) -> OpeningStockQuantityEnrichment:
    source_quantity_raw = row.get("Qté")
    source_packaging_raw = row.get("Colisage")
    business_quantity_raw = row.get("العلبة")

    if _is_blank(business_quantity_raw):
        return _without_quantity(
            status=(
                OpeningStockQuantityStatus
                .MISSING_BUSINESS_QUANTITY
            ),
            product=None,
            match_method=None,
            source_quantity_raw=source_quantity_raw,
            source_packaging_raw=source_packaging_raw,
            business_quantity_raw=business_quantity_raw,
            error_code="missing_opening_stock_business_quantity",
        )

    resolution = resolve_source_product_packaging(
        source_system=source_system,
        barcode=row.get("Barcode"),
        designation=row.get("Article"),
    )

    status_map = {
        PackagingResolutionStatus.UNKNOWN_PRODUCT:
            OpeningStockQuantityStatus.UNKNOWN_PRODUCT,
        PackagingResolutionStatus.UNKNOWN_PACKAGING:
            OpeningStockQuantityStatus.UNKNOWN_PACKAGING,
        PackagingResolutionStatus.AMBIGUOUS_PRODUCT:
            OpeningStockQuantityStatus.AMBIGUOUS_PRODUCT,
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
            match_method=resolution.match_method,
            source_quantity_raw=source_quantity_raw,
            source_packaging_raw=source_packaging_raw,
            business_quantity_raw=business_quantity_raw,
            error_code=resolution.status.value,
        )

    product = resolution.product

    assert product is not None
    assert product.units_per_carton is not None

    try:
        quantity = quantity_from_carton_value(
            business_quantity_raw,
            units_per_carton=(
                product.units_per_carton
            ),
        )
    except ProductQuantityError as exc:
        return _without_quantity(
            status=(
                OpeningStockQuantityStatus
                .INVALID_BUSINESS_QUANTITY
            ),
            product=product,
            match_method=resolution.match_method,
            source_quantity_raw=source_quantity_raw,
            source_packaging_raw=source_packaging_raw,
            business_quantity_raw=business_quantity_raw,
            error_code=exc.code,
        )

    if quantity.total_units < 0:
        return _without_quantity(
            status=(
                OpeningStockQuantityStatus
                .INVALID_BUSINESS_QUANTITY
            ),
            product=product,
            match_method=resolution.match_method,
            source_quantity_raw=source_quantity_raw,
            source_packaging_raw=source_packaging_raw,
            business_quantity_raw=business_quantity_raw,
            error_code="negative_business_quantity",
        )

    try:
        source_total_units = _parse_whole_number(
            source_quantity_raw,
            field_name="source_quantity",
        )
    except ValueError:
        return _with_business_quantity(
            status=(
                OpeningStockQuantityStatus
                .INVALID_SOURCE_QUANTITY
            ),
            product=product,
            match_method=resolution.match_method,
            source_quantity_raw=source_quantity_raw,
            source_packaging_raw=source_packaging_raw,
            business_quantity_raw=business_quantity_raw,
            quantity=quantity,
            source_total_units=None,
            source_units_per_carton=None,
            quantity_matches_source=None,
            packaging_matches_product=None,
            error_code="invalid_source_quantity",
        )

    try:
        source_units_per_carton = (
            _parse_whole_number(
                source_packaging_raw,
                field_name="source_packaging",
            )
        )

        if (
            source_units_per_carton is None
            or source_units_per_carton <= 0
        ):
            raise ValueError(
                "Source packaging must be positive."
            )
    except ValueError:
        return _with_business_quantity(
            status=(
                OpeningStockQuantityStatus
                .INVALID_SOURCE_PACKAGING
            ),
            product=product,
            match_method=resolution.match_method,
            source_quantity_raw=source_quantity_raw,
            source_packaging_raw=source_packaging_raw,
            business_quantity_raw=business_quantity_raw,
            quantity=quantity,
            source_total_units=source_total_units,
            source_units_per_carton=None,
            quantity_matches_source=(
                source_total_units is None
                or source_total_units
                == quantity.total_units
            ),
            packaging_matches_product=None,
            error_code="invalid_source_packaging",
        )

    quantity_matches_source = (
        source_total_units is None
        or source_total_units
        == quantity.total_units
    )

    packaging_matches_product = (
        source_units_per_carton
        == product.units_per_carton
    )

    if (
        quantity_matches_source
        and packaging_matches_product
    ):
        status = (
            OpeningStockQuantityStatus.READY
        )
    elif (
        not quantity_matches_source
        and not packaging_matches_product
    ):
        status = (
            OpeningStockQuantityStatus
            .SOURCE_QUANTITY_AND_PACKAGING_MISMATCH
        )
    elif not quantity_matches_source:
        status = (
            OpeningStockQuantityStatus
            .SOURCE_QUANTITY_MISMATCH
        )
    else:
        status = (
            OpeningStockQuantityStatus
            .SOURCE_PACKAGING_MISMATCH
        )

    return _with_business_quantity(
        status=status,
        product=product,
        match_method=resolution.match_method,
        source_quantity_raw=source_quantity_raw,
        source_packaging_raw=source_packaging_raw,
        business_quantity_raw=business_quantity_raw,
        quantity=quantity,
        source_total_units=source_total_units,
        source_units_per_carton=(
            source_units_per_carton
        ),
        quantity_matches_source=(
            quantity_matches_source
        ),
        packaging_matches_product=(
            packaging_matches_product
        ),
    )