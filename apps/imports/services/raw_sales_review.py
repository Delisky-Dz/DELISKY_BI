from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from .raw_sales_file import (
    RawSalesFileError,
    RawSalesFileResult,
    adapt_raw_sales_file,
    to_report_row_read_result,
)
from .report_row_cleaner import (
    clean_report_rows_from_metadata,
)
from .report_row_reader import ReportRowReadResult
from .source_truck_mapper import (
    SourceTruckMappingError,
)
from .value_normalizers import (
    ValueNormalizationError,
    is_blank_value,
    parse_datetime_value,
)


class RawSalesImportReviewError(Exception):
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
class RawSalesReviewResult:
    adapted: RawSalesFileResult
    row_result: ReportRowReadResult
    cleaning_result: Any
    period_start: date
    period_end: date


def _coerce_period_date(
    value: Any,
    *,
    field_name: str,
) -> date:
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        cleaned = value.strip()

        try:
            return date.fromisoformat(cleaned)
        except ValueError:
            pass

    raise RawSalesImportReviewError(
        "invalid_period_date",
        (
            f"{field_name} must be a valid "
            "ISO date."
        ),
        details={
            "field_name": field_name,
            "value": str(value),
        },
    )


def _validate_raw_sales_period(
    result: RawSalesFileResult,
    *,
    period_start: date,
    period_end: date,
) -> None:
    for row in result.rows:
        raw_datetime = row.values.get(
            "Date&Heure"
        )

        if is_blank_value(raw_datetime):
            raise RawSalesImportReviewError(
                "missing_datetime",
                (
                    "The raw Sales Date&Heure "
                    "value is required."
                ),
                details={
                    "excel_row_number": (
                        row.excel_row_number
                    ),
                },
            )

        try:
            parsed_datetime = parse_datetime_value(
                raw_datetime
            )
        except ValueNormalizationError as exc:
            raise RawSalesImportReviewError(
                "invalid_datetime",
                (
                    "The raw Sales Date&Heure "
                    "value is invalid."
                ),
                details={
                    "excel_row_number": (
                        row.excel_row_number
                    ),
                    "raw_value": str(
                        raw_datetime
                    ),
                },
            ) from exc

        if parsed_datetime is None:
            raise RawSalesImportReviewError(
                "missing_datetime",
                (
                    "The raw Sales Date&Heure "
                    "value is required."
                ),
                details={
                    "excel_row_number": (
                        row.excel_row_number
                    ),
                },
            )

        sale_date = parsed_datetime.date()

        if (
            sale_date < period_start
            or sale_date > period_end
        ):
            raise RawSalesImportReviewError(
                "sale_outside_period",
                (
                    "The raw Sales file contains "
                    "a sale outside the selected period."
                ),
                details={
                    "excel_row_number": (
                        row.excel_row_number
                    ),
                    "sale_date": (
                        sale_date.isoformat()
                    ),
                    "period_start": (
                        period_start.isoformat()
                    ),
                    "period_end": (
                        period_end.isoformat()
                    ),
                },
            )


def prepare_raw_sales_review(
    source: Any,
    *,
    truck_mapping: dict[object, object],
    period_start: Any,
    period_end: Any,
    original_filename: str | None = None,
) -> RawSalesReviewResult:
    normalized_period_start = _coerce_period_date(
        period_start,
        field_name="period_start",
    )
    normalized_period_end = _coerce_period_date(
        period_end,
        field_name="period_end",
    )

    if (
        normalized_period_end
        < normalized_period_start
    ):
        raise RawSalesImportReviewError(
            "invalid_period_range",
            (
                "period_end cannot be before "
                "period_start."
            ),
        )

    try:
        adapted = adapt_raw_sales_file(
            source,
            truck_mapping=truck_mapping,
            original_filename=original_filename,
        )
    except (
        RawSalesFileError,
        SourceTruckMappingError,
    ) as exc:
        raise RawSalesImportReviewError(
            "raw_sales_file_failed",
            (
                "The raw Sales file could not "
                "be prepared for review."
            ),
            details={
                "cause_code": exc.code,
                "cause_details": dict(
                    getattr(exc, "details", {})
                ),
            },
        ) from exc

    _validate_raw_sales_period(
        adapted,
        period_start=normalized_period_start,
        period_end=normalized_period_end,
    )

    row_result = to_report_row_read_result(
        adapted
    )

    cleaning_result = (
        clean_report_rows_from_metadata(
            row_result,
            period_start=normalized_period_start,
            period_end=normalized_period_end,
        )
    )

    return RawSalesReviewResult(
        adapted=adapted,
        row_result=row_result,
        cleaning_result=cleaning_result,
        period_start=normalized_period_start,
        period_end=normalized_period_end,
    )
