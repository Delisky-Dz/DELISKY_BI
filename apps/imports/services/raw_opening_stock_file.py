from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from typing import Any

from .raw_excel_reader import (
    RawExcelReadError,
    read_raw_excel_rows,
)
from .raw_opening_stock_adapter import (
    RawOpeningStockAdapterError,
    adapt_raw_opening_stock_row,
)
from .report_row_reader import (
    RawReportRow,
    ReportRowReadResult,
)
from .report_schemas import normalize_header
from .source_truck_mapper import (
    SourceTruckMappingError,
)


class RawOpeningStockFileError(Exception):
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
class AdaptedOpeningStockRow:
    excel_row_number: int
    values: dict[str, object]


@dataclass(frozen=True, slots=True)
class RawOpeningStockFileResult:
    filename: str
    worksheet_name: str
    rows: tuple[
        AdaptedOpeningStockRow,
        ...
    ]


CANONICAL_OPENING_STOCK_HEADERS = (
    "VAN",
    "Qté",
    "Article",
)

OPENING_STOCK_METADATA_HEADERS = (
    "Colisage",
    "العلبة",
    "Barcode",
)


def _is_blank_value(
    value: object,
) -> bool:
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
        if (
            value.is_integer()
            and value >= 0
        ):
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
    if (
        value is None
        or isinstance(value, bool)
    ):
        return None

    if isinstance(value, Decimal):
        return value

    if isinstance(
        value,
        (int, float),
    ):
        return Decimal(
            str(value)
        )

    if isinstance(value, str):
        cleaned = (
            value.strip()
            .replace("\xa0", "")
            .replace(" ", "")
            .replace(",", ".")
        )

        if not cleaned:
            return None

        try:
            return Decimal(
                cleaned
            )
        except InvalidOperation:
            return None

    return None


def source_truck_code_from_filename(
    filename: str,
) -> str:
    stem = Path(
        filename
    ).stem.strip()

    stem = re.sub(
        (
            r"[\s_-]+"
            r"(?:OPENING|OPNING)"
            r"[\s_-]*STOCK$"
        ),
        "",
        stem,
        flags=re.IGNORECASE,
    ).strip()

    if not stem:
        raise RawOpeningStockFileError(
            "missing_source_truck_code",
            (
                "The raw Opening Stock filename "
                "does not contain a truck code."
            ),
        )

    return stem.upper()


def _is_export_summary_footer(
    raw_row: Mapping[
        object,
        object,
    ],
    *,
    adapted_row_count: int,
    adapted_quantity_total: (
        Decimal | None
    ),
    is_last_row: bool,
) -> bool:
    if not is_last_row:
        return False

    if adapted_quantity_total is None:
        return False

    normalized = {
        normalize_header(
            header
        ): value
        for header, value
        in raw_row.items()
    }

    designation = normalized.get(
        normalize_header(
            "Désignation"
        )
    )
    source_quantity = normalized.get(
        normalize_header(
            "Qté"
        )
    )

    summary_count = (
        _summary_row_count(
            designation
        )
    )

    summary_quantity = (
        _decimal_value(
            source_quantity
        )
    )

    return (
        summary_count
        == adapted_row_count
        and summary_quantity
        == adapted_quantity_total
    )


def _looks_like_export_summary_footer(
    raw_row: Mapping[
        object,
        object,
    ],
    *,
    is_last_row: bool,
) -> bool:
    if not is_last_row:
        return False

    normalized = {
        normalize_header(
            header
        ): value
        for header, value
        in raw_row.items()
    }

    designation = normalized.get(
        normalize_header(
            "Désignation"
        )
    )
    source_quantity = normalized.get(
        normalize_header(
            "Qté"
        )
    )
    colisage = normalized.get(
        normalize_header(
            "Colisage"
        )
    )
    business_quantity = normalized.get(
        normalize_header(
            "العلبة"
        )
    )

    if (
        _summary_row_count(
            designation
        )
        is None
    ):
        return False

    if _is_blank_value(
        source_quantity
    ):
        return False

    return (
        _is_blank_value(
            colisage
        )
        and _is_blank_value(
            business_quantity
        )
    )

def adapt_raw_opening_stock_file(
    source: Any,
    *,
    truck_mapping: Mapping[
        object,
        object,
    ],
    original_filename: (
        str | None
    ) = None,
) -> RawOpeningStockFileResult:
    try:
        raw_result = (
            read_raw_excel_rows(
                source,
                original_filename=(
                    original_filename
                ),
            )
        )
    except RawExcelReadError as exc:
        raise RawOpeningStockFileError(
            "raw_excel_read_failed",
            (
                "The raw Opening Stock Excel "
                "file could not be read."
            ),
            details={
                "cause_code": exc.code,
                "cause_details": dict(
                    exc.details
                ),
            },
        ) from exc

    source_truck_code = (
        source_truck_code_from_filename(
            raw_result.filename
        )
    )

    adapted_rows: list[
        AdaptedOpeningStockRow
    ] = []

    adapted_quantity_total = (
        Decimal("0")
    )
    quantity_total_is_valid = True

    raw_rows = raw_result.rows

    for index, raw_row in enumerate(
        raw_rows
    ):
        raw_values = (
            raw_row.as_dict()
        )

        footer_quantity_total = (
            adapted_quantity_total
            if quantity_total_is_valid
            else None
        )

        is_last_row = (
            index
            == len(raw_rows) - 1
        )

        if _is_export_summary_footer(
            raw_values,
            adapted_row_count=len(
                adapted_rows
            ),
            adapted_quantity_total=(
                footer_quantity_total
            ),
            is_last_row=is_last_row,
        ):
            continue

        if _looks_like_export_summary_footer(
            raw_values,
            is_last_row=is_last_row,
        ):
            raise RawOpeningStockFileError(
                "invalid_export_summary_footer",
                (
                    "The Opening Stock export footer "
                    "does not match the imported rows."
                ),
                details={
                    "excel_row_number": (
                        raw_row.row_number
                    ),
                    "adapted_row_count": len(
                        adapted_rows
                    ),
                    "adapted_quantity_total": (
                        str(
                            footer_quantity_total
                        )
                        if footer_quantity_total
                        is not None
                        else None
                    ),
                },
            )

        try:
            values = (
                adapt_raw_opening_stock_row(
                    raw_values,
                    source_truck_code=(
                        source_truck_code
                    ),
                    truck_mapping=(
                        truck_mapping
                    ),
                )
            )
        except (
            RawOpeningStockAdapterError,
            SourceTruckMappingError,
        ) as exc:
            raise RawOpeningStockFileError(
                "row_adaptation_failed",
                (
                    "A raw Opening Stock Excel "
                    "row could not be adapted."
                ),
                details={
                    "excel_row_number": (
                        raw_row.row_number
                    ),
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

        quantity = _decimal_value(
            values.get("Qté")
        )

        if quantity is None:
            quantity_total_is_valid = (
                False
            )
        elif quantity_total_is_valid:
            adapted_quantity_total += (
                quantity
            )

        adapted_rows.append(
            AdaptedOpeningStockRow(
                excel_row_number=(
                    raw_row.row_number
                ),
                values=values,
            )
        )

    return RawOpeningStockFileResult(
        filename=raw_result.filename,
        worksheet_name=(
            raw_result.worksheet_name
        ),
        rows=tuple(
            adapted_rows
        ),
    )


def to_report_row_read_result(
    result: RawOpeningStockFileResult,
) -> ReportRowReadResult:
    metadata_headers = tuple(
        header
        for header
        in OPENING_STOCK_METADATA_HEADERS
        if any(
            header in row.values
            for row in result.rows
        )
    )

    headers = (
        CANONICAL_OPENING_STOCK_HEADERS
        + metadata_headers
    )

    rows = tuple(
        RawReportRow(
            row_number=(
                row.excel_row_number
            ),
            values=tuple(
                (
                    header,
                    row.values.get(
                        header
                    ),
                )
                for header in headers
            ),
        )
        for row in result.rows
    )

    return ReportRowReadResult(
        filename=result.filename,
        report_type="OPENING_STOCK",
        worksheet_name=(
            result.worksheet_name
        ),
        headers=headers,
        rows=rows,
    )