from datetime import date, datetime
from typing import Any, Mapping

from apps.imports.models import ImportBatch

from .batch_review import (
    ImportBatchReviewError,
    ImportBatchReviewResult,
    _get_active_brand,
    _persist_import_review,
    _validate_user,
)
from .raw_chargement_brand_validator import (
    validate_raw_chargement_brand,
)
from .raw_opening_stock_file import (
    RawOpeningStockFileError,
    adapt_raw_opening_stock_file,
    to_report_row_read_result,
)
from .report_row_cleaner import (
    clean_report_rows_from_metadata,
)
from .review_summary import (
    build_import_review_summary_from_metadata,
)
from .row_staging import prepare_import_rows


class RawOpeningStockImportReviewError(Exception):
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


def _coerce_stock_date(
    value: Any,
) -> date:
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        try:
            return date.fromisoformat(
                value.strip()
            )
        except ValueError:
            pass

    raise RawOpeningStockImportReviewError(
        "invalid_stock_date",
        "stock_date must be a valid ISO date.",
        details={
            "field_name": "stock_date",
        },
    )


def _serialize_brand_issue(
    issue: Any,
) -> dict[str, Any]:
    return {
        "code": issue.code,
        "excel_row_number": issue.excel_row_number,
        "van": issue.van,
        **issue.details,
    }


def create_raw_opening_stock_import_review(
    source: Any,
    *,
    uploaded_by: Any,
    brand_code: str,
    stock_date: Any,
    truck_mapping: Mapping[object, object],
    reviewed_by: Any | None = None,
    batch: ImportBatch | None = None,
    original_filename: str | None = None,
) -> ImportBatchReviewResult:
    _validate_user(
        uploaded_by,
        "uploaded_by",
    )

    reviewer = reviewed_by or uploaded_by

    _validate_user(
        reviewer,
        "reviewed_by",
    )

    try:
        selected_brand = _get_active_brand(
            brand_code
        )
    except ImportBatchReviewError as exc:
        raise RawOpeningStockImportReviewError(
            exc.code,
            exc.message,
            details=dict(exc.details),
        ) from exc

    selected_brand_code = selected_brand.code

    try:
        adapted = adapt_raw_opening_stock_file(
            source,
            truck_mapping=truck_mapping,
            original_filename=original_filename,
        )
    except RawOpeningStockFileError as exc:
        raise RawOpeningStockImportReviewError(
            "raw_file_adaptation_failed",
            (
                "The raw Opening Stock file "
                "could not be adapted."
            ),
            details={
                "cause_code": exc.code,
                "cause_details": dict(exc.details),
            },
        ) from exc

    brand_validation = (
        validate_raw_chargement_brand(
            adapted.rows,
            brand_code=selected_brand_code,
        )
    )

    if not brand_validation.is_valid:
        raise RawOpeningStockImportReviewError(
            "brand_validation_failed",
            (
                "The raw Opening Stock file contains "
                "truck rows that do not belong to "
                "the selected distribution brand."
            ),
            details={
                "issues": [
                    _serialize_brand_issue(issue)
                    for issue
                    in brand_validation.issues
                ],
            },
        )

    normalized_stock_date = (
        _coerce_stock_date(
            stock_date
        )
    )

    row_result = (
        to_report_row_read_result(
            adapted
        )
    )

    cleaning_result = (
        clean_report_rows_from_metadata(
            row_result,
            period_start=normalized_stock_date,
            period_end=normalized_stock_date,
        )
    )

    summary = (
        build_import_review_summary_from_metadata(
            brand_code=selected_brand_code,
            period_start=normalized_stock_date,
            period_end=normalized_stock_date,
            row_result=row_result,
            cleaning_result=cleaning_result,
        )
    )

    prepared_rows = prepare_import_rows(
        cleaning_result
    )

    return _persist_import_review(
        source,
        uploaded_by=uploaded_by,
        reviewer=reviewer,
        batch=batch,
        brand_code=selected_brand_code,
        report_type="OPENING_STOCK",
        period_start=normalized_stock_date,
        period_end=normalized_stock_date,
        worksheet_name=adapted.worksheet_name,
        summary=summary,
        prepared_rows=prepared_rows,
    )