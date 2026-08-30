from dataclasses import dataclass
from pathlib import Path
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from .raw_excel_reader import (
    RawExcelReadError,
    read_raw_excel_rows,
)
from .raw_items_adapter import (
    RawItemsAdapterError,
    adapt_raw_items_row,
)
from .report_row_cleaner import QTY_SOLD_HEADER
from .report_row_reader import (
    RawReportRow,
    ReportRowReadResult,
)
from .report_schemas import normalize_header
from .source_truck_mapper import (
    SourceTruckMappingError,
)


class RawItemsFileError(Exception):
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
class AdaptedItemsRow:
    excel_row_number: int
    values: dict[str, object]


@dataclass(frozen=True, slots=True)
class RawItemsFileResult:
    filename: str
    worksheet_name: str
    source_truck_code: str
    rows: tuple[AdaptedItemsRow, ...]


CANONICAL_ITEMS_HEADERS = (
    "VAN",
    "Article",
    QTY_SOLD_HEADER,
    "Client",
)

OPTIONAL_ITEMS_HEADERS = (
    "Nbre carton",
    "Barcode",
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


def _decimal_value(
    value: object,
) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None

    if isinstance(value, Decimal):
        return value

    if isinstance(value, (int, float)):
        return Decimal(str(value))

    if isinstance(value, str):
        cleaned = (
            value.strip()
            .replace(" ", "")
            .replace(",", ".")
        )

        if not cleaned:
            return None

        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None

    return None



def source_truck_code_from_filename(
    filename: str,
) -> str:
    stem = Path(filename).stem.strip().upper()

    match = re.fullmatch(
        (
            r"(?P<source>.+?)"
            r"[\s_-]+ITEMS"
            r"(?:"
            r"[\s_-]+"
            r"\d{4}-\d{2}-\d{2}"
            r"[\s_-]+TO[\s_-]+"
            r"\d{4}-\d{2}-\d{2}"
            r")?"
        ),
        stem,
        flags=re.IGNORECASE,
    )

    if match is not None:
        stem = (
            match.group("source")
            .strip()
            .upper()
        )

    if not stem:
        raise RawItemsFileError(
            "missing_source_truck_code",
            (
                "The raw Items filename does not "
                "contain a truck code."
            ),
        )

    return stem


def _is_export_summary_footer(
    raw_row: dict[object, object],
    *,
    adapted_row_count: int,
    adapted_quantity_total: Decimal | None,
    is_last_row: bool,
) -> bool:
    if not is_last_row:
        return False

    if adapted_quantity_total is None:
        return False

    normalized = {
        normalize_header(header): value
        for header, value in raw_row.items()
    }

    article = normalized.get(
        normalize_header("Article")
    )
    code = normalized.get(
        normalize_header("Code")
    )
    quantity = normalized.get(
        normalize_header("Qt\u00e9")
    )
    client = normalized.get(
        normalize_header("Client")
    )

    if not _is_blank_value(code):
        return False

    if not _is_blank_value(client):
        return False

    summary_count = _summary_row_count(
        article
    )

    summary_quantity = _decimal_value(
        quantity
    )

    return (
        summary_count == adapted_row_count
        and summary_quantity
        == adapted_quantity_total
    )


def adapt_raw_items_file(
    source: Any,
    *,
    truck_mapping: dict[object, object],
    original_filename: str | None = None,
) -> RawItemsFileResult:
    try:
        raw_result = read_raw_excel_rows(
            source,
            original_filename=original_filename,
        )
    except RawExcelReadError as exc:
        raise RawItemsFileError(
            "raw_excel_read_failed",
            "The raw Items Excel file could not be read.",
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

    adapted_rows: list[AdaptedItemsRow] = []
    adapted_quantity_total = Decimal("0")
    quantity_total_is_valid = True

    raw_rows = raw_result.rows

    for index, raw_row in enumerate(raw_rows):
        raw_values = raw_row.as_dict()

        footer_quantity_total = (
            adapted_quantity_total
            if quantity_total_is_valid
            else None
        )

        if _is_export_summary_footer(
            raw_values,
            adapted_row_count=len(adapted_rows),
            adapted_quantity_total=(
                footer_quantity_total
            ),
            is_last_row=(
                index == len(raw_rows) - 1
            ),
        ):
            continue

        try:
            values = adapt_raw_items_row(
                raw_values,
                source_truck_code=source_truck_code,
                truck_mapping=truck_mapping,
            )
        except (
            RawItemsAdapterError,
            SourceTruckMappingError,
        ) as exc:
            raise RawItemsFileError(
                "row_adaptation_failed",
                (
                    "A raw Items Excel row could not "
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

        quantity = _decimal_value(
            values.get(QTY_SOLD_HEADER)
        )

        if quantity is None:
            quantity_total_is_valid = False
        elif quantity_total_is_valid:
            adapted_quantity_total += quantity

        adapted_rows.append(
            AdaptedItemsRow(
                excel_row_number=raw_row.row_number,
                values=values,
            )
        )

    return RawItemsFileResult(
        filename=raw_result.filename,
        worksheet_name=raw_result.worksheet_name,
        source_truck_code=source_truck_code,
        rows=tuple(adapted_rows),
    )


def to_report_row_read_result(
    result: RawItemsFileResult,
) -> ReportRowReadResult:
    optional_headers = tuple(
        header
        for header in OPTIONAL_ITEMS_HEADERS
        if any(
            header in row.values
            for row in result.rows
        )
    )

    headers = (
        CANONICAL_ITEMS_HEADERS
        + optional_headers
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
        report_type="ITEMS",
        worksheet_name=result.worksheet_name,
        headers=headers,
        rows=rows,
    )