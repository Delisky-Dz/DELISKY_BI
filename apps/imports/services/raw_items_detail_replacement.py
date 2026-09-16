from dataclasses import dataclass
from typing import Any, Iterable

from apps.imports.models import (
    ImportBatch,
    ImportBatchStatus,
)

from .batch_review import MUTABLE_BATCH_STATUSES
from .raw_items_file import (
    RawItemsFileError,
    source_truck_code_from_filename,
)
from .source_truck_mapper import (
    SourceTruckMappingError,
    map_source_truck_code,
)
from .source_truck_mapping_store import (
    build_source_truck_mapping,
)


class RawItemsDetailReplacementError(Exception):
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
class ItemsDetailReplacementPlan:
    covered_trucks: tuple[str, ...]
    replacement_batches: tuple[ImportBatch, ...]

    @property
    def replacement_batch_ids(self) -> tuple[int, ...]:
        return tuple(
            batch.pk
            for batch in self.replacement_batches
            if batch.pk is not None
        )


def _canonical_truck_codes(
    values: Iterable[object],
) -> tuple[str, ...]:
    normalized = {
        " ".join(str(value or "").split()).upper()
        for value in values
    }
    normalized.discard("")
    return tuple(sorted(normalized))


def detail_batch_covered_trucks(
    batch: ImportBatch,
) -> tuple[str, ...]:
    summary = batch.review_summary or {}
    detail = summary.get("items_detail")

    if not isinstance(detail, dict):
        return ()

    if not detail.get("transaction_level"):
        return ()

    trucks = detail.get("covered_trucks")
    if not isinstance(trucks, (list, tuple)):
        return ()

    return _canonical_truck_codes(trucks)


def _legacy_batch_covered_trucks(
    batch: ImportBatch,
    *,
    truck_mapping: dict[object, object],
) -> tuple[str, ...]:
    source_upload = batch.source_upload
    if source_upload is None:
        raise RawItemsDetailReplacementError(
            "missing_source_upload",
            "An overlapping Items batch has no source upload identity.",
            details={"batch_id": batch.pk},
        )

    try:
        source_truck_code = source_truck_code_from_filename(
            source_upload.original_filename
        )
        internal_code = map_source_truck_code(
            source_truck_code,
            mapping=truck_mapping,
        )
    except (RawItemsFileError, SourceTruckMappingError) as exc:
        raise RawItemsDetailReplacementError(
            "unverifiable_items_scope",
            (
                "An overlapping Items batch cannot be assigned "
                "to a truck safely."
            ),
            details={
                "batch_id": batch.pk,
                "filename": source_upload.original_filename,
                "cause_code": getattr(exc, "code", None),
            },
        ) from exc

    return _canonical_truck_codes((internal_code,))


def batch_covered_trucks(
    batch: ImportBatch,
    *,
    truck_mapping: dict[object, object],
) -> tuple[str, ...]:
    detail_trucks = detail_batch_covered_trucks(batch)
    if detail_trucks:
        return detail_trucks

    return _legacy_batch_covered_trucks(
        batch,
        truck_mapping=truck_mapping,
    )


def plan_items_detail_replacements(
    *,
    source_system_code: str,
    brand_code: str,
    covered_trucks: Iterable[object],
    period_start: Any,
    period_end: Any,
    current_source_upload_id: int | None = None,
) -> ItemsDetailReplacementPlan:
    normalized_covered_trucks = _canonical_truck_codes(
        covered_trucks
    )

    if not normalized_covered_trucks:
        raise RawItemsDetailReplacementError(
            "empty_items_detail_scope",
            "The Items detail batch does not cover any trucks.",
        )

    new_scope = set(normalized_covered_trucks)
    truck_mapping = build_source_truck_mapping(
        source_system_code
    )

    candidates = (
        ImportBatch.objects
        .select_related(
            "source_upload",
            "source_upload__source_system",
            "brand",
        )
        .filter(
            source_upload__isnull=False,
            source_upload__source_system__code__iexact=(
                source_system_code
            ),
            brand__code__iexact=brand_code,
            report_type="ITEMS",
            period_start__lte=period_end,
            period_end__gte=period_start,
        )
        .exclude(status=ImportBatchStatus.SUPERSEDED)
        .order_by("id")
    )

    replacements: list[ImportBatch] = []

    for candidate in candidates:
        if (
            current_source_upload_id is not None
            and candidate.source_upload_id
            == current_source_upload_id
        ):
            continue

        if candidate.status not in (
            set(MUTABLE_BATCH_STATUSES)
            | {ImportBatchStatus.APPROVED}
        ):
            continue

        candidate_scope = set(
            batch_covered_trucks(
                candidate,
                truck_mapping=truck_mapping,
            )
        )

        intersection = new_scope & candidate_scope
        if not intersection:
            continue

        if candidate.status in MUTABLE_BATCH_STATUSES:
            raise RawItemsDetailReplacementError(
                "items_detail_mutable_overlap_conflict",
                (
                    "A mutable Items batch overlaps the new "
                    "transaction-level truck scope."
                ),
                details={
                    "batch_id": candidate.pk,
                    "overlapping_trucks": sorted(intersection),
                },
            )

        candidate_fully_contained = (
            candidate.period_start is not None
            and candidate.period_end is not None
            and period_start <= candidate.period_start
            and period_end >= candidate.period_end
        )

        if not candidate_fully_contained:
            raise RawItemsDetailReplacementError(
                "items_detail_period_overlap_conflict",
                (
                    "An approved Items batch overlaps the new "
                    "transaction-level period without being "
                    "fully contained by it."
                ),
                details={
                    "batch_id": candidate.pk,
                    "approved_period_start": str(
                        candidate.period_start
                    ),
                    "approved_period_end": str(
                        candidate.period_end
                    ),
                    "requested_period_start": str(period_start),
                    "requested_period_end": str(period_end),
                    "overlapping_trucks": sorted(intersection),
                },
            )

        if not candidate_scope.issubset(new_scope):
            raise RawItemsDetailReplacementError(
                "items_detail_partial_truck_scope_conflict",
                (
                    "An approved transaction-level Items batch "
                    "contains trucks that are not present in the "
                    "new detail scope, so it cannot be superseded "
                    "as a whole."
                ),
                details={
                    "batch_id": candidate.pk,
                    "candidate_trucks": sorted(candidate_scope),
                    "requested_trucks": sorted(new_scope),
                },
            )

        replacements.append(candidate)

    return ItemsDetailReplacementPlan(
        covered_trucks=normalized_covered_trucks,
        replacement_batches=tuple(replacements),
    )
