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
    AdaptedChargementRow,
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
from .value_normalizers import (
    ValueNormalizationError,
    is_blank_value,
    parse_datetime_value,
    parse_decimal_value,
)


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


def _validate_raw_chargement_period(
    rows: tuple[AdaptedChargementRow, ...],
    *,
    period_start: Any,
    period_end: Any,
) -> None:
    """Reject dated in-scope rows before any review or source file is persisted.

    Adaptation already removes export footers and configured source exclusions.
    Keep support for legacy files without a Date&Heure column.
    """
    offending: list[tuple[int, date]] = []
    for row in rows:
        if "Date&Heure" not in row.values:
            continue

        raw_datetime = row.values[
            "Date&Heure"
        ]

        if is_blank_value(raw_datetime):
            quantity_raw = row.values.get(
                "Qt\u00e9"
            )
            article_is_blank = is_blank_value(
                row.values.get("Article")
            )

            try:
                quantity = parse_decimal_value(
                    quantity_raw
                )
            except ValueNormalizationError:
                quantity = None
                quantity_is_invalid = True
            else:
                quantity_is_invalid = False

            is_stopped_candidate = (
                article_is_blank
                and not quantity_is_invalid
                and (
                    is_blank_value(quantity_raw)
                    or quantity == 0
                )
            )

            if is_stopped_candidate:
                continue

            raise RawChargementImportReviewError(
                "missing_datetime",
                (
                    "The raw Chargement Date&Heure "
                    "value is required for an active row."
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
            raise RawChargementImportReviewError(
                "invalid_datetime",
                (
                    "The raw Chargement Date&Heure "
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
            raise RawChargementImportReviewError(
                "invalid_datetime",
                (
                    "The raw Chargement Date&Heure "
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
            )

        row_date = parsed_datetime.date()

        if (
            row_date < period_start
            or row_date > period_end
        ):
            offending.append((row.excel_row_number, row_date))

    if offending:
        earliest = min(day for _, day in offending).isoformat()
        latest = max(day for _, day in offending).isoformat()
        sample = [number for number, _ in offending[:20]]
        raise RawChargementImportReviewError(
            "chargement_row_outside_selected_period",
            (
                f"{len(offending)} Chargement row(s) dated {earliest} to "
                f"{latest} are outside the selected period "
                f"{period_start.isoformat()} to {period_end.isoformat()}. "
                f"Sample Excel rows: {', '.join(map(str, sample))}. "
                "Prepare a separate file for the selected period and upload it again."
            ),
            details={
                "out_of_period_count": len(offending),
                "earliest_offending_date": earliest,
                "latest_offending_date": latest,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "sample_excel_row_numbers": sample,
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

    _validate_raw_chargement_period(
        adapted.rows,
        period_start=normalized_period_start,
        period_end=normalized_period_end,
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
