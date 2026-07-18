from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder

from apps.imports.models import (
    ImportBatch,
    ImportRow,
    ImportRowStatus,
)

from .report_row_cleaner import ReportCleaningResult


class ImportRowStagingError(Exception):
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
class PreparedImportRow:
    excel_row_number: int
    status: str
    raw_data: dict[str, Any]
    cleaned_data: dict[str, Any]
    issues: list[dict[str, Any]]
    row_sha256: str


@dataclass(frozen=True, slots=True)
class PreparedImportRows:
    report_type: str
    rows: tuple[PreparedImportRow, ...]
    content_sha256: str

    @property
    def total_rows(self) -> int:
        return len(self.rows)

    @property
    def accepted_rows(self) -> int:
        return sum(
            row.status == ImportRowStatus.ACCEPTED
            for row in self.rows
        )

    @property
    def excluded_rows(self) -> int:
        return sum(
            row.status == ImportRowStatus.EXCLUDED
            for row in self.rows
        )

    @property
    def stopped_rows(self) -> int:
        return sum(
            row.status == ImportRowStatus.STOPPED
            for row in self.rows
        )


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            cls=DjangoJSONEncoder,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ImportRowStagingError(
            "non_serializable_row",
            (
                "A reviewed row contains a value that "
                "cannot be stored safely as JSON."
            ),
        ) from exc


def _payload_sha256(value: Any) -> str:
    canonical = _canonical_json(value)

    return sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def _serialize_issue(issue: Any) -> dict[str, Any]:
    return {
        "code": issue.code,
        "severity": issue.severity,
        "message": issue.message,
        "field": issue.field,
        "raw_value": issue.raw_value,
        "details": dict(issue.details),
    }


def prepare_import_rows(
    cleaning_result: ReportCleaningResult,
) -> PreparedImportRows:
    valid_statuses = {
        ImportRowStatus.ACCEPTED,
        ImportRowStatus.EXCLUDED,
        ImportRowStatus.STOPPED,
    }

    prepared_rows: list[PreparedImportRow] = []
    normalized_row_hashes: list[str] = []
    seen_excel_rows: set[int] = set()

    for row in cleaning_result.rows:
        if row.row_number in seen_excel_rows:
            raise ImportRowStagingError(
                "duplicate_excel_row",
                (
                    "The cleaning result contains the same "
                    "Excel row number more than once."
                ),
                details={
                    "excel_row_number": row.row_number,
                },
            )

        seen_excel_rows.add(row.row_number)

        if row.row_number < 2:
            raise ImportRowStagingError(
                "invalid_excel_row_number",
                (
                    "Excel data row numbers must be "
                    "2 or greater."
                ),
                details={
                    "excel_row_number": row.row_number,
                },
            )

        if row.status not in valid_statuses:
            raise ImportRowStagingError(
                "invalid_row_status",
                "The cleaned row has an unsupported status.",
                details={
                    "status": row.status,
                    "excel_row_number": row.row_number,
                },
            )

        raw_data = row.raw_dict()
        cleaned_data = row.cleaned_dict()
        issues = [
            _serialize_issue(issue)
            for issue in row.issues
        ]

        row_payload = {
            "report_type": cleaning_result.report_type,
            "excel_row_number": row.row_number,
            "status": row.status,
            "raw_data": raw_data,
            "cleaned_data": cleaned_data,
            "issues": issues,
        }

        row_hash = _payload_sha256(row_payload)

        normalized_payload = {
            "status": row.status,
            "cleaned_data": cleaned_data,
        }

        normalized_row_hashes.append(
            _payload_sha256(normalized_payload)
        )

        prepared_rows.append(
            PreparedImportRow(
                excel_row_number=row.row_number,
                status=row.status,
                raw_data=raw_data,
                cleaned_data=cleaned_data,
                issues=issues,
                row_sha256=row_hash,
            )
        )

    content_payload = {
        "report_type": cleaning_result.report_type,
        "normalized_row_hashes": sorted(
            normalized_row_hashes
        ),
    }

    return PreparedImportRows(
        report_type=cleaning_result.report_type,
        rows=tuple(prepared_rows),
        content_sha256=_payload_sha256(
            content_payload
        ),
    )


def replace_import_batch_rows(
    batch: ImportBatch,
    prepared: PreparedImportRows,
    *,
    batch_size: int = 1000,
) -> int:
    if batch.pk is None:
        raise ImportRowStagingError(
            "unsaved_batch",
            (
                "The ImportBatch must be saved before "
                "its rows can be persisted."
            ),
        )

    if batch.report_type != prepared.report_type:
        raise ImportRowStagingError(
            "report_type_mismatch",
            (
                "The prepared rows do not match the "
                "ImportBatch report type."
            ),
            details={
                "batch_report_type": batch.report_type,
                "rows_report_type": prepared.report_type,
            },
        )

    expected_counts = {
        "total": batch.total_rows,
        "accepted": batch.accepted_rows,
        "excluded": batch.excluded_rows,
        "stopped": batch.stopped_rows,
    }

    actual_counts = {
        "total": prepared.total_rows,
        "accepted": prepared.accepted_rows,
        "excluded": prepared.excluded_rows,
        "stopped": prepared.stopped_rows,
    }

    if expected_counts != actual_counts:
        raise ImportRowStagingError(
            "row_count_mismatch",
            (
                "The prepared row counts do not match "
                "the ImportBatch review totals."
            ),
            details={
                "expected": expected_counts,
                "actual": actual_counts,
            },
        )

    if batch.content_sha256 != prepared.content_sha256:
        raise ImportRowStagingError(
            "content_hash_mismatch",
            (
                "The ImportBatch content hash does not "
                "match its prepared rows."
            ),
        )

    ImportRow.objects.filter(
        batch=batch
    ).delete()

    database_rows = [
        ImportRow(
            batch=batch,
            excel_row_number=row.excel_row_number,
            status=row.status,
            raw_data=row.raw_data,
            cleaned_data=row.cleaned_data,
            issues=row.issues,
            row_sha256=row.row_sha256,
        )
        for row in prepared.rows
    ]

    ImportRow.objects.bulk_create(
        database_rows,
        batch_size=batch_size,
    )

    return len(database_rows)
