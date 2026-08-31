from collections.abc import Iterable, Mapping
from typing import Any

from .report_schemas import normalize_header
from .source_truck_mapper import (
    SourceTruckMappingError,
    map_source_truck_code,
)


class RawPosAdapterError(ValueError):
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
        normalized_header = normalize_header(header)

        if normalized_header in normalized:
            raise RawPosAdapterError(
                "duplicate_normalized_column",
                (
                    "More than one raw POS column "
                    "normalizes to the same header."
                ),
                details={
                    "normalized_header": normalized_header,
                    "first_header": original_headers[
                        normalized_header
                    ],
                    "duplicate_header": str(header),
                },
            )

        normalized[normalized_header] = value
        original_headers[normalized_header] = str(header)

    return normalized


def _required_value(
    row: Mapping[str, object],
    header: str,
) -> object:
    normalized_header = normalize_header(header)

    if normalized_header not in row:
        raise RawPosAdapterError(
            "missing_required_column",
            (
                "The raw POS row is missing "
                f"the required column {header!r}."
            ),
            details={
                "column": header,
            },
        )

    return row[normalized_header]


def adapt_raw_pos_row(
    raw_row: Mapping[object, object],
    *,
    source_truck_code: object,
    truck_mapping: Mapping[object, object],
) -> dict[str, object]:
    row = _normalized_row(raw_row)

    client = _required_value(
        row,
        "Nom du client",
    )
    message = _required_value(
        row,
        "Message d'ignoration",
    )
    visit_date = _required_value(
        row,
        "Date",
    )
    cause = _required_value(
        row,
        "Cause d'ignoration",
    )

    latitude = row.get(
        normalize_header("Latitude")
    )
    longitude = row.get(
        normalize_header("Longitude")
    )

    internal_code = map_source_truck_code(
        source_truck_code,
        mapping=truck_mapping,
    )

    return {
        "VAN": internal_code,
        "Nom du client": client,
        "Latitude": latitude,
        "Longitude": longitude,
        "Message d'ignoration": message,
        "Date": visit_date,
        "Cause d'ignoration": cause,
    }


def adapt_raw_pos_rows(
    raw_rows: Iterable[Mapping[object, object]],
    *,
    source_truck_code: object,
    truck_mapping: Mapping[object, object],
) -> tuple[dict[str, object], ...]:
    adapted_rows: list[dict[str, object]] = []

    for row_number, raw_row in enumerate(
        raw_rows,
        start=1,
    ):
        try:
            adapted = adapt_raw_pos_row(
                raw_row,
                source_truck_code=source_truck_code,
                truck_mapping=truck_mapping,
            )
        except (
            RawPosAdapterError,
            SourceTruckMappingError,
        ) as exc:
            raise RawPosAdapterError(
                "row_adaptation_failed",
                (
                    "A raw POS row could not "
                    "be adapted."
                ),
                details={
                    "row_number": row_number,
                    "cause_code": exc.code,
                    "cause_details": dict(
                        getattr(exc, "details", {})
                    ),
                },
            ) from exc

        adapted_rows.append(adapted)

    return tuple(adapted_rows)
