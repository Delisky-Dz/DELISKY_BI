from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from apps.imports.models import ImportBatch

from .raw_sales_derived_review import (
    RawSalesDerivedReviewError,
    create_raw_sales_derived_import_review,
)
from .raw_sales_review import (
    RawSalesImportReviewError,
)


@dataclass(frozen=True, slots=True)
class RawSalesImportRequest:
    source: Any
    source_system_code: str
    period_start: Any
    period_end: Any
    original_filename: str | None = None


@dataclass(frozen=True, slots=True)
class RawSalesFileReviewResult:
    filename: str
    succeeded: bool
    batch: ImportBatch | None = None
    error_code: str | None = None
    error_message: str | None = None
    error_details: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class RawSalesMultiReviewResult:
    files: tuple[RawSalesFileReviewResult, ...]

    @property
    def succeeded_count(self) -> int:
        return sum(
            1
            for item in self.files
            if item.succeeded
        )

    @property
    def failed_count(self) -> int:
        return sum(
            1
            for item in self.files
            if not item.succeeded
        )


def _request_filename(
    request: RawSalesImportRequest,
) -> str:
    return str(
        request.original_filename
        or getattr(request.source, "name", None)
        or ""
    ).strip()


def create_raw_sales_multi_import_reviews(
    requests: Iterable[RawSalesImportRequest],
    *,
    uploaded_by: Any,
    reviewed_by: Any | None = None,
) -> RawSalesMultiReviewResult:
    results: list[RawSalesFileReviewResult] = []

    for request in requests:
        filename = _request_filename(request)

        try:
            review = (
                create_raw_sales_derived_import_review(
                    request.source,
                    source_system_code=(
                        request.source_system_code
                    ),
                    uploaded_by=uploaded_by,
                    reviewed_by=reviewed_by,
                    period_start=request.period_start,
                    period_end=request.period_end,
                    original_filename=(
                        request.original_filename
                    ),
                )
            )
        except (
            RawSalesImportReviewError,
            RawSalesDerivedReviewError,
        ) as exc:
            results.append(
                RawSalesFileReviewResult(
                    filename=filename,
                    succeeded=False,
                    error_code=exc.code,
                    error_message=exc.message,
                    error_details=dict(
                        getattr(exc, "details", {})
                    ),
                )
            )
            continue

        results.append(
            RawSalesFileReviewResult(
                filename=filename,
                succeeded=True,
                batch=review.batch,
            )
        )

    return RawSalesMultiReviewResult(
        files=tuple(results),
    )
