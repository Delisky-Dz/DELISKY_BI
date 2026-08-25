from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


class ProductQuantityError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True, slots=True)
class ProductQuantity:
    units_per_carton: int
    total_units: int
    carton_quantity: Decimal
    cartons: int
    pieces: int


def _validate_units_per_carton(
    value: Any,
) -> int:
    if isinstance(value, bool):
        raise ProductQuantityError(
            "invalid_units_per_carton",
            "units_per_carton must be a positive integer.",
        )

    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ProductQuantityError(
            "invalid_units_per_carton",
            "units_per_carton must be a positive integer.",
        ) from exc

    if (
        parsed <= 0
        or parsed != parsed.to_integral_value()
    ):
        raise ProductQuantityError(
            "invalid_units_per_carton",
            "units_per_carton must be a positive integer.",
        )

    return int(parsed)


def _parse_decimal(
    value: Any,
    *,
    field_name: str,
) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ProductQuantityError(
            "invalid_quantity",
            f"{field_name} must be numeric.",
            details={
                "field_name": field_name,
                "raw_value": value,
            },
        )

    if isinstance(value, Decimal):
        return value

    text = (
        str(value)
        .strip()
        .replace("\xa0", "")
        .replace(" ", "")
        .replace(",", ".")
    )

    if not text:
        raise ProductQuantityError(
            "invalid_quantity",
            f"{field_name} must be numeric.",
            details={
                "field_name": field_name,
                "raw_value": value,
            },
        )

    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ProductQuantityError(
            "invalid_quantity",
            f"{field_name} must be numeric.",
            details={
                "field_name": field_name,
                "raw_value": value,
            },
        ) from exc


def quantity_from_total_units(
    total_units: Any,
    *,
    units_per_carton: Any,
) -> ProductQuantity:
    packaging = _validate_units_per_carton(
        units_per_carton
    )

    parsed_units = _parse_decimal(
        total_units,
        field_name="total_units",
    )

    if (
        parsed_units
        != parsed_units.to_integral_value()
    ):
        raise ProductQuantityError(
            "fractional_total_units",
            "total_units cannot contain a fraction of a piece.",
            details={
                "raw_value": total_units,
            },
        )

    total = int(parsed_units)

    absolute_total = abs(total)

    carton_count = (
        absolute_total // packaging
    )
    piece_count = (
        absolute_total % packaging
    )

    if total < 0:
        carton_count = -carton_count
        piece_count = -piece_count

    return ProductQuantity(
        units_per_carton=packaging,
        total_units=total,
        carton_quantity=(
            Decimal(total)
            / Decimal(packaging)
        ),
        cartons=carton_count,
        pieces=piece_count,
    )


def quantity_from_carton_value(
    value: Any,
    *,
    units_per_carton: Any,
) -> ProductQuantity:
    packaging = _validate_units_per_carton(
        units_per_carton
    )

    if isinstance(value, str):
        text = value.strip()

        if ":" in text:
            parts = text.split(":")

            if len(parts) != 2:
                raise ProductQuantityError(
                    "invalid_carton_piece_notation",
                    (
                        "Carton/piece quantity must use "
                        "the format cartons:pieces."
                    ),
                    details={
                        "raw_value": value,
                    },
                )

            carton_raw = _parse_decimal(
                parts[0],
                field_name="cartons",
            )
            pieces_raw = _parse_decimal(
                parts[1],
                field_name="pieces",
            )

            if (
                carton_raw
                != carton_raw.to_integral_value()
                or pieces_raw
                != pieces_raw.to_integral_value()
            ):
                raise ProductQuantityError(
                    "invalid_carton_piece_notation",
                    (
                        "Cartons and pieces must both "
                        "be whole numbers."
                    ),
                    details={
                        "raw_value": value,
                    },
                )

            cartons = int(carton_raw)
            pieces = int(pieces_raw)

            if cartons < 0 or pieces < 0:
                raise ProductQuantityError(
                    "negative_carton_piece_notation",
                    (
                        "Carton/piece notation cannot "
                        "contain negative values."
                    ),
                    details={
                        "raw_value": value,
                    },
                )

            if pieces >= packaging:
                raise ProductQuantityError(
                    "pieces_exceed_carton_size",
                    (
                        "The piece remainder must be "
                        "smaller than units_per_carton."
                    ),
                    details={
                        "raw_value": value,
                        "pieces": pieces,
                        "units_per_carton": packaging,
                    },
                )

            total_units = (
                cartons * packaging
                + pieces
            )

            return quantity_from_total_units(
                total_units,
                units_per_carton=packaging,
            )

    carton_quantity = _parse_decimal(
        value,
        field_name="carton_quantity",
    )

    total_units = (
        carton_quantity
        * Decimal(packaging)
    )

    if (
        total_units
        != total_units.to_integral_value()
    ):
        raise ProductQuantityError(
            "carton_quantity_not_exact",
            (
                "The carton quantity does not convert "
                "to a whole number of pieces."
            ),
            details={
                "raw_value": value,
                "units_per_carton": packaging,
            },
        )

    return quantity_from_total_units(
        int(total_units),
        units_per_carton=packaging,
    )