from dataclasses import dataclass, field as dataclass_field
from datetime import date
from decimal import Decimal
from typing import Any

from .report_row_reader import ReportRowReadResult
from .value_normalizers import (
    ValueNormalizationError,
    is_blank_value,
    normalize_lookup_text,
    normalize_text,
    parse_date_value,
    parse_datetime_value,
    parse_decimal_value,
)


STATUS_ACCEPTED = "ACCEPTED"
STATUS_EXCLUDED = "EXCLUDED"
STATUS_STOPPED = "STOPPED"

SEVERITY_ERROR = "ERROR"
SEVERITY_WARNING = "WARNING"


QTY_HEADER = "Qt\u00e9"
QTY_SOLD_HEADER = "Qt\u00e9 vendue"

class ReportRowCleaningError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
    ):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class RowCleaningIssue:
    code: str
    severity: str
    message: str
    field: str = ""
    raw_value: Any = None
    details: dict[str, Any] = dataclass_field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CleanedReportRow:
    row_number: int
    status: str
    raw_values: tuple[tuple[str, Any], ...]
    cleaned_values: tuple[tuple[str, Any], ...]
    issues: tuple[RowCleaningIssue, ...]

    def raw_dict(self) -> dict[str, Any]:
        return dict(self.raw_values)

    def cleaned_dict(self) -> dict[str, Any]:
        return dict(self.cleaned_values)


@dataclass(frozen=True, slots=True)
class ReportCleaningResult:
    filename: str
    report_type: str
    rows: tuple[CleanedReportRow, ...]

    @property
    def total_rows(self) -> int:
        return len(self.rows)

    @property
    def accepted_rows(self) -> int:
        return sum(
            row.status == STATUS_ACCEPTED
            for row in self.rows
        )

    @property
    def excluded_rows(self) -> int:
        return sum(
            row.status == STATUS_EXCLUDED
            for row in self.rows
        )

    @property
    def stopped_rows(self) -> int:
        return sum(
            row.status == STATUS_STOPPED
            for row in self.rows
        )

    @property
    def warning_count(self) -> int:
        return sum(
            issue.severity == SEVERITY_WARNING
            for row in self.rows
            for issue in row.issues
        )

    @property
    def error_count(self) -> int:
        return sum(
            issue.severity == SEVERITY_ERROR
            for row in self.rows
            for issue in row.issues
        )


def _issue(
    code: str,
    severity: str,
    message: str,
    *,
    field_name: str = "",
    raw_value: Any = None,
    details: dict[str, Any] | None = None,
) -> RowCleaningIssue:
    return RowCleaningIssue(
        code=code,
        severity=severity,
        message=message,
        field=field_name,
        raw_value=raw_value,
        details=details or {},
    )


def _normalize_van(
    raw: dict[str, Any],
    issues: list[RowCleaningIssue],
) -> tuple[str | None, str | None]:
    value = raw.get("VAN")
    text = normalize_text(value)

    if text is None:
        issues.append(
            _issue(
                "missing_van",
                SEVERITY_ERROR,
                "The VAN value is required.",
                field_name="VAN",
                raw_value=value,
            )
        )
        return None, None

    return text, normalize_lookup_text(text)


def _parse_number(
    value: Any,
    field_name: str,
    issues: list[RowCleaningIssue],
    *,
    required: bool = True,
) -> Decimal | None:
    try:
        parsed = parse_decimal_value(value)
    except ValueNormalizationError:
        issues.append(
            _issue(
                "invalid_number",
                SEVERITY_ERROR,
                "The value is not a valid number.",
                field_name=field_name,
                raw_value=value,
            )
        )
        return None

    if parsed is None and required:
        issues.append(
            _issue(
                "missing_number",
                SEVERITY_ERROR,
                "A numeric value is required.",
                field_name=field_name,
                raw_value=value,
            )
        )

    return parsed


def _parse_required_date(
    value: Any,
    field_name: str,
    issues: list[RowCleaningIssue],
) -> date | None:
    try:
        parsed = parse_date_value(value)
    except ValueNormalizationError:
        issues.append(
            _issue(
                "invalid_date",
                SEVERITY_ERROR,
                "The value is not a valid date.",
                field_name=field_name,
                raw_value=value,
            )
        )
        return None

    if parsed is None:
        issues.append(
            _issue(
                "missing_date",
                SEVERITY_ERROR,
                "A date value is required.",
                field_name=field_name,
                raw_value=value,
            )
        )

    return parsed


def _check_period(
    value: date | None,
    period_start: date,
    period_end: date,
    field_name: str,
    issues: list[RowCleaningIssue],
) -> None:
    if value is None:
        return

    if value < period_start or value > period_end:
        issues.append(
            _issue(
                "date_outside_period",
                SEVERITY_ERROR,
                (
                    "The row date is outside the period "
                    "declared in the filename."
                ),
                field_name=field_name,
                raw_value=value,
                details={
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                },
            )
        )


def _status_from_issues(
    issues: list[RowCleaningIssue],
    *,
    force_excluded: bool = False,
) -> str:
    if force_excluded:
        return STATUS_EXCLUDED

    if any(
        issue.severity == SEVERITY_ERROR
        for issue in issues
    ):
        return STATUS_EXCLUDED

    return STATUS_ACCEPTED


def _clean_stock_or_load(
    raw: dict[str, Any],
    report_type: str,
) -> tuple[str, dict[str, Any], list[RowCleaningIssue]]:
    issues: list[RowCleaningIssue] = []
    van, van_normalized = _normalize_van(raw, issues)

    quantity_raw = raw.get(QTY_HEADER)
    quantity = _parse_number(
        quantity_raw,
        QTY_HEADER,
        issues,
        required=False,
    )

    article = normalize_text(raw.get("Article"))

    quantity_is_invalid = any(
        issue.code == "invalid_number"
        and issue.field == QTY_HEADER
        for issue in issues
    )

    if (
        van is not None
        and article is None
        and not quantity_is_invalid
        and (
            is_blank_value(quantity_raw)
            or quantity == Decimal("0")
        )
    ):
        issues.append(
            _issue(
                "stopped_indicator",
                SEVERITY_WARNING,
                (
                    "The row contains a truck identifier "
                    "without product activity."
                ),
                field_name="VAN",
                raw_value=raw.get("VAN"),
                details={
                    "authoritative": False,
                    "report_type": report_type,
                },
            )
        )

        return (
            STATUS_STOPPED,
            {
                "van": van,
                "van_normalized": van_normalized,
                "article": None,
                "article_normalized": None,
                "quantity": quantity or Decimal("0"),
            },
            issues,
        )

    chargement_datetime = None
    has_chargement_datetime = (
        report_type == "CHARGEMENT"
        and "Date&Heure" in raw
    )

    if has_chargement_datetime:
        datetime_raw = raw.get("Date&Heure")

        try:
            chargement_datetime = parse_datetime_value(
                datetime_raw
            )
        except ValueNormalizationError:
            issues.append(
                _issue(
                    "invalid_datetime",
                    SEVERITY_ERROR,
                    "The chargement datetime is invalid.",
                    field_name="Date&Heure",
                    raw_value=datetime_raw,
                )
            )

    if article is None:
        issues.append(
            _issue(
                "missing_article",
                SEVERITY_ERROR,
                "The Article value is required.",
                field_name="Article",
                raw_value=raw.get("Article"),
            )
        )

    if quantity is None:
        issues.append(
            _issue(
                "missing_quantity",
                SEVERITY_ERROR,
                "The quantity value is required.",
                field_name=QTY_HEADER,
                raw_value=raw.get(QTY_HEADER),
            )
        )
    elif (
        quantity < 0
        and report_type != "CHARGEMENT"
    ):
        issues.append(
            _issue(
                "negative_quantity",
                SEVERITY_ERROR,
                "Negative quantities are not allowed.",
                field_name=QTY_HEADER,
                raw_value=raw.get(QTY_HEADER),
            )
        )

    cleaned = {
        "van": van,
        "van_normalized": van_normalized,
        "article": article,
        "article_normalized": normalize_lookup_text(article),
        "quantity": quantity,
    }

    if has_chargement_datetime:
        cleaned["chargement_datetime"] = (
            chargement_datetime
        )

    return _status_from_issues(issues), cleaned, issues


def _clean_items(
    raw: dict[str, Any],
) -> tuple[str, dict[str, Any], list[RowCleaningIssue]]:
    issues: list[RowCleaningIssue] = []
    van, van_normalized = _normalize_van(raw, issues)

    article = normalize_text(raw.get("Article"))
    client = normalize_text(raw.get("Client"))

    quantity_raw = raw.get(QTY_SOLD_HEADER)
    quantity = _parse_number(
        quantity_raw,
        QTY_SOLD_HEADER,
        issues,
        required=False,
    )

    quantity_is_invalid = any(
        issue.code == "invalid_number"
        and issue.field == QTY_SOLD_HEADER
        for issue in issues
    )

    if (
        van is not None
        and article is None
        and client is None
        and not quantity_is_invalid
        and is_blank_value(quantity_raw)
    ):
        issues.append(
            _issue(
                "stopped_indicator",
                SEVERITY_WARNING,
                (
                    "The row contains a truck identifier "
                    "without item sales activity."
                ),
                field_name="VAN",
                raw_value=raw.get("VAN"),
                details={
                    "authoritative": False,
                },
            )
        )

        return (
            STATUS_STOPPED,
            {
                "van": van,
                "van_normalized": van_normalized,
                "article": None,
                "article_normalized": None,
                "quantity_sold": None,
                "client": None,
                "client_normalized": None,
            },
            issues,
        )

    if article is None:
        issues.append(
            _issue(
                "missing_article",
                SEVERITY_ERROR,
                "The Article value is required.",
                field_name="Article",
                raw_value=raw.get("Article"),
            )
        )

    if client is None:
        issues.append(
            _issue(
                "missing_client",
                SEVERITY_ERROR,
                "The Client value is required.",
                field_name="Client",
                raw_value=raw.get("Client"),
            )
        )

    force_excluded = False

    if quantity is None:
        issues.append(
            _issue(
                "missing_quantity",
                SEVERITY_ERROR,
                "The sold quantity is required.",
                field_name=QTY_SOLD_HEADER,
                raw_value=quantity_raw,
            )
        )
    elif quantity < 0:
        issues.append(
            _issue(
                "negative_quantity",
                SEVERITY_WARNING,
                (
                    "Negative item quantities are retained "
                    "but excluded from calculations."
                ),
                field_name=QTY_SOLD_HEADER,
                raw_value=quantity_raw,
            )
        )
        force_excluded = True
    elif quantity == 0:
        issues.append(
            _issue(
                "zero_quantity",
                SEVERITY_WARNING,
                "The sold quantity is zero.",
                field_name=QTY_SOLD_HEADER,
                raw_value=quantity_raw,
            )
        )

    cleaned = {
        "van": van,
        "van_normalized": van_normalized,
        "article": article,
        "article_normalized": normalize_lookup_text(article),
        "quantity_sold": quantity,
        "client": client,
        "client_normalized": normalize_lookup_text(client),
    }

    return (
        _status_from_issues(
            issues,
            force_excluded=force_excluded,
        ),
        cleaned,
        issues,
    )


def _clean_sales(
    raw: dict[str, Any],
    period_start: date,
    period_end: date,
) -> tuple[str, dict[str, Any], list[RowCleaningIssue]]:
    issues: list[RowCleaningIssue] = []
    van, van_normalized = _normalize_van(raw, issues)

    total = _parse_number(
        raw.get("Total"),
        "Total",
        issues,
        required=True,
    )

    client = normalize_text(raw.get("Nom du client"))
    date_raw = raw.get("Date&Heure")

    if (
        van is not None
        and total == Decimal("0")
        and client is None
        and is_blank_value(date_raw)
    ):
        issues.append(
            _issue(
                "truck_stopped_for_period",
                SEVERITY_WARNING,
                (
                    "A zero-total Sales row declares that "
                    "the truck was stopped for the period."
                ),
                field_name="VAN",
                raw_value=raw.get("VAN"),
                details={
                    "authoritative": True,
                },
            )
        )

        return (
            STATUS_STOPPED,
            {
                "van": van,
                "van_normalized": van_normalized,
                "sale_datetime": None,
                "client": None,
                "client_normalized": None,
                "total": Decimal("0"),
                "region": None,
                "region_normalized": None,
            },
            issues,
        )

    try:
        sale_datetime = parse_datetime_value(date_raw)
    except ValueNormalizationError:
        sale_datetime = None
        issues.append(
            _issue(
                "invalid_datetime",
                SEVERITY_ERROR,
                "The sale datetime is invalid.",
                field_name="Date&Heure",
                raw_value=date_raw,
            )
        )

    if sale_datetime is None:
        issues.append(
            _issue(
                "missing_datetime",
                SEVERITY_ERROR,
                "The sale datetime is required.",
                field_name="Date&Heure",
                raw_value=date_raw,
            )
        )
    else:
        _check_period(
            sale_datetime.date(),
            period_start,
            period_end,
            "Date&Heure",
            issues,
        )

    if client is None:
        issues.append(
            _issue(
                "missing_client",
                SEVERITY_ERROR,
                "The customer name is required.",
                field_name="Nom du client",
                raw_value=raw.get("Nom du client"),
            )
        )

    if total is not None:
        if total < 0:
            issues.append(
                _issue(
                    "negative_total",
                    SEVERITY_ERROR,
                    "Negative sale totals are not allowed.",
                    field_name="Total",
                    raw_value=raw.get("Total"),
                )
            )
        elif total == 0:
            issues.append(
                _issue(
                    "zero_total",
                    SEVERITY_WARNING,
                    "The sale total is zero.",
                    field_name="Total",
                    raw_value=raw.get("Total"),
                )
            )

    region = normalize_text(raw.get("Region"))

    cleaned = {
        "van": van,
        "van_normalized": van_normalized,
        "sale_datetime": sale_datetime,
        "client": client,
        "client_normalized": normalize_lookup_text(client),
        "total": total,
        "region": region,
        "region_normalized": normalize_lookup_text(region),
    }

    return _status_from_issues(issues), cleaned, issues


def _clean_pos(
    raw: dict[str, Any],
    period_start: date,
    period_end: date,
) -> tuple[str, dict[str, Any], list[RowCleaningIssue]]:
    issues: list[RowCleaningIssue] = []
    van, van_normalized = _normalize_van(raw, issues)

    client = normalize_text(raw.get("Nom du client"))
    date_raw = raw.get("Date")
    message_raw = raw.get("Message d'ignoration")
    cause_raw = raw.get("Cause d'ignoration")

    if (
        van is not None
        and client is None
        and is_blank_value(date_raw)
        and is_blank_value(message_raw)
        and is_blank_value(cause_raw)
    ):
        issues.append(
            _issue(
                "stopped_indicator",
                SEVERITY_WARNING,
                (
                    "The row contains a truck identifier "
                    "without visit activity."
                ),
                field_name="VAN",
                raw_value=raw.get("VAN"),
                details={
                    "authoritative": False,
                },
            )
        )

        return (
            STATUS_STOPPED,
            {
                "van": van,
                "van_normalized": van_normalized,
                "client": None,
                "client_normalized": None,
                "visit_date": None,
                "ignoration_message": None,
                "ignoration_cause": None,
            },
            issues,
        )

    if client is None:
        issues.append(
            _issue(
                "missing_client",
                SEVERITY_ERROR,
                "The customer name is required.",
                field_name="Nom du client",
                raw_value=raw.get("Nom du client"),
            )
        )

    visit_date = _parse_required_date(
        date_raw,
        "Date",
        issues,
    )

    _check_period(
        visit_date,
        period_start,
        period_end,
        "Date",
        issues,
    )

    if (
        isinstance(message_raw, (int, float, Decimal))
        and not isinstance(message_raw, bool)
    ):
        message = None
        issues.append(
            _issue(
                "numeric_ignoration_message",
                SEVERITY_WARNING,
                (
                    "A numeric value was found in the "
                    "ignoration message and is not used "
                    "as a reason."
                ),
                field_name="Message d'ignoration",
                raw_value=message_raw,
            )
        )
    else:
        message = normalize_text(message_raw)

    cause = normalize_text(cause_raw)

    cleaned = {
        "van": van,
        "van_normalized": van_normalized,
        "client": client,
        "client_normalized": normalize_lookup_text(client),
        "visit_date": visit_date,
        "ignoration_message": message,
        "ignoration_cause": cause,
    }

    return _status_from_issues(issues), cleaned, issues


def clean_report_rows_from_metadata(
    row_result: ReportRowReadResult,
    *,
    period_start: Any | None = None,
    period_end: Any | None = None,
) -> ReportCleaningResult:
    if row_result.report_type in {
        "SALES",
        "POS",
    } and (
        period_start is None
        or period_end is None
    ):
        raise ReportRowCleaningError(
            "missing_period_metadata",
            (
                "Period start and end are required "
                f"for {row_result.report_type} rows."
            ),
        )

    cleaned_rows: list[CleanedReportRow] = []

    for row in row_result.rows:
        raw = row.as_dict()

        if row_result.report_type in {
            "OPENING_STOCK",
            "CHARGEMENT",
        }:
            status, cleaned, issues = (
                _clean_stock_or_load(
                    raw,
                    row_result.report_type,
                )
            )
        elif row_result.report_type == "ITEMS":
            status, cleaned, issues = _clean_items(raw)
        elif row_result.report_type == "SALES":
            status, cleaned, issues = _clean_sales(
                raw,
                period_start,
                period_end,
            )
        elif row_result.report_type == "POS":
            status, cleaned, issues = _clean_pos(
                raw,
                period_start,
                period_end,
            )
        else:
            raise ReportRowCleaningError(
                "unsupported_report_type",
                (
                    "No row cleaner exists for report "
                    f"type {row_result.report_type}."
                ),
            )

        cleaned_rows.append(
            CleanedReportRow(
                row_number=row.row_number,
                status=status,
                raw_values=row.values,
                cleaned_values=tuple(cleaned.items()),
                issues=tuple(issues),
            )
        )

    return ReportCleaningResult(
        filename=row_result.filename,
        report_type=row_result.report_type,
        rows=tuple(cleaned_rows),
    )


def clean_report_rows(
    row_result: ReportRowReadResult,
    preflight_result: Any,
) -> ReportCleaningResult:
    if not preflight_result.is_valid:
        raise ReportRowCleaningError(
            "invalid_preflight",
            (
                "Rows cannot be cleaned because the "
                "preflight contains blocking errors."
            ),
        )

    parsed = preflight_result.parsed_filename

    if parsed is None:
        raise ReportRowCleaningError(
            "incomplete_preflight",
            "The parsed filename information is missing.",
        )

    if parsed.report_type != row_result.report_type:
        raise ReportRowCleaningError(
            "report_type_mismatch",
            (
                "The row result and preflight report "
                "types do not match."
            ),
        )

    return clean_report_rows_from_metadata(
        row_result,
        period_start=getattr(
            parsed,
            "period_start",
            None,
        ),
        period_end=getattr(
            parsed,
            "period_end",
            None,
        ),
    )
