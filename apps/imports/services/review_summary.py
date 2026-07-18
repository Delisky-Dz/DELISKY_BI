from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .report_row_cleaner import (
    ReportCleaningResult,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
)
from .report_row_reader import ReportRowReadResult


REVIEW_STATUS_REVIEWED = "REVIEWED"
REVIEW_STATUS_BLOCKED = "BLOCKED"


class ImportReviewSummaryError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
    ):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class ReviewIssueGroup:
    code: str
    severity: str
    count: int
    row_numbers: tuple[int, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "count": self.count,
            "row_numbers": list(self.row_numbers),
        }


@dataclass(frozen=True, slots=True)
class ImportReviewSummary:
    filename: str
    report_type: str
    brand_code: str
    period_start: str
    period_end: str
    total_rows: int
    accepted_rows: int
    excluded_rows: int
    stopped_rows: int
    retained_rows: int
    warning_count: int
    error_count: int
    blocking_row_count: int
    can_approve: bool
    recommended_status: str
    issue_groups: tuple[ReviewIssueGroup, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "report_type": self.report_type,
            "brand_code": self.brand_code,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "total_rows": self.total_rows,
            "accepted_rows": self.accepted_rows,
            "excluded_rows": self.excluded_rows,
            "stopped_rows": self.stopped_rows,
            "retained_rows": self.retained_rows,
            "warning_count": self.warning_count,
            "error_count": self.error_count,
            "blocking_row_count": self.blocking_row_count,
            "can_approve": self.can_approve,
            "recommended_status": self.recommended_status,
            "issue_groups": [
                group.as_dict()
                for group in self.issue_groups
            ],
        }


def build_import_review_summary(
    preflight_result: Any,
    row_result: ReportRowReadResult,
    cleaning_result: ReportCleaningResult,
) -> ImportReviewSummary:
    if not preflight_result.is_valid:
        raise ImportReviewSummaryError(
            "invalid_preflight",
            (
                "A review summary cannot be built from "
                "an invalid preflight result."
            ),
        )

    parsed = preflight_result.parsed_filename

    if parsed is None:
        raise ImportReviewSummaryError(
            "incomplete_preflight",
            "Parsed filename information is missing.",
        )

    if (
        parsed.report_type != row_result.report_type
        or parsed.report_type != cleaning_result.report_type
    ):
        raise ImportReviewSummaryError(
            "report_type_mismatch",
            (
                "Preflight, row reader, and cleaner report "
                "types do not match."
            ),
        )

    if row_result.row_count != cleaning_result.total_rows:
        raise ImportReviewSummaryError(
            "row_count_mismatch",
            (
                "The row reader and cleaner totals "
                "do not match."
            ),
        )

    accounted_rows = (
        cleaning_result.accepted_rows
        + cleaning_result.excluded_rows
        + cleaning_result.stopped_rows
    )

    if accounted_rows != cleaning_result.total_rows:
        raise ImportReviewSummaryError(
            "unaccounted_rows",
            (
                "Accepted, excluded, and stopped rows "
                "do not equal the total row count."
            ),
        )

    grouped_rows: dict[
        tuple[str, str],
        list[int],
    ] = defaultdict(list)

    blocking_rows: set[int] = set()

    for row in cleaning_result.rows:
        for issue in row.issues:
            grouped_rows[
                (issue.code, issue.severity)
            ].append(row.row_number)

            if issue.severity == SEVERITY_ERROR:
                blocking_rows.add(row.row_number)

    severity_order = {
        SEVERITY_ERROR: 0,
        SEVERITY_WARNING: 1,
    }

    issue_groups = tuple(
        ReviewIssueGroup(
            code=code,
            severity=severity,
            count=len(row_numbers),
            row_numbers=tuple(row_numbers),
        )
        for (
            code,
            severity,
        ), row_numbers in sorted(
            grouped_rows.items(),
            key=lambda item: (
                severity_order.get(
                    item[0][1],
                    99,
                ),
                item[0][0],
            ),
        )
    )

    can_approve = cleaning_result.error_count == 0

    return ImportReviewSummary(
        filename=cleaning_result.filename,
        report_type=cleaning_result.report_type,
        brand_code=parsed.brand_code,
        period_start=parsed.period_start.isoformat(),
        period_end=parsed.period_end.isoformat(),
        total_rows=cleaning_result.total_rows,
        accepted_rows=cleaning_result.accepted_rows,
        excluded_rows=cleaning_result.excluded_rows,
        stopped_rows=cleaning_result.stopped_rows,
        retained_rows=(
            cleaning_result.accepted_rows
            + cleaning_result.stopped_rows
        ),
        warning_count=cleaning_result.warning_count,
        error_count=cleaning_result.error_count,
        blocking_row_count=len(blocking_rows),
        can_approve=can_approve,
        recommended_status=(
            REVIEW_STATUS_REVIEWED
            if can_approve
            else REVIEW_STATUS_BLOCKED
        ),
        issue_groups=issue_groups,
    )
