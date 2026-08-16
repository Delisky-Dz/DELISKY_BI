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
from .raw_chargement_file import (
    RawChargementFileError,
    adapt_raw_chargement_file,
    to_report_row_read_result,
)
from .report_row_cleaner import (
    clean_report_rows_from_metadata,
)
from .review_summary import (
    build_import_review_summary_from_metadata,
)
from .row_staging import prepare_import_rows


class RawChargementImportReviewError(Exception):
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
        try:
            return date.fromisoformat(
                value.strip()
            )
        except ValueError:
            pass

    raise RawChargementImportReviewError(
        "invalid_period_metadata",
        (
            f"{field_name} must be a valid "
            "ISO date."
        ),
        details={
            "field_name": field_name,
        },
    )


def _serialize_brand_issue(issue: Any) -> dict[str, Any]:
    return {
        "code": issue.code,
        "excel_row_number": issue.excel_row_number,
        "van": issue.van,
        **issue.details,
    }


def create_raw_chargement_import_review(
    source: Any,
    *,
    uploaded_by: Any,
    brand_code: str,
    period_start: Any,
    period_end: Any,
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
        raise RawChargementImportReviewError(
            exc.code,
            exc.message,
            details=dict(exc.details),
        ) from exc

    selected_brand_code = selected_brand.code

    try:
        adapted = adapt_raw_chargement_file(
            source,
            truck_mapping=truck_mapping,
            original_filename=original_filename,
        )
    except RawChargementFileError as exc:
        raise RawChargementImportReviewError(
            "raw_file_adaptation_failed",
            (
                "The raw Chargement file could not "
                "be adapted."
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
        raise RawChargementImportReviewError(
            "brand_validation_failed",
            (
                "The raw Chargement file contains "
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

    normalized_period_start = _coerce_period_date(
        period_start,
        field_name="period_start",
    )
    normalized_period_end = _coerce_period_date(
        period_end,
        field_name="period_end",
    )

    if normalized_period_end < normalized_period_start:
        raise RawChargementImportReviewError(
            "invalid_period_range",
            (
                "period_end cannot be before "
                "period_start."
            ),
        )

    row_result = to_report_row_read_result(
        adapted
    )

    cleaning_result = (
        clean_report_rows_from_metadata(
            row_result
        )
    )

    summary = (
        build_import_review_summary_from_metadata(
            brand_code=selected_brand_code,
            period_start=normalized_period_start,
            period_end=normalized_period_end,
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
        report_type="CHARGEMENT",
        period_start=normalized_period_start,
        period_end=normalized_period_end,
        worksheet_name=adapted.worksheet_name,
        summary=summary,
        prepared_rows=prepared_rows,
    )
