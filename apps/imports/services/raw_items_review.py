from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from .raw_items_file import (
    RawItemsFileError,
    RawItemsFileResult,
    adapt_raw_items_file,
    to_report_row_read_result,
)
from .report_row_cleaner import (
    clean_report_rows_from_metadata,
)
from .report_row_reader import ReportRowReadResult


class RawItemsImportReviewError(Exception):
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
class RawItemsReviewResult:
    adapted: RawItemsFileResult
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

    raise RawItemsImportReviewError(
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


def prepare_raw_items_review(
    source: Any,
    *,
    truck_mapping: dict[object, object],
    period_start: Any,
    period_end: Any,
    original_filename: str | None = None,
) -> RawItemsReviewResult:
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
        raise RawItemsImportReviewError(
            "invalid_period_range",
            (
                "period_end cannot be before "
                "period_start."
            ),
        )

    try:
        adapted = adapt_raw_items_file(
            source,
            truck_mapping=truck_mapping,
            original_filename=original_filename,
        )
    except RawItemsFileError as exc:
        raise RawItemsImportReviewError(
            "raw_items_file_failed",
            (
                "The raw Items file could not "
                "be prepared for review."
            ),
            details={
                "cause_code": exc.code,
                "cause_details": dict(
                    exc.details
                ),
            },
        ) from exc

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

    return RawItemsReviewResult(
        adapted=adapted,
        row_result=row_result,
        cleaning_result=cleaning_result,
        period_start=normalized_period_start,
        period_end=normalized_period_end,
    )
