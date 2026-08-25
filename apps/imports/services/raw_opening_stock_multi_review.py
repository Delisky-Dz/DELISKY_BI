from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from apps.imports.models import ImportBatch

from .raw_opening_stock_derived_review import (
    create_raw_opening_stock_derived_import_reviews,
)
from .raw_opening_stock_file import (
    RawOpeningStockFileError,
)
from .raw_opening_stock_review import (
    RawOpeningStockImportReviewError,
)


@dataclass(frozen=True, slots=True)
class RawOpeningStockImportRequest:
    source: Any
    source_system_code: str
    stock_date: Any
    original_filename: str | None = None


@dataclass(frozen=True, slots=True)
class RawOpeningStockFileReviewResult:
    filename: str
    succeeded: bool
    batches: tuple[ImportBatch, ...] = ()
    error_code: str | None = None
    error_message: str | None = None
    error_details: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class RawOpeningStockMultiReviewResult:
    files: tuple[RawOpeningStockFileReviewResult, ...]

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
    request: RawOpeningStockImportRequest,
) -> str:
    return str(
        request.original_filename
        or getattr(request.source, "name", None)
        or ""
    ).strip()


def create_raw_opening_stock_multi_import_reviews(
    requests: Iterable[RawOpeningStockImportRequest],
    *,
    uploaded_by: Any,
    reviewed_by: Any | None = None,
) -> RawOpeningStockMultiReviewResult:
    results: list[
        RawOpeningStockFileReviewResult
    ] = []

    for request in requests:
        filename = _request_filename(
            request
        )

        try:
            review = (
                create_raw_opening_stock_derived_import_reviews(
                    request.source,
                    source_system_code=(
                        request.source_system_code
                    ),
                    uploaded_by=uploaded_by,
                    reviewed_by=reviewed_by,
                    stock_date=request.stock_date,
                    original_filename=(
                        request.original_filename
                    ),
                )
            )
        except (
            RawOpeningStockImportReviewError,
            RawOpeningStockFileError,
        ) as exc:
            results.append(
                RawOpeningStockFileReviewResult(
                    filename=filename,
                    succeeded=False,
                    error_code=exc.code,
                    error_message=exc.message,
                    error_details=dict(
                        getattr(
                            exc,
                            "details",
                            {},
                        )
                    ),
                )
            )
            continue

        results.append(
            RawOpeningStockFileReviewResult(
                filename=filename,
                succeeded=True,
                batches=review.batches,
            )
        )

    return RawOpeningStockMultiReviewResult(
        files=tuple(results),
    )