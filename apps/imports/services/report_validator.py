from dataclasses import dataclass, field
from typing import Any

from .excel_reader import (
    WorkbookInspection,
    WorksheetInspection,
)
from .report_schemas import (
    get_report_schema,
    normalize_header,
)


SEVERITY_ERROR = "ERROR"
SEVERITY_WARNING = "WARNING"


@dataclass(frozen=True, slots=True)
class SchemaIssue:
    code: str
    severity: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReportSchemaValidation:
    report_type: str
    is_valid: bool
    errors: tuple[SchemaIssue, ...]
    warnings: tuple[SchemaIssue, ...]
    column_positions: tuple[tuple[str, int], ...]
    worksheet_name: str = ""


def _build_column_positions(
    worksheet: WorksheetInspection,
    required_headers: tuple[str, ...],
) -> tuple[tuple[str, int], ...]:
    actual_positions: dict[str, int] = {}

    for position, header in enumerate(
        worksheet.headers,
        start=1,
    ):
        normalized = normalize_header(header)

        if normalized and normalized not in actual_positions:
            actual_positions[normalized] = position

    positions = []

    for required_header in required_headers:
        normalized = normalize_header(required_header)

        if normalized in actual_positions:
            positions.append(
                (
                    required_header,
                    actual_positions[normalized],
                )
            )

    return tuple(positions)


def validate_workbook_schema(
    inspection: WorkbookInspection,
    report_type: str,
) -> ReportSchemaValidation:
    schema = get_report_schema(report_type)

    errors: list[SchemaIssue] = []
    warnings: list[SchemaIssue] = []

    if (
        inspection.worksheet_count
        != schema.expected_worksheet_count
    ):
        errors.append(
            SchemaIssue(
                code="unexpected_worksheet_count",
                severity=SEVERITY_ERROR,
                message=(
                    "??? ?? ????? ??? Excel ??? ???? ?????? "
                    "????? ???."
                ),
                details={
                    "expected": schema.expected_worksheet_count,
                    "actual": inspection.worksheet_count,
                },
            )
        )

        return ReportSchemaValidation(
            report_type=report_type,
            is_valid=False,
            errors=tuple(errors),
            warnings=tuple(warnings),
            column_positions=(),
        )

    worksheet = inspection.worksheets[0]

    if worksheet.empty_header_positions:
        errors.append(
            SchemaIssue(
                code="empty_headers",
                severity=SEVERITY_ERROR,
                message=(
                    "????? ?? ???????? ??? ????? ??? ?????."
                ),
                details={
                    "positions": list(
                        worksheet.empty_header_positions
                    ),
                },
            )
        )

    if worksheet.duplicate_headers:
        errors.append(
            SchemaIssue(
                code="duplicate_headers",
                severity=SEVERITY_ERROR,
                message=(
                    "????? ????? ??? ?????? ????? ?????."
                ),
                details={
                    "headers": list(
                        worksheet.duplicate_headers
                    ),
                },
            )
        )

    actual_headers = {
        normalize_header(header): header
        for header in worksheet.headers
        if normalize_header(header)
    }

    required_headers = {
        normalize_header(header): header
        for header in schema.required_headers
    }

    missing_headers = tuple(
        required_headers[normalized]
        for normalized in required_headers
        if normalized not in actual_headers
    )

    extra_headers = tuple(
        actual_headers[normalized]
        for normalized in actual_headers
        if normalized not in required_headers
    )

    if missing_headers:
        errors.append(
            SchemaIssue(
                code="missing_required_headers",
                severity=SEVERITY_ERROR,
                message=(
                    "????? ????? ??? ????? ???????."
                ),
                details={
                    "headers": list(missing_headers),
                },
            )
        )

    if extra_headers:
        warnings.append(
            SchemaIssue(
                code="extra_headers",
                severity=SEVERITY_WARNING,
                message=(
                    "????? ????? ??? ????? ?????? "
                    "?? ???? ????? ????????."
                ),
                details={
                    "headers": list(extra_headers),
                },
            )
        )

    column_positions = _build_column_positions(
        worksheet,
        schema.required_headers,
    )

    return ReportSchemaValidation(
        report_type=report_type,
        is_valid=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
        column_positions=column_positions,
        worksheet_name=worksheet.name,
    )
