from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .raw_excel_reader import (
    RawExcelReadError,
    read_raw_excel_rows,
)
from .raw_sales_adapter import (
    RawSalesAdapterError,
    adapt_raw_sales_row,
)
from .report_row_reader import (
    RawReportRow,
    ReportRowReadResult,
)
from .report_schemas import normalize_header
from .source_truck_mapper import (
    SourceTruckMappingError,
)


class RawSalesFileError(Exception):
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
class AdaptedSalesRow:
    excel_row_number: int
    values: dict[str, object]


@dataclass(frozen=True, slots=True)
class RawSalesFileResult:
    filename: str
    worksheet_name: str
    source_truck_code: str
    rows: tuple[AdaptedSalesRow, ...]


CANONICAL_SALES_HEADERS = (
    "VAN",
    "Date&Heure",
    "Nom du client",
    "Total",
    "Region",
)


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


def source_truck_code_from_filename(
    filename: str,
) -> str:
    stem = Path(filename).stem.strip().upper()

    if not stem:
        raise RawSalesFileError(
            "missing_source_truck_code",
            (
                "The raw Sales filename does not "
                "contain a truck code."
            ),
        )

    if stem.startswith("DPV-"):
        raise RawSalesFileError(
            "unsupported_dpv_sales_source",
            (
                "DPV Sales exports are not accepted "
                "as an independent Sales source."
            ),
            details={
                "source_truck_code": stem,
            },
        )

    return stem


def _is_export_summary_footer(
    raw_row: dict[object, object],
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

    key = normalized.get(
        normalize_header("Cl\u00e9")
    )
    raw_datetime = normalized.get(
        normalize_header("Date&Heure")
    )
    client = normalized.get(
        normalize_header("Nom du client")
    )
    region = normalized.get(
        normalize_header("Region")
    )

    if not all(
        _is_blank_value(value)
        for value in (
            raw_datetime,
            client,
            region,
        )
    ):
        return False

    summary_count = _summary_row_count(
        key
    )

    return summary_count == adapted_row_count


def adapt_raw_sales_file(
    source: Any,
    *,
    truck_mapping: dict[object, object],
    original_filename: str | None = None,
) -> RawSalesFileResult:
    try:
        raw_result = read_raw_excel_rows(
            source,
            original_filename=original_filename,
        )
    except RawExcelReadError as exc:
        raise RawSalesFileError(
            "raw_excel_read_failed",
            "The raw Sales Excel file could not be read.",
            details={
                "cause_code": exc.code,
                "cause_details": dict(exc.details),
            },
        ) from exc

    source_truck_code = (
        source_truck_code_from_filename(
            raw_result.filename
        )
    )

    adapted_rows: list[AdaptedSalesRow] = []
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
            values = adapt_raw_sales_row(
                raw_values,
                source_truck_code=source_truck_code,
                truck_mapping=truck_mapping,
            )
        except (
            RawSalesAdapterError,
            SourceTruckMappingError,
        ) as exc:
            raise RawSalesFileError(
                "row_adaptation_failed",
                (
                    "A raw Sales Excel row could not "
                    "be adapted."
                ),
                details={
                    "excel_row_number": (
                        raw_row.row_number
                    ),
                    "cause_code": exc.code,
                    "cause_details": dict(
                        getattr(exc, "details", {})
                    ),
                },
            ) from exc

        adapted_rows.append(
            AdaptedSalesRow(
                excel_row_number=raw_row.row_number,
                values=values,
            )
        )

    return RawSalesFileResult(
        filename=raw_result.filename,
        worksheet_name=raw_result.worksheet_name,
        source_truck_code=source_truck_code,
        rows=tuple(adapted_rows),
    )


def to_report_row_read_result(
    result: RawSalesFileResult,
) -> ReportRowReadResult:
    rows = tuple(
        RawReportRow(
            row_number=row.excel_row_number,
            values=tuple(
                (
                    header,
                    row.values.get(header),
                )
                for header in CANONICAL_SALES_HEADERS
            ),
        )
        for row in result.rows
    )

    return ReportRowReadResult(
        filename=result.filename,
        report_type="SALES",
        worksheet_name=result.worksheet_name,
        headers=CANONICAL_SALES_HEADERS,
        rows=rows,
    )
