from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from apps.imports.models import ImportBatch

from .raw_items_derived_review import (
    RawItemsDerivedReviewError,
    create_raw_items_derived_import_review,
)
from .raw_items_review import (
    RawItemsImportReviewError,
)


@dataclass(frozen=True, slots=True)
class RawItemsImportRequest:
    source: Any
    source_system_code: str
    period_start: Any
    period_end: Any
    original_filename: str | None = None


@dataclass(frozen=True, slots=True)
class RawItemsFileReviewResult:
    filename: str
    succeeded: bool
    batch: ImportBatch | None = None
    error_code: str | None = None
    error_message: str | None = None
    error_details: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class RawItemsMultiReviewResult:
    files: tuple[RawItemsFileReviewResult, ...]

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
    request: RawItemsImportRequest,
) -> str:
    return str(
        request.original_filename
        or getattr(request.source, "name", None)
        or ""
    ).strip()


def create_raw_items_multi_import_reviews(
    requests: Iterable[RawItemsImportRequest],
    *,
    uploaded_by: Any,
    reviewed_by: Any | None = None,
) -> RawItemsMultiReviewResult:
    results: list[RawItemsFileReviewResult] = []

    for request in requests:
        filename = _request_filename(request)

        try:
            review = (
                create_raw_items_derived_import_review(
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
            RawItemsImportReviewError,
            RawItemsDerivedReviewError,
        ) as exc:
            results.append(
                RawItemsFileReviewResult(
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
            RawItemsFileReviewResult(
                filename=filename,
                succeeded=True,
                batch=review.batch,
            )
        )

    return RawItemsMultiReviewResult(
        files=tuple(results),
    )
