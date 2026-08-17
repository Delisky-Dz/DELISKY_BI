from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from apps.imports.models import ImportBatch

from .raw_chargement_review import (
    RawChargementImportReviewError,
    create_raw_chargement_import_review,
)
from .source_truck_mapping_store import (
    SourceTruckMappingStoreError,
    build_source_truck_mapping,
)


@dataclass(frozen=True, slots=True)
class RawChargementImportRequest:
    source: Any
    brand_code: str
    period_start: Any
    period_end: Any
    truck_mapping: Mapping[object, object] | None = None
    source_system_code: str | None = None
    original_filename: str | None = None


@dataclass(frozen=True, slots=True)
class RawChargementFileReviewResult:
    succeeded: bool
    original_filename: str | None
    batch: ImportBatch | None
    error_code: str | None
    error_message: str | None
    error_details: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RawChargementMultiReviewResult:
    files: tuple[RawChargementFileReviewResult, ...]

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


def create_raw_chargement_multi_import_reviews(
    requests: Iterable[RawChargementImportRequest],
    *,
    uploaded_by: Any,
    reviewed_by: Any | None = None,
) -> RawChargementMultiReviewResult:
    results: list[RawChargementFileReviewResult] = []

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
            if request.truck_mapping is not None:
                truck_mapping = request.truck_mapping
            elif request.source_system_code:
                truck_mapping = build_source_truck_mapping(
                    request.source_system_code
                )
            else:
                raise SourceTruckMappingStoreError(
                    "truck_mapping_missing",
                    (
                        "A truck mapping or source "
                        "system code is required."
                    ),
                    details={},
                )

            review_result = (
                create_raw_chargement_import_review(
                    request.source,
                    uploaded_by=uploaded_by,
                    reviewed_by=reviewed_by,
                    brand_code=request.brand_code,
                    period_start=request.period_start,
                    period_end=request.period_end,
                    truck_mapping=truck_mapping,
                    original_filename=(
                        original_filename
                    ),
                )
            )
        except (
            RawChargementImportReviewError,
            SourceTruckMappingStoreError,
        ) as exc:
            results.append(
                RawChargementFileReviewResult(
                    succeeded=False,
                    original_filename=original_filename,
                    batch=None,
                    error_code=exc.code,
                    error_message=exc.message,
                    error_details=dict(exc.details),
                )
            )
            continue

        results.append(
            RawChargementFileReviewResult(
                succeeded=True,
                original_filename=original_filename,
                batch=review_result.batch,
                error_code=None,
                error_message=None,
                error_details={},
            )
        )

    return RawChargementMultiReviewResult(
        files=tuple(results),
    )
