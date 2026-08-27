from collections.abc import Iterable, Mapping
from typing import Any

from .report_schemas import normalize_header
from .source_truck_mapper import (
    SourceTruckMappingError,
    map_source_truck_code,
)


class RawOpeningStockAdapterError(ValueError):
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


def _normalized_row(
    raw_row: Mapping[object, object],
) -> dict[str, object]:
    normalized: dict[str, object] = {}
    original_headers: dict[str, str] = {}

    for header, value in raw_row.items():
        normalized_header = normalize_header(
            header
        )

        if normalized_header in normalized:
            raise RawOpeningStockAdapterError(
                "duplicate_normalized_column",
                (
                    "More than one raw Opening Stock "
                    "column normalizes to the same header."
                ),
                details={
                    "normalized_header": (
                        normalized_header
                    ),
                    "first_header": original_headers[
                        normalized_header
                    ],
                    "duplicate_header": str(header),
                },
            )

        normalized[normalized_header] = value
        original_headers[
            normalized_header
        ] = str(header)

    return normalized


def _required_value(
    row: Mapping[str, object],
    header: str,
) -> object:
    normalized_header = normalize_header(
        header
    )

    if normalized_header not in row:
        raise RawOpeningStockAdapterError(
            "missing_required_column",
            (
                "The raw Opening Stock row is missing "
                f"the required column {header!r}."
            ),
            details={
                "column": header,
            },
        )

    return row[normalized_header]


def _optional_value(
    row: Mapping[str, object],
    header: str,
) -> tuple[bool, object]:
    normalized_header = normalize_header(
        header
    )

    if normalized_header not in row:
        return False, None

    return True, row[normalized_header]


def adapt_raw_opening_stock_row(
    raw_row: Mapping[object, object],
    *,
    source_truck_code: object,
    truck_mapping: Mapping[object, object],
) -> dict[str, object]:
    row = _normalized_row(raw_row)

    canonical_headers = {
        normalize_header("VAN"),
        normalize_header("Qt\u00e9"),
        normalize_header("Article"),
    }

    if canonical_headers.issubset(row):
        adapted = {
            "VAN": _required_value(
                row,
                "VAN",
            ),
            "Qt\u00e9": _required_value(
                row,
                "Qt\u00e9",
            ),
            "Article": _required_value(
                row,
                "Article",
            ),
        }

        has_barcode, barcode = _optional_value(
            row,
            "Barcode",
        )

        if has_barcode:
            adapted["Barcode"] = barcode

        return adapted

    designation = _required_value(
        row,
        "D\u00e9signation",
    )
    source_quantity = _required_value(
        row,
        "Qt\u00e9",
    )
    colisage = _required_value(
        row,
        "Colisage",
    )
    business_quantity = _required_value(
        row,
        "\u0627\u0644\u0639\u0644\u0628\u0629",
    )

    has_barcode, barcode = _optional_value(
        row,
        "Barcode",
    )

    internal_code = map_source_truck_code(
        source_truck_code,
        mapping=truck_mapping,
    )

    adapted = {
        "VAN": internal_code,
        "Qt\u00e9": source_quantity,
        "Article": designation,
        "Colisage": colisage,
        "\u0627\u0644\u0639\u0644\u0628\u0629": business_quantity,
    }

    if has_barcode:
        adapted["Barcode"] = barcode

    return adapted


def adapt_raw_opening_stock_rows(
    raw_rows: Iterable[
        Mapping[object, object]
    ],
    *,
    source_truck_code: object,
    truck_mapping: Mapping[object, object],
) -> tuple[dict[str, object], ...]:
    adapted_rows: list[
        dict[str, object]
    ] = []

    for row_number, raw_row in enumerate(
        raw_rows,
        start=1,
    ):
        try:
            adapted = (
                adapt_raw_opening_stock_row(
                    raw_row,
                    source_truck_code=(
                        source_truck_code
                    ),
                    truck_mapping=truck_mapping,
                )
            )
        except (
            RawOpeningStockAdapterError,
            SourceTruckMappingError,
        ) as exc:
            raise RawOpeningStockAdapterError(
                "row_adaptation_failed",
                (
                    "A raw Opening Stock row could "
                    "not be adapted."
                ),
                details={
                    "row_number": row_number,
                    "cause_code": exc.code,
                    "cause_details": dict(
                        getattr(
                            exc,
                            "details",
                            {},
                        )
                    ),
                },
            ) from exc

        adapted_rows.append(
            adapted
        )

    return tuple(adapted_rows)