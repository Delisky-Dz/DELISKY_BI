from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .report_schemas import normalize_header
from .raw_chargement_adapter import (
    RawChargementAdapterError,
    adapt_raw_chargement_row,
)
from .raw_excel_reader import (
    RawExcelReadError,
    read_raw_excel_rows,
)
from .report_row_reader import (
    RawReportRow,
    ReportRowReadResult,
)
from .source_truck_mapper import (
    SourceTruckMappingError,
)


class RawChargementFileError(Exception):
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
class AdaptedChargementRow:
    excel_row_number: int
    values: dict[str, object]


@dataclass(frozen=True, slots=True)
class RawChargementFileResult:
    filename: str
    worksheet_name: str
    rows: tuple[AdaptedChargementRow, ...]


def _is_blank_value(value: object) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        return not value.strip()

    return False


def _summary_row_count(
    value: object,
) -> int | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value if value >= 0 else None

    if isinstance(value, float):
        if value.is_integer() and value >= 0:
            return int(value)
        return None

    if isinstance(value, str):
        cleaned = value.strip()

        if cleaned.isdigit():
            return int(cleaned)

    return None


def _is_export_summary_footer(
    raw_row: Mapping[object, object],
    *,
    adapted_row_count: int,
    is_last_row: bool,
) -> bool:
    if not is_last_row:
        return False

    normalized = {
        normalize_header(header): value
        for header, value in raw_row.items()
    }

    source_truck = normalized.get(
        normalize_header("Vers l'emplacement")
    )
    source_location = normalized.get(
        normalize_header("De l'emplacement")
    )
    raw_datetime = normalized.get(
        normalize_header("Date&Heure")
    )
    article = normalized.get(
        normalize_header("Article")
    )
    quantity = normalized.get(
        normalize_header("Qt\u00e9")
    )

    if not all(
        _is_blank_value(value)
        for value in (
            source_truck,
            source_location,
            raw_datetime,
        )
    ):
        return False

    if _is_blank_value(quantity):
        return False

    summary_count = _summary_row_count(
        article
    )

    return summary_count == adapted_row_count


def adapt_raw_chargement_file(
    source: Any,
    *,
    truck_mapping: Mapping[object, object],
    original_filename: str | None = None,
) -> RawChargementFileResult:
    try:
        raw_result = read_raw_excel_rows(
            source,
            original_filename=original_filename,
        )
    except RawExcelReadError as exc:
        raise RawChargementFileError(
            "raw_excel_read_failed",
            "The raw Chargement Excel file could not be read.",
            details={
                "cause_code": exc.code,
                "cause_details": dict(exc.details),
            },
        ) from exc

    adapted_rows: list[AdaptedChargementRow] = []
    raw_rows = raw_result.rows

    for index, raw_row in enumerate(raw_rows):
        raw_values = raw_row.as_dict()

        if _is_export_summary_footer(
            raw_values,
            adapted_row_count=len(adapted_rows),
            is_last_row=(
                index == len(raw_rows) - 1
            ),
        ):
            continue

        try:
            values = adapt_raw_chargement_row(
                raw_values,
                truck_mapping=truck_mapping,
            )
        except (
            RawChargementAdapterError,
            SourceTruckMappingError,
        ) as exc:
            raise RawChargementFileError(
                "row_adaptation_failed",
                (
                    "A raw Chargement Excel row could not "
                    "be adapted."
                ),
                details={
                    "excel_row_number": raw_row.row_number,
                    "cause_code": exc.code,
                    "cause_details": dict(
                        getattr(exc, "details", {})
                    ),
                },
            ) from exc

        adapted_rows.append(
            AdaptedChargementRow(
                excel_row_number=raw_row.row_number,
                values=values,
            )
        )

    return RawChargementFileResult(
        filename=raw_result.filename,
        worksheet_name=raw_result.worksheet_name,
        rows=tuple(adapted_rows),
    )

CANONICAL_CHARGEMENT_HEADERS = (
    "VAN",
    "Qt\u00e9",
    "Article",
)


def to_report_row_read_result(
    result: RawChargementFileResult,
) -> ReportRowReadResult:
    headers = CANONICAL_CHARGEMENT_HEADERS

    if any(
        "Date&Heure" in row.values
        for row in result.rows
    ):
        headers = headers + (
            "Date&Heure",
        )

    rows = tuple(
        RawReportRow(
            row_number=row.excel_row_number,
            values=tuple(
                (
                    header,
                    row.values.get(header),
                )
                for header in headers
            ),
        )
        for row in result.rows
    )

    return ReportRowReadResult(
        filename=result.filename,
        report_type="CHARGEMENT",
        worksheet_name=result.worksheet_name,
        headers=headers,
        rows=rows,
    )
