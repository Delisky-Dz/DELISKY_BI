from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.imports.models import ImportBatch

from .batch_review import ImportBatchReviewError
from .raw_items_detail_brand_partition import (
    RawItemsDetailBrandPartitionError,
)
from .raw_items_detail_cleaning import (
    RawItemsDetailCleaningError,
)
from .raw_items_detail_file import (
    RawItemsDetailFileError,
)
from .raw_items_detail_import_review import (
    RawItemsDetailImportReviewError,
    create_raw_items_detail_import_review,
)
from .raw_items_detail_replacement import (
    RawItemsDetailReplacementError,
)
from .raw_items_detail_review import (
    RawItemsDetailReviewError,
)
from .source_upload_store import (
    ImportSourceUploadStoreError,
)


@dataclass(frozen=True, slots=True)
class RawItemsDetailImportRequest:
    source: Any
    source_system_code: str
    period_start: Any
    period_end: Any
    original_filename: str | None = None


@dataclass(frozen=True, slots=True)
class RawItemsDetailFileReviewResult:
    filename: str
    succeeded: bool
    batches: tuple[ImportBatch, ...] = ()
    error_code: str | None = None
    error_message: str | None = None
    error_details: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class RawItemsDetailMultiReviewResult:
    files: tuple[
        RawItemsDetailFileReviewResult,
        ...,
    ]

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


_KNOWN_REVIEW_ERRORS = (
    ImportBatchReviewError,
    ImportSourceUploadStoreError,
    RawItemsDetailBrandPartitionError,
    RawItemsDetailCleaningError,
    RawItemsDetailFileError,
    RawItemsDetailImportReviewError,
    RawItemsDetailReplacementError,
    RawItemsDetailReviewError,
)


def _request_filename(
    request: RawItemsDetailImportRequest,
) -> str:
    return str(
        request.original_filename
        or getattr(request.source, "name", None)
        or ""
    ).strip()


def _known_error_payload(
    exc: Exception,
) -> tuple[str, str, dict[str, Any]]:
    return (
        str(
            getattr(
                exc,
                "code",
                "items_detail_review_failed",
            )
        ),
        str(
            getattr(
                exc,
                "message",
                None,
            )
            or str(exc)
            or "Items detail review failed."
        ),
        dict(
            getattr(
                exc,
                "details",
                {},
            )
            or {}
        ),
    )


def create_raw_items_detail_multi_import_reviews(
    requests: Iterable[
        RawItemsDetailImportRequest
    ],
    *,
    uploaded_by: Any,
    reviewed_by: Any | None = None,
) -> RawItemsDetailMultiReviewResult:
    results: list[
        RawItemsDetailFileReviewResult
    ] = []

    for request in requests:
        filename = _request_filename(request)

        try:
            review = (
                create_raw_items_detail_import_review(
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

        except _KNOWN_REVIEW_ERRORS as exc:
            code, message, details = (
                _known_error_payload(exc)
            )
            results.append(
                RawItemsDetailFileReviewResult(
                    filename=filename,
                    succeeded=False,
                    error_code=code,
                    error_message=message,
                    error_details=details,
                )
            )
            continue

        except ValidationError as exc:
            results.append(
                RawItemsDetailFileReviewResult(
                    filename=filename,
                    succeeded=False,
                    error_code=(
                        "items_detail_validation_error"
                    ),
                    error_message=" ".join(
                        str(message)
                        for message in exc.messages
                    ),
                    error_details={},
                )
            )
            continue

        except IntegrityError:
            results.append(
                RawItemsDetailFileReviewResult(
                    filename=filename,
                    succeeded=False,
                    error_code=(
                        "items_detail_persistence_conflict"
                    ),
                    error_message=(
                        "The Items detail review conflicts "
                        "with data already stored."
                    ),
                    error_details={},
                )
            )
            continue

        results.append(
            RawItemsDetailFileReviewResult(
                filename=filename,
                succeeded=True,
                batches=review.batches,
            )
        )

    return RawItemsDetailMultiReviewResult(
        files=tuple(results),
    )
