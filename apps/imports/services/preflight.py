from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any

from .excel_reader import (
    DEFAULT_MAX_FILE_SIZE_BYTES,
    ExcelInspectionError,
    WorkbookInspection,
    inspect_excel_file,
)
from .filename_parser import (
    ImportFilenameError,
    ParsedImportFilename,
    parse_import_filename,
)
from .report_validator import (
    ReportSchemaValidation,
    validate_workbook_schema,
)


@dataclass(frozen=True, slots=True)
class PreflightIssue:
    stage: str
    code: str
    severity: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ImportPreflightResult:
    filename: str
    parsed_filename: ParsedImportFilename | None
    inspection: WorkbookInspection | None
    schema_validation: ReportSchemaValidation | None
    errors: tuple[PreflightIssue, ...]
    warnings: tuple[PreflightIssue, ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors


def _resolve_filename(
    source: Any,
    original_filename: str | None,
) -> str:
    if original_filename:
        return Path(original_filename).name

    if isinstance(source, (str, PathLike)):
        return Path(source).name

    source_name = getattr(source, "name", "")

    if source_name:
        return Path(str(source_name)).name

    return ""


def _filename_error_issue(
    exc: ImportFilenameError,
) -> PreflightIssue:
    return PreflightIssue(
        stage="filename",
        code=exc.code,
        severity="ERROR",
        message=exc.message,
        details=dict(exc.details),
    )


def _inspection_error_issue(
    exc: ExcelInspectionError,
) -> PreflightIssue:
    return PreflightIssue(
        stage="workbook",
        code=exc.code,
        severity="ERROR",
        message=exc.message,
        details=dict(exc.details),
    )


def run_import_preflight(
    source: Any,
    *,
    original_filename: str | None = None,
    max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
) -> ImportPreflightResult:
    filename = _resolve_filename(
        source,
        original_filename,
    )

    errors: list[PreflightIssue] = []
    warnings: list[PreflightIssue] = []

    parsed_filename = None
    inspection = None
    schema_validation = None

    if not filename:
        errors.append(
            PreflightIssue(
                stage="filename",
                code="missing_filename",
                severity="ERROR",
                message="The uploaded file has no usable filename.",
            )
        )

        return ImportPreflightResult(
            filename="",
            parsed_filename=None,
            inspection=None,
            schema_validation=None,
            errors=tuple(errors),
            warnings=(),
        )

    try:
        parsed_filename = parse_import_filename(filename)
    except ImportFilenameError as exc:
        errors.append(
            _filename_error_issue(exc)
        )

    try:
        inspection = inspect_excel_file(
            source,
            original_filename=filename,
            max_file_size_bytes=max_file_size_bytes,
        )
    except ExcelInspectionError as exc:
        errors.append(
            _inspection_error_issue(exc)
        )

    if (
        parsed_filename is not None
        and inspection is not None
    ):
        schema_validation = validate_workbook_schema(
            inspection,
            parsed_filename.report_type,
        )

        for issue in schema_validation.errors:
            errors.append(
                PreflightIssue(
                    stage="schema",
                    code=issue.code,
                    severity=issue.severity,
                    message=issue.message,
                    details=dict(issue.details),
                )
            )

        for issue in schema_validation.warnings:
            warnings.append(
                PreflightIssue(
                    stage="schema",
                    code=issue.code,
                    severity=issue.severity,
                    message=issue.message,
                    details=dict(issue.details),
                )
            )

    return ImportPreflightResult(
        filename=filename,
        parsed_filename=parsed_filename,
        inspection=inspection,
        schema_validation=schema_validation,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
