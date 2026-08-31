from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from apps.imports.models import (
    ImportBatchStatus,
    ImportReportType,
    ImportRow,
    ImportRowStatus,
)

from .typed_values import (
    AnalyticalValueError,
    read_optional_datetime,
    read_optional_text,
    read_required_date,
    read_required_datetime,
    read_required_decimal,
    read_required_lookup_text,
    read_required_text,
)


class AnalyticalRowError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        row_id: int | None = None,
        batch_id: int | None = None,
        excel_row_number: int | None = None,
        field_name: str = "",
        raw_value: Any = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.row_id = row_id
        self.batch_id = batch_id
        self.excel_row_number = excel_row_number
        self.field_name = field_name
        self.raw_value = raw_value


@dataclass(frozen=True, slots=True)
class BaseAnalyticalRow:
    import_row_id: int
    batch_id: int
    brand_id: int
    excel_row_number: int
    period_start: date
    period_end: date
    van: str
    van_normalized: str


@dataclass(frozen=True, slots=True)
class OpeningStockAnalyticalRow(BaseAnalyticalRow):
    article: str
    article_normalized: str
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class ChargementAnalyticalRow(BaseAnalyticalRow):
    article: str
    article_normalized: str
    quantity: Decimal
    chargement_datetime: datetime | None = None


@dataclass(frozen=True, slots=True)
class SalesAnalyticalRow(BaseAnalyticalRow):
    sale_datetime: datetime
    client: str | None
    client_normalized: str | None
    total: Decimal
    region: str | None
    region_normalized: str | None


@dataclass(frozen=True, slots=True)
class ItemAnalyticalRow(BaseAnalyticalRow):
    article: str
    article_normalized: str
    quantity_sold: Decimal
    client: str
    client_normalized: str


@dataclass(frozen=True, slots=True)
class PosAnalyticalRow(BaseAnalyticalRow):
    client: str
    client_normalized: str
    visit_date: date
    ignoration_message: str | None
    ignoration_cause: str | None


AcceptedAnalyticalRow = (
    OpeningStockAnalyticalRow
    | ChargementAnalyticalRow
    | SalesAnalyticalRow
    | ItemAnalyticalRow
    | PosAnalyticalRow
)


def _row_error(
    row: ImportRow,
    code: str,
    message: str,
    *,
    field_name: str = "",
    raw_value: Any = None,
) -> AnalyticalRowError:
    return AnalyticalRowError(
        code,
        message,
        row_id=row.pk,
        batch_id=row.batch_id,
        excel_row_number=row.excel_row_number,
        field_name=field_name,
        raw_value=raw_value,
    )


def _validate_row_context(
    row: ImportRow,
    expected_report_type: str,
) -> None:
    if row.pk is None or row.batch_id is None:
        raise _row_error(
            row,
            "unsaved_import_row",
            "The analytical row must already be saved.",
        )

    if row.batch.status != ImportBatchStatus.APPROVED:
        raise _row_error(
            row,
            "batch_not_approved",
            "Only rows from approved batches may be analyzed.",
        )

    if row.status != ImportRowStatus.ACCEPTED:
        raise _row_error(
            row,
            "row_not_accepted",
            "Only accepted rows may enter calculations.",
        )

    if row.batch.report_type != expected_report_type:
        raise _row_error(
            row,
            "report_type_mismatch",
            (
                "The import row report type does not match "
                "the requested analytical row type."
            ),
        )

    if not isinstance(row.cleaned_data, dict):
        raise _row_error(
            row,
            "invalid_cleaned_data",
            "The cleaned analytical data must be a dictionary.",
        )


def _base_values(
    row: ImportRow,
) -> dict[str, Any]:
    data = row.cleaned_data

    return {
        "import_row_id": row.pk,
        "batch_id": row.batch_id,
        "brand_id": row.batch.brand_id,
        "excel_row_number": row.excel_row_number,
        "period_start": row.batch.period_start,
        "period_end": row.batch.period_end,
        "van": read_required_text(
            data,
            "van",
        ),
        "van_normalized": read_required_lookup_text(
            data,
            "van_normalized",
        ),
    }


def _require_non_negative(
    row: ImportRow,
    value: Decimal,
    field_name: str,
) -> None:
    if value < 0:
        raise _row_error(
            row,
            "negative_analytical_value",
            (
                f"The {field_name} value cannot be negative "
                "in an accepted analytical row."
            ),
            field_name=field_name,
            raw_value=value,
        )


def _require_date_inside_batch(
    row: ImportRow,
    value: date,
    field_name: str,
) -> None:
    if (
        value < row.batch.period_start
        or value > row.batch.period_end
    ):
        raise _row_error(
            row,
            "date_outside_batch_period",
            (
                f"The {field_name} value is outside "
                "the import batch period."
            ),
            field_name=field_name,
            raw_value=value,
        )


def _convert_value_error(
    row: ImportRow,
    error: AnalyticalValueError,
) -> AnalyticalRowError:
    return _row_error(
        row,
        error.code,
        error.message,
        field_name=error.field_name,
        raw_value=error.raw_value,
    )


def parse_opening_stock_row(
    row: ImportRow,
) -> OpeningStockAnalyticalRow:
    _validate_row_context(
        row,
        ImportReportType.OPENING_STOCK,
    )

    try:
        quantity = read_required_decimal(
            row.cleaned_data,
            "total_units",
        )
        _require_non_negative(
            row,
            quantity,
            "total_units",
        )

        return OpeningStockAnalyticalRow(
            **_base_values(row),
            article=read_required_text(
                row.cleaned_data,
                "article",
            ),
            article_normalized=read_required_lookup_text(
                row.cleaned_data,
                "article_normalized",
            ),
            quantity=quantity,
        )
    except AnalyticalValueError as exc:
        raise _convert_value_error(
            row,
            exc,
        ) from exc


def parse_chargement_row(
    row: ImportRow,
) -> ChargementAnalyticalRow:
    _validate_row_context(
        row,
        ImportReportType.CHARGEMENT,
    )

    try:
        quantity = read_required_decimal(
            row.cleaned_data,
            "total_units",
        )
        chargement_datetime = read_optional_datetime(
            row.cleaned_data,
            "chargement_datetime",
        )

        return ChargementAnalyticalRow(
            **_base_values(row),
            article=read_required_text(
                row.cleaned_data,
                "article",
            ),
            article_normalized=read_required_lookup_text(
                row.cleaned_data,
                "article_normalized",
            ),
            quantity=quantity,
            chargement_datetime=chargement_datetime,
        )
    except AnalyticalValueError as exc:
        raise _convert_value_error(
            row,
            exc,
        ) from exc


def parse_sales_row(
    row: ImportRow,
) -> SalesAnalyticalRow:
    _validate_row_context(
        row,
        ImportReportType.SALES,
    )

    try:
        sale_datetime = read_required_datetime(
            row.cleaned_data,
            "sale_datetime",
        )
        total = read_required_decimal(
            row.cleaned_data,
            "total",
        )

        _require_date_inside_batch(
            row,
            sale_datetime.date(),
            "sale_datetime",
        )

        return SalesAnalyticalRow(
            **_base_values(row),
            sale_datetime=sale_datetime,
            client=read_optional_text(
                row.cleaned_data,
                "client",
            ),
            client_normalized=read_optional_text(
                row.cleaned_data,
                "client_normalized",
            ),
            total=total,
            region=read_optional_text(
                row.cleaned_data,
                "region",
            ),
            region_normalized=read_optional_text(
                row.cleaned_data,
                "region_normalized",
            ),
        )
    except AnalyticalValueError as exc:
        raise _convert_value_error(
            row,
            exc,
        ) from exc


def parse_item_row(
    row: ImportRow,
) -> ItemAnalyticalRow:
    _validate_row_context(
        row,
        ImportReportType.ITEMS,
    )

    try:
        quantity_sold = read_required_decimal(
            row.cleaned_data,
            "total_units",
        )
        _require_non_negative(
            row,
            quantity_sold,
            "total_units",
        )

        return ItemAnalyticalRow(
            **_base_values(row),
            article=read_required_text(
                row.cleaned_data,
                "article",
            ),
            article_normalized=read_required_lookup_text(
                row.cleaned_data,
                "article_normalized",
            ),
            quantity_sold=quantity_sold,
            client=read_required_text(
                row.cleaned_data,
                "client",
            ),
            client_normalized=read_required_lookup_text(
                row.cleaned_data,
                "client_normalized",
            ),
        )
    except AnalyticalValueError as exc:
        raise _convert_value_error(
            row,
            exc,
        ) from exc


def parse_pos_row(
    row: ImportRow,
) -> PosAnalyticalRow:
    _validate_row_context(
        row,
        ImportReportType.POS,
    )

    try:
        visit_date = read_required_date(
            row.cleaned_data,
            "visit_date",
        )
        _require_date_inside_batch(
            row,
            visit_date,
            "visit_date",
        )

        return PosAnalyticalRow(
            **_base_values(row),
            client=read_required_text(
                row.cleaned_data,
                "client",
            ),
            client_normalized=read_required_lookup_text(
                row.cleaned_data,
                "client_normalized",
            ),
            visit_date=visit_date,
            ignoration_message=read_optional_text(
                row.cleaned_data,
                "ignoration_message",
            ),
            ignoration_cause=read_optional_text(
                row.cleaned_data,
                "ignoration_cause",
            ),
        )
    except AnalyticalValueError as exc:
        raise _convert_value_error(
            row,
            exc,
        ) from exc


def parse_accepted_row(
    row: ImportRow,
) -> AcceptedAnalyticalRow:
    parser_by_report_type = {
        ImportReportType.OPENING_STOCK: parse_opening_stock_row,
        ImportReportType.CHARGEMENT: parse_chargement_row,
        ImportReportType.SALES: parse_sales_row,
        ImportReportType.ITEMS: parse_item_row,
        ImportReportType.POS: parse_pos_row,
    }

    try:
        parser = parser_by_report_type[
            row.batch.report_type
        ]
    except KeyError as exc:
        raise _row_error(
            row,
            "unsupported_report_type",
            (
                "No analytical parser exists for "
                f"{row.batch.report_type}."
            ),
        ) from exc

    return parser(row)
