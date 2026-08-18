from dataclasses import dataclass
from typing import Any, Iterable

from apps.imports.models import ImportBatch

from .batch_review import ImportBatchReviewError
from .raw_chargement_brand_partition import (
    RawChargementBrandPartitionError,
)
from .raw_chargement_derived_review import (
    create_raw_chargement_derived_import_reviews,
)
from .raw_chargement_file import (
    RawChargementFileError,
)
from .raw_chargement_review import (
    RawChargementImportReviewError,
)
from .review_summary import (
    ImportReviewSummaryError,
)
from .row_staging import (
    ImportRowStagingError,
)
from .source_truck_mapping_store import (
    SourceTruckMappingStoreError,
)
from .source_upload_store import (
    ImportSourceUploadStoreError,
)


@dataclass(frozen=True, slots=True)
class RawChargementDerivedImportRequest:
    source: Any
    source_system_code: str
    period_start: Any
    period_end: Any
    original_filename: str | None = None


@dataclass(frozen=True, slots=True)
class RawChargementDerivedFileReviewResult:
    succeeded: bool
    original_filename: str | None
    batches: tuple[ImportBatch, ...]
    error_code: str | None
    error_message: str | None
    error_details: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RawChargementDerivedMultiReviewResult:
    files: tuple[RawChargementDerivedFileReviewResult, ...]

    @property
    def succeeded_count(self) -> int:
        return sum(
            1
            for result in self.files
            if result.succeeded
        )

    @property
    def failed_count(self) -> int:
        return len(self.files) - self.succeeded_count


DOMAIN_ERRORS = (
    ImportBatchReviewError,
    RawChargementBrandPartitionError,
    RawChargementFileError,
    RawChargementImportReviewError,
    ImportReviewSummaryError,
    ImportRowStagingError,
    SourceTruckMappingStoreError,
    ImportSourceUploadStoreError,
)


def create_raw_chargement_derived_multi_import_reviews(
    requests: Iterable[RawChargementDerivedImportRequest],
    *,
    uploaded_by: Any,
    reviewed_by: Any | None = None,
) -> RawChargementDerivedMultiReviewResult:
    results: list[
        RawChargementDerivedFileReviewResult
    ] = []

    for request in requests:
        original_filename = (
            request.original_filename
            or getattr(
                request.source,
                "name",
                None,
            )
        )

        try:
            review_result = (
                create_raw_chargement_derived_import_reviews(
                    request.source,
                    source_system_code=(
                        request.source_system_code
                    ),
                    uploaded_by=uploaded_by,
                    reviewed_by=reviewed_by,
                    period_start=request.period_start,
                    period_end=request.period_end,
                    original_filename=original_filename,
                )
            )
        except DOMAIN_ERRORS as exc:
            results.append(
                RawChargementDerivedFileReviewResult(
                    succeeded=False,
                    original_filename=original_filename,
                    batches=(),
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
            RawChargementDerivedFileReviewResult(
                succeeded=True,
                original_filename=original_filename,
                batches=review_result.batches,
                error_code=None,
                error_message=None,
                error_details={},
            )
        )

    return RawChargementDerivedMultiReviewResult(
        files=tuple(results),
    )
