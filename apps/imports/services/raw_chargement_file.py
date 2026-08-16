from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

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

    for raw_row in raw_result.rows:
        try:
            values = adapt_raw_chargement_row(
                raw_row.as_dict(),
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
    "Qt?",
    "Article",
)


def to_report_row_read_result(
    result: RawChargementFileResult,
) -> ReportRowReadResult:
    rows = tuple(
        RawReportRow(
            row_number=row.excel_row_number,
            values=tuple(
                (
                    header,
                    row.values[header],
                )
                for header
                in CANONICAL_CHARGEMENT_HEADERS
            ),
        )
        for row in result.rows
    )

    return ReportRowReadResult(
        filename=result.filename,
        report_type="CHARGEMENT",
        worksheet_name=result.worksheet_name,
        headers=CANONICAL_CHARGEMENT_HEADERS,
        rows=rows,
    )
