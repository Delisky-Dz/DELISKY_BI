from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .raw_excel_reader import (
    RawExcelReadError,
    read_raw_excel_rows,
)
from .report_row_cleaner import QTY_SOLD_HEADER
from .report_row_reader import (
    RawReportRow,
    ReportRowReadResult,
)
from .report_schemas import normalize_header
from .source_truck_mapper import (
    SourceTruckMappingError,
    map_source_truck_code,
)


class RawItemsDetailFileError(Exception):
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
class AdaptedItemsDetailRow:
    excel_row_number: int
    values: dict[str, object]


@dataclass(frozen=True, slots=True)
class ExcludedItemsDetailSourceRow:
    excel_row_number: int
    source_code: str
    reason: str
    sale_datetime_raw: object
    article: object
    quantity_raw: object
    client: object
    document: object
    document_number: object


@dataclass(frozen=True, slots=True)
class RawItemsDetailFileResult:
    filename: str
    worksheet_name: str
    rows: tuple[AdaptedItemsDetailRow, ...]
    excluded_source_rows: tuple[
        ExcludedItemsDetailSourceRow,
        ...,
    ] = ()


CANONICAL_ITEMS_DETAIL_HEADERS = (
    "VAN",
    "Article",
    QTY_SOLD_HEADER,
    "Client",
    "Date de vente",
    "Utilisateur",
    "Document",
    "Num doc.",
)

OPTIONAL_ITEMS_DETAIL_HEADERS = (
    "Barcode",
    "Prix",
    "Total vente",
)


def _canonical_source_code(value: object) -> str:
    return " ".join(
        str(value or "").split()
    ).upper()


def _is_blank_value(value: object) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        return not value.strip()

    return False


def _summary_row_count(value: object) -> int | None:
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


def _normalized_row(
    raw_row: Mapping[object, object],
) -> dict[str, object]:
    normalized: dict[str, object] = {}
    original_headers: dict[str, str] = {}

    for header, value in raw_row.items():
        normalized_header = normalize_header(header)

        if normalized_header in normalized:
            raise RawItemsDetailFileError(
                "duplicate_normalized_column",
                (
                    "More than one Items detail column "
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
        raise RawItemsDetailFileError(
            "missing_required_column",
            (
                "The Items detail row is missing "
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
    normalized_header = normalize_header(header)

    if normalized_header not in row:
        return False, None

    return True, row[normalized_header]


def _is_export_summary_footer(
    raw_row: Mapping[object, object],
    *,
    source_row_count: int,
    is_last_row: bool,
) -> bool:
    if not is_last_row:
        return False

    row = _normalized_row(raw_row)

    article = row.get(normalize_header("Article"))
    sale_datetime = row.get(
        normalize_header("Date de vente")
    )
    source_code = row.get(
        normalize_header("Utilisateur")
    )
    client = row.get(normalize_header("Client"))
    document = row.get(normalize_header("Document"))
    document_number = row.get(
        normalize_header("Num doc.")
    )
    quantity = row.get(
        normalize_header(QTY_SOLD_HEADER)
    )

    if not all(
        _is_blank_value(value)
        for value in (
            sale_datetime,
            source_code,
            client,
            document,
            document_number,
        )
    ):
        return False

    if _is_blank_value(quantity):
        return False

    return _summary_row_count(article) == source_row_count


def adapt_raw_items_detail_file(
    source: Any,
    *,
    truck_mapping: Mapping[object, object],
    source_exclusions: Mapping[object, object] | None = None,
    original_filename: str | None = None,
) -> RawItemsDetailFileResult:
    try:
        raw_result = read_raw_excel_rows(
            source,
            original_filename=original_filename,
        )
    except RawExcelReadError as exc:
        raise RawItemsDetailFileError(
            "raw_excel_read_failed",
            "The Items detail Excel file could not be read.",
            details={
                "cause_code": exc.code,
                "cause_details": dict(exc.details),
            },
        ) from exc

    normalized_exclusions = {
        _canonical_source_code(source_code): str(
            reason or "OUT_OF_SCOPE"
        ).strip().upper()
        for source_code, reason
        in (source_exclusions or {}).items()
    }

    adapted_rows: list[AdaptedItemsDetailRow] = []
    excluded_source_rows: list[
        ExcludedItemsDetailSourceRow
    ] = []

    raw_rows = raw_result.rows

    for index, raw_row in enumerate(raw_rows):
        raw_values = raw_row.as_dict()

        if _is_export_summary_footer(
            raw_values,
            source_row_count=(
                len(adapted_rows)
                + len(excluded_source_rows)
            ),
            is_last_row=(
                index == len(raw_rows) - 1
            ),
        ):
            continue

        try:
            row = _normalized_row(raw_values)
            article = _required_value(row, "Article")
            sale_datetime = _required_value(
                row,
                "Date de vente",
            )
            quantity = _required_value(
                row,
                QTY_SOLD_HEADER,
            )
            source_code_raw = _required_value(
                row,
                "Utilisateur",
            )
            client = _required_value(row, "Client")
            document = _required_value(
                row,
                "Document",
            )
            document_number = _required_value(
                row,
                "Num doc.",
            )
        except RawItemsDetailFileError as exc:
            raise RawItemsDetailFileError(
                "row_adaptation_failed",
                "An Items detail row could not be adapted.",
                details={
                    "excel_row_number": raw_row.row_number,
                    "cause_code": exc.code,
                    "cause_details": dict(exc.details),
                },
            ) from exc

        canonical_source_code = _canonical_source_code(
            source_code_raw
        )
        exclusion_reason = normalized_exclusions.get(
            canonical_source_code
        )

        if exclusion_reason is not None:
            excluded_source_rows.append(
                ExcludedItemsDetailSourceRow(
                    excel_row_number=raw_row.row_number,
                    source_code=canonical_source_code,
                    reason=exclusion_reason,
                    sale_datetime_raw=sale_datetime,
                    article=article,
                    quantity_raw=quantity,
                    client=client,
                    document=document,
                    document_number=document_number,
                )
            )
            continue

        try:
            internal_code = map_source_truck_code(
                source_code_raw,
                mapping=truck_mapping,
            )
        except SourceTruckMappingError as exc:
            raise RawItemsDetailFileError(
                "row_adaptation_failed",
                "An Items detail row could not be adapted.",
                details={
                    "excel_row_number": raw_row.row_number,
                    "cause_code": exc.code,
                    "cause_details": dict(exc.details),
                },
            ) from exc

        adapted = {
            "VAN": internal_code,
            "Article": article,
            QTY_SOLD_HEADER: quantity,
            "Client": client,
            "Date de vente": sale_datetime,
            "Utilisateur": source_code_raw,
            "Document": document,
            "Num doc.": document_number,
        }

        for header in OPTIONAL_ITEMS_DETAIL_HEADERS:
            has_value, value = _optional_value(row, header)
            if has_value:
                adapted[header] = value

        adapted_rows.append(
            AdaptedItemsDetailRow(
                excel_row_number=raw_row.row_number,
                values=adapted,
            )
        )

    return RawItemsDetailFileResult(
        filename=raw_result.filename,
        worksheet_name=raw_result.worksheet_name,
        rows=tuple(adapted_rows),
        excluded_source_rows=tuple(
            excluded_source_rows
        ),
    )


def to_report_row_read_result(
    result: RawItemsDetailFileResult,
) -> ReportRowReadResult:
    optional_headers = tuple(
        header
        for header in OPTIONAL_ITEMS_DETAIL_HEADERS
        if any(
            header in row.values
            for row in result.rows
        )
    )

    headers = (
        CANONICAL_ITEMS_DETAIL_HEADERS
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
