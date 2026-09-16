from datetime import date
from typing import Any

from .report_row_cleaner import (
    CleanedReportRow,
    ReportCleaningResult,
    RowCleaningIssue,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    STATUS_ACCEPTED,
    STATUS_EXCLUDED,
    clean_report_rows_from_metadata,
)
from .report_row_reader import ReportRowReadResult
from .value_normalizers import (
    ValueNormalizationError,
    normalize_lookup_text,
    normalize_text,
    parse_datetime_value,
)


class RawItemsDetailCleaningError(Exception):
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
    if isinstance(value, date):
        return value

    if isinstance(value, str):
        cleaned = value.strip()
        try:
            return date.fromisoformat(cleaned)
        except ValueError:
            pass

    raise RawItemsDetailCleaningError(
        "invalid_period_date",
        f"{field_name} must be a valid ISO date.",
        details={
            "field_name": field_name,
            "value": str(value),
        },
    )


def _detail_issue(
    code: str,
    message: str,
    *,
    field_name: str,
    raw_value: Any,
    details: dict[str, Any] | None = None,
) -> RowCleaningIssue:
    return RowCleaningIssue(
        code=code,
        severity=SEVERITY_ERROR,
        message=message,
        field=field_name,
        raw_value=raw_value,
        details=details or {},
    )


def _detail_issues(
    issues: list[RowCleaningIssue],
) -> list[RowCleaningIssue]:
    result: list[RowCleaningIssue] = []

    for issue in issues:
        if (
            issue.code == "missing_client"
            and issue.severity == SEVERITY_ERROR
        ):
            result.append(
                RowCleaningIssue(
                    code=issue.code,
                    severity=SEVERITY_WARNING,
                    message=(
                        "The Items transaction has no client; "
                        "it remains valid for product, truck, "
                        "seller and period analytics but must "
                        "not be attributed to a client."
                    ),
                    field=issue.field,
                    raw_value=issue.raw_value,
                    details={
                        **issue.details,
                        "client_analytics_eligible": False,
                    },
                )
            )
            continue

        result.append(issue)

    return result


def clean_raw_items_detail_rows(
    row_result: ReportRowReadResult,
    *,
    period_start: Any,
    period_end: Any,
) -> ReportCleaningResult:
    if row_result.report_type != "ITEMS":
        raise RawItemsDetailCleaningError(
            "invalid_report_type",
            "Transaction-level Items cleaning requires ITEMS rows.",
            details={
                "report_type": row_result.report_type,
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
        raise RawItemsDetailCleaningError(
            "invalid_period_range",
            "period_end cannot be before period_start.",
        )

    base_result = clean_report_rows_from_metadata(
        row_result,
        period_start=normalized_period_start,
        period_end=normalized_period_end,
    )

    cleaned_rows: list[CleanedReportRow] = []

    for raw_row, base_row in zip(
        row_result.rows,
        base_result.rows,
        strict=True,
    ):
        raw = raw_row.as_dict()
        cleaned = base_row.cleaned_dict()
        issues = _detail_issues(
            list(base_row.issues)
        )

        sale_datetime_raw = raw.get("Date de vente")

        try:
            sale_datetime = parse_datetime_value(
                sale_datetime_raw
            )
        except ValueNormalizationError:
            sale_datetime = None
            issues.append(
                _detail_issue(
                    "invalid_datetime",
                    "The Items sale datetime is invalid.",
                    field_name="Date de vente",
                    raw_value=sale_datetime_raw,
                )
            )

        if sale_datetime is None:
            if not any(
                issue.code == "invalid_datetime"
                and issue.field == "Date de vente"
                for issue in issues
            ):
                issues.append(
                    _detail_issue(
                        "missing_datetime",
                        "The Items sale datetime is required.",
                        field_name="Date de vente",
                        raw_value=sale_datetime_raw,
                    )
                )
        elif (
            sale_datetime.date() < normalized_period_start
            or sale_datetime.date() > normalized_period_end
        ):
            issues.append(
                _detail_issue(
                    "date_outside_period",
                    (
                        "The Items sale datetime is outside "
                        "the declared detail-report period."
                    ),
                    field_name="Date de vente",
                    raw_value=sale_datetime_raw,
                    details={
                        "period_start": (
                            normalized_period_start.isoformat()
                        ),
                        "period_end": (
                            normalized_period_end.isoformat()
                        ),
                    },
                )
            )

        source_user = normalize_text(
            raw.get("Utilisateur")
        )
        document = normalize_text(raw.get("Document"))
        document_number = normalize_text(
            raw.get("Num doc.")
        )

        cleaned["sale_datetime"] = sale_datetime
        cleaned["source_user"] = source_user
        cleaned["source_user_normalized"] = (
            normalize_lookup_text(source_user)
        )
        cleaned["document"] = document
        cleaned["document_number"] = document_number

        has_detail_error = any(
            issue.severity == SEVERITY_ERROR
            for issue in issues
        )
        has_forced_exclusion = any(
            issue.code == "negative_quantity"
            for issue in issues
        )

        if has_detail_error or has_forced_exclusion:
            status = STATUS_EXCLUDED
        else:
            status = STATUS_ACCEPTED

        cleaned_rows.append(
            CleanedReportRow(
                row_number=base_row.row_number,
                status=status,
                raw_values=base_row.raw_values,
                cleaned_values=tuple(cleaned.items()),
                issues=tuple(issues),
            )
        )

    return ReportCleaningResult(
        filename=row_result.filename,
        report_type=row_result.report_type,
        rows=tuple(cleaned_rows),
    )
