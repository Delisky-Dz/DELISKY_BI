from collections.abc import Iterable, Mapping
from typing import Any

from .report_schemas import normalize_header
from .source_truck_mapper import (
    SourceTruckMappingError,
    map_source_truck_code,
)


class RawChargementAdapterError(ValueError):
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
            raise RawChargementAdapterError(
                "duplicate_normalized_column",
                (
                    "More than one raw Chargement column "
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
        raise RawChargementAdapterError(
            "missing_required_column",
            (
                "The raw Chargement row is missing "
                f"the required column {header!r}."
            ),
            details={
                "column": header,
            },
        )

    return row[normalized_header]


def adapt_raw_chargement_row(
    raw_row: Mapping[object, object],
    *,
    truck_mapping: Mapping[object, object],
) -> dict[str, object]:
    row = _normalized_row(raw_row)

    source_truck = _required_value(
        row,
        "Vers l'emplacement",
    )
    quantity = _required_value(
        row,
        "Qt?",
    )
    article = _required_value(
        row,
        "Article",
    )

    internal_code = map_source_truck_code(
        source_truck,
        mapping=truck_mapping,
    )

    return {
        "VAN": internal_code,
        "Qt?": quantity,
        "Article": article,
    }


def adapt_raw_chargement_rows(
    raw_rows: Iterable[Mapping[object, object]],
    *,
    truck_mapping: Mapping[object, object],
) -> tuple[dict[str, object], ...]:
    adapted_rows: list[dict[str, object]] = []

    for row_number, raw_row in enumerate(
        raw_rows,
        start=1,
    ):
        try:
            adapted = adapt_raw_chargement_row(
                raw_row,
                truck_mapping=truck_mapping,
            )
        except (
            RawChargementAdapterError,
            SourceTruckMappingError,
        ) as exc:
            raise RawChargementAdapterError(
                "row_adaptation_failed",
                (
                    "A raw Chargement row could not "
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
