from collections.abc import Iterable, Mapping
from typing import Any

from .report_schemas import normalize_header
from .source_truck_mapper import (
    SourceTruckMappingError,
    map_source_truck_code,
)


class RawItemsAdapterError(ValueError):
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
            raise RawItemsAdapterError(
                "duplicate_normalized_column",
                (
                    "More than one raw Items column "
                    "normalizes to the same header."
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
        raise RawItemsAdapterError(
            "missing_required_column",
            (
                "The raw Items row is missing "
                f"the required column {header!r}."
            ),
            details={
                "column": header,
            },
        )

    return row[normalized_header]


def adapt_raw_items_row(
    raw_row: Mapping[object, object],
    *,
    source_truck_code: object,
    truck_mapping: Mapping[object, object],
) -> dict[str, object]:
    row = _normalized_row(raw_row)

    article = _required_value(
        row,
        "Article",
    )

    quantity = _required_value(
        row,
        "Qt\u00e9",
    )

    client = _required_value(
        row,
        "Client",
    )

    internal_code = map_source_truck_code(
        source_truck_code,
        mapping=truck_mapping,
    )

    return {
        "VAN": internal_code,
        "Article": article,
        "Qt\u00e9 vendue": quantity,
        "Client": client,
    }


def adapt_raw_items_rows(
    raw_rows: Iterable[
        Mapping[object, object]
    ],
    *,
    source_truck_code: object,
    truck_mapping: Mapping[object, object],
) -> tuple[dict[str, object], ...]:
    adapted_rows = []

    for row_number, raw_row in enumerate(
        raw_rows,
        start=1,
    ):
        try:
            adapted = adapt_raw_items_row(
                raw_row,
                source_truck_code=(
                    source_truck_code
                ),
                truck_mapping=truck_mapping,
            )
        except (
            RawItemsAdapterError,
            SourceTruckMappingError,
        ) as exc:
            raise RawItemsAdapterError(
                "row_adaptation_failed",
                (
                    "A raw Items row could not "
                    "be adapted."
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

        adapted_rows.append(adapted)

    return tuple(adapted_rows)
