from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Iterable

from apps.imports.models import (
    ImportReportType,
    ImportRow,
)

from .approved_data_source import (
    get_approved_calculation_rows,
)
from .assignment_resolver import (
    AssignmentIndex,
    build_assignment_index,
    resolve_worker_for_period,
)
from .report_rows import parse_pos_row
from .truck_resolver import (
    TruckCodeIndex,
    build_truck_code_index,
    resolve_truck_by_van,
)


class PosVisitOutcome(StrEnum):
    VISITED = "VISITED"
    NOT_VISITED = "NOT_VISITED"


class PosAttributionStage(StrEnum):
    TRUCK = "TRUCK"
    WORKER = "WORKER"


@dataclass(frozen=True, slots=True)
class VisitMetrics:
    total_record_count: int
    visited_record_count: int
    not_visited_record_count: int
    unique_client_day_count: int


@dataclass(frozen=True, slots=True)
class BrandVisitTotal:
    brand_id: int
    metrics: VisitMetrics


@dataclass(frozen=True, slots=True)
class TruckVisitTotal:
    truck_id: int
    metrics: VisitMetrics


@dataclass(frozen=True, slots=True)
class WorkerVisitTotal:
    worker_id: int
    metrics: VisitMetrics


@dataclass(frozen=True, slots=True)
class BrandTruckWorkerVisitTotal:
    brand_id: int
    truck_id: int
    worker_id: int
    metrics: VisitMetrics


@dataclass(frozen=True, slots=True)
class DailyBrandTruckWorkerVisitTotal:
    visit_date: date
    brand_id: int
    truck_id: int
    worker_id: int
    metrics: VisitMetrics


@dataclass(frozen=True, slots=True)
class BrandClientVisitTotal:
    brand_id: int
    client: str
    client_normalized: str
    metrics: VisitMetrics


@dataclass(frozen=True, slots=True)
class BrandTruckClientVisitTotal:
    brand_id: int
    truck_id: int
    client: str
    client_normalized: str
    metrics: VisitMetrics


@dataclass(frozen=True, slots=True)
class BrandWorkerClientVisitTotal:
    brand_id: int
    worker_id: int
    client: str
    client_normalized: str
    metrics: VisitMetrics


@dataclass(frozen=True, slots=True)
class PosAttributionIssue:
    stage: PosAttributionStage
    code: str
    import_row_id: int
    batch_id: int
    excel_row_number: int
    brand_id: int
    normalized_van: str
    visit_date: date
    outcome: PosVisitOutcome
    matching_entity_ids: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class PosVisitAggregationResult:
    requested_period_start: date | None
    requested_period_end: date | None
    source_row_count: int
    included_row_count: int
    outside_requested_period_count: int
    numeric_message_warning_count: int
    duplicate_same_day_warning_count: int
    duplicate_same_day_row_ids: tuple[int, ...]
    overall: VisitMetrics
    by_brand: tuple[BrandVisitTotal, ...]
    by_truck: tuple[TruckVisitTotal, ...]
    by_worker: tuple[WorkerVisitTotal, ...]
    by_brand_truck_worker: tuple[
        BrandTruckWorkerVisitTotal,
        ...,
    ]
    by_brand_client: tuple[
        BrandClientVisitTotal,
        ...,
    ]
    by_brand_truck_client: tuple[
        BrandTruckClientVisitTotal,
        ...,
    ]
    by_brand_worker_client: tuple[
        BrandWorkerClientVisitTotal,
        ...,
    ]
    attribution_issues: tuple[
        PosAttributionIssue,
        ...,
    ]

    by_date_brand_truck_worker: tuple[
        DailyBrandTruckWorkerVisitTotal,
        ...,
    ] = ()

    @property
    def has_attribution_issues(self) -> bool:
        return bool(self.attribution_issues)

    @property
    def has_duplicate_warnings(self) -> bool:
        return self.duplicate_same_day_warning_count > 0

    def top_visited_clients(
        self,
        limit: int = 10,
    ) -> tuple[BrandClientVisitTotal, ...]:
        if limit < 0:
            raise ValueError(
                "limit cannot be negative."
            )

        ranked = sorted(
            (
                item
                for item in self.by_brand_client
                if item.metrics.visited_record_count > 0
            ),
            key=lambda item: (
                -item.metrics.visited_record_count,
                -item.metrics.unique_client_day_count,
                item.client_normalized,
                item.brand_id,
            ),
        )

        return tuple(ranked[:limit])

    def top_not_visited_clients(
        self,
        limit: int = 10,
    ) -> tuple[BrandClientVisitTotal, ...]:
        if limit < 0:
            raise ValueError(
                "limit cannot be negative."
            )

        ranked = sorted(
            (
                item
                for item in self.by_brand_client
                if item.metrics.not_visited_record_count > 0
            ),
            key=lambda item: (
                -item.metrics.not_visited_record_count,
                -item.metrics.unique_client_day_count,
                item.client_normalized,
                item.brand_id,
            ),
        )

        return tuple(ranked[:limit])

    def never_visited_clients(
        self,
    ) -> tuple[BrandClientVisitTotal, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in self.by_brand_client
                    if (
                        item.metrics.not_visited_record_count > 0
                        and item.metrics.visited_record_count == 0
                    )
                ),
                key=lambda item: (
                    -item.metrics.not_visited_record_count,
                    item.client_normalized,
                    item.brand_id,
                ),
            )
        )


@dataclass(slots=True)
class _VisitAccumulator:
    total_record_count: int = 0
    visited_record_count: int = 0
    not_visited_record_count: int = 0
    client_days: set[
        tuple[str, date]
    ] = field(default_factory=set)

    def add(
        self,
        *,
        outcome: PosVisitOutcome,
        client_normalized: str,
        visit_date: date,
    ) -> None:
        self.total_record_count += 1

        if outcome == PosVisitOutcome.VISITED:
            self.visited_record_count += 1
        else:
            self.not_visited_record_count += 1

        self.client_days.add(
            (
                client_normalized,
                visit_date,
            )
        )

    def freeze(self) -> VisitMetrics:
        return VisitMetrics(
            total_record_count=self.total_record_count,
            visited_record_count=self.visited_record_count,
            not_visited_record_count=(
                self.not_visited_record_count
            ),
            unique_client_day_count=len(
                self.client_days
            ),
        )


@dataclass(slots=True)
class _NamedVisitAccumulator:
    display_name: str
    accumulator: _VisitAccumulator = field(
        default_factory=_VisitAccumulator
    )


def _get_accumulator(
    buckets: dict,
    key,
) -> _VisitAccumulator:
    accumulator = buckets.get(key)

    if accumulator is None:
        accumulator = _VisitAccumulator()
        buckets[key] = accumulator

    return accumulator


def _get_named_accumulator(
    buckets: dict,
    key,
    display_name: str,
) -> _NamedVisitAccumulator:
    named = buckets.get(key)

    if named is None:
        named = _NamedVisitAccumulator(
            display_name=display_name,
        )
        buckets[key] = named

    return named


def _clean_optional_text(
    value: str | None,
) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _is_numeric_message(
    value: str | None,
) -> bool:
    text = _clean_optional_text(value)

    if not text:
        return False

    candidate = (
        text.replace(" ", "")
        .replace("\u00a0", "")
        .replace(",", ".")
    )

    try:
        Decimal(candidate)
    except InvalidOperation:
        return False

    return True


def _classify_visit(
    *,
    ignoration_message: str | None,
    ignoration_cause: str | None,
) -> PosVisitOutcome:
    cause = _clean_optional_text(
        ignoration_cause
    )
    message = _clean_optional_text(
        ignoration_message
    )

    if cause:
        return PosVisitOutcome.NOT_VISITED

    if message and not _is_numeric_message(message):
        return PosVisitOutcome.NOT_VISITED

    return PosVisitOutcome.VISITED


def aggregate_pos_visits(
    *,
    period_start: date | None = None,
    period_end: date | None = None,
    brand_id: int | None = None,
    rows: Iterable[ImportRow] | None = None,
    truck_index: TruckCodeIndex | None = None,
    assignment_index: AssignmentIndex | None = None,
) -> PosVisitAggregationResult:
    """
    Aggregate approved and accepted POS rows.

    POS has exact visit-date precision. Numeric values inside
    ignoration_message are retained as warnings but do not prove
    that the client was not visited.
    """
    if (
        period_start is not None
        and period_end is not None
        and period_end < period_start
    ):
        raise ValueError(
            "period_end cannot be before period_start."
        )

    if rows is None:
        rows = get_approved_calculation_rows(
            report_type=ImportReportType.POS,
            brand_id=brand_id,
            period_start=period_start,
            period_end=period_end,
        )

    if truck_index is None:
        truck_index = build_truck_code_index()

    if assignment_index is None:
        assignment_index = build_assignment_index()

    overall = _VisitAccumulator()

    brand_buckets: dict[
        int,
        _VisitAccumulator,
    ] = {}
    truck_buckets: dict[
        int,
        _VisitAccumulator,
    ] = {}
    worker_buckets: dict[
        int,
        _VisitAccumulator,
    ] = {}

    brand_truck_worker_buckets: dict[
        tuple[int, int, int],
        _VisitAccumulator,
    ] = {}

    date_brand_truck_worker_buckets: dict[
        tuple[date, int, int, int],
        _VisitAccumulator,
    ] = {}

    brand_client_buckets: dict[
        tuple[int, str],
        _NamedVisitAccumulator,
    ] = {}

    brand_truck_client_buckets: dict[
        tuple[int, int, str],
        _NamedVisitAccumulator,
    ] = {}

    brand_worker_client_buckets: dict[
        tuple[int, int, str],
        _NamedVisitAccumulator,
    ] = {}

    attribution_issues: list[
        PosAttributionIssue
    ] = []

    source_row_count = 0
    outside_requested_period_count = 0
    numeric_message_warning_count = 0
    duplicate_same_day_row_ids: list[int] = []

    seen_client_days: set[
        tuple[int, str, date]
    ] = set()

    for import_row in rows:
        source_row_count += 1
        visit = parse_pos_row(import_row)

        if (
            period_start is not None
            and visit.visit_date < period_start
        ):
            outside_requested_period_count += 1
            continue

        if (
            period_end is not None
            and visit.visit_date > period_end
        ):
            outside_requested_period_count += 1
            continue

        outcome = _classify_visit(
            ignoration_message=(
                visit.ignoration_message
            ),
            ignoration_cause=(
                visit.ignoration_cause
            ),
        )

        if _is_numeric_message(
            visit.ignoration_message
        ):
            numeric_message_warning_count += 1

        duplicate_key = (
            visit.brand_id,
            visit.client_normalized,
            visit.visit_date,
        )

        if duplicate_key in seen_client_days:
            duplicate_same_day_row_ids.append(
                visit.import_row_id
            )
        else:
            seen_client_days.add(duplicate_key)

        add_arguments = {
            "outcome": outcome,
            "client_normalized": (
                visit.client_normalized
            ),
            "visit_date": visit.visit_date,
        }

        overall.add(**add_arguments)

        _get_accumulator(
            brand_buckets,
            visit.brand_id,
        ).add(**add_arguments)

        brand_client = _get_named_accumulator(
            brand_client_buckets,
            (
                visit.brand_id,
                visit.client_normalized,
            ),
            visit.client,
        )
        brand_client.accumulator.add(
            **add_arguments
        )

        truck_resolution = resolve_truck_by_van(
            visit.van_normalized,
            truck_index=truck_index,
        )

        if not truck_resolution.is_matched:
            attribution_issues.append(
                PosAttributionIssue(
                    stage=PosAttributionStage.TRUCK,
                    code=truck_resolution.status.value,
                    import_row_id=visit.import_row_id,
                    batch_id=visit.batch_id,
                    excel_row_number=(
                        visit.excel_row_number
                    ),
                    brand_id=visit.brand_id,
                    normalized_van=(
                        visit.van_normalized
                    ),
                    visit_date=visit.visit_date,
                    outcome=outcome,
                    matching_entity_ids=(
                        truck_resolution.matching_truck_ids
                    ),
                )
            )
            continue

        truck = truck_resolution.truck
        truck_id = truck.pk

        _get_accumulator(
            truck_buckets,
            truck_id,
        ).add(**add_arguments)

        truck_client = _get_named_accumulator(
            brand_truck_client_buckets,
            (
                visit.brand_id,
                truck_id,
                visit.client_normalized,
            ),
            visit.client,
        )
        truck_client.accumulator.add(
            **add_arguments
        )

        assignment_resolution = resolve_worker_for_period(
            truck,
            visit.visit_date,
            visit.visit_date,
            assignment_index=assignment_index,
        )

        if not assignment_resolution.is_matched:
            attribution_issues.append(
                PosAttributionIssue(
                    stage=PosAttributionStage.WORKER,
                    code=assignment_resolution.status.value,
                    import_row_id=visit.import_row_id,
                    batch_id=visit.batch_id,
                    excel_row_number=(
                        visit.excel_row_number
                    ),
                    brand_id=visit.brand_id,
                    normalized_van=(
                        visit.van_normalized
                    ),
                    visit_date=visit.visit_date,
                    outcome=outcome,
                    matching_entity_ids=(
                        assignment_resolution
                        .matching_assignment_ids
                    ),
                )
            )
            continue

        worker_id = assignment_resolution.worker.pk

        _get_accumulator(
            worker_buckets,
            worker_id,
        ).add(**add_arguments)

        _get_accumulator(
            brand_truck_worker_buckets,
            (
                visit.brand_id,
                truck_id,
                worker_id,
            ),
        ).add(**add_arguments)

        _get_accumulator(
            date_brand_truck_worker_buckets,
            (
                visit.visit_date,
                visit.brand_id,
                truck_id,
                worker_id,
            ),
        ).add(**add_arguments)

        worker_client = _get_named_accumulator(
            brand_worker_client_buckets,
            (
                visit.brand_id,
                worker_id,
                visit.client_normalized,
            ),
            visit.client,
        )
        worker_client.accumulator.add(
            **add_arguments
        )

    return PosVisitAggregationResult(
        requested_period_start=period_start,
        requested_period_end=period_end,
        source_row_count=source_row_count,
        included_row_count=overall.total_record_count,
        outside_requested_period_count=(
            outside_requested_period_count
        ),
        numeric_message_warning_count=(
            numeric_message_warning_count
        ),
        duplicate_same_day_warning_count=len(
            duplicate_same_day_row_ids
        ),
        duplicate_same_day_row_ids=tuple(
            duplicate_same_day_row_ids
        ),
        overall=overall.freeze(),
        by_brand=tuple(
            BrandVisitTotal(
                brand_id=key,
                metrics=value.freeze(),
            )
            for key, value in sorted(
                brand_buckets.items()
            )
        ),
        by_truck=tuple(
            TruckVisitTotal(
                truck_id=key,
                metrics=value.freeze(),
            )
            for key, value in sorted(
                truck_buckets.items()
            )
        ),
        by_worker=tuple(
            WorkerVisitTotal(
                worker_id=key,
                metrics=value.freeze(),
            )
            for key, value in sorted(
                worker_buckets.items()
            )
        ),
        by_brand_truck_worker=tuple(
            BrandTruckWorkerVisitTotal(
                brand_id=key[0],
                truck_id=key[1],
                worker_id=key[2],
                metrics=value.freeze(),
            )
            for key, value in sorted(
                brand_truck_worker_buckets.items()
            )
        ),
        by_brand_client=tuple(
            BrandClientVisitTotal(
                brand_id=key[0],
                client=value.display_name,
                client_normalized=key[1],
                metrics=value.accumulator.freeze(),
            )
            for key, value in sorted(
                brand_client_buckets.items()
            )
        ),
        by_brand_truck_client=tuple(
            BrandTruckClientVisitTotal(
                brand_id=key[0],
                truck_id=key[1],
                client=value.display_name,
                client_normalized=key[2],
                metrics=value.accumulator.freeze(),
            )
            for key, value in sorted(
                brand_truck_client_buckets.items()
            )
        ),
        by_brand_worker_client=tuple(
            BrandWorkerClientVisitTotal(
                brand_id=key[0],
                worker_id=key[1],
                client=value.display_name,
                client_normalized=key[2],
                metrics=value.accumulator.freeze(),
            )
            for key, value in sorted(
                brand_worker_client_buckets.items()
            )
        ),
        by_date_brand_truck_worker=tuple(
            DailyBrandTruckWorkerVisitTotal(
                visit_date=key[0],
                brand_id=key[1],
                truck_id=key[2],
                worker_id=key[3],
                metrics=value.freeze(),
            )
            for key, value in sorted(
                date_brand_truck_worker_buckets.items()
            )
        ),
        attribution_issues=tuple(
            attribution_issues
        ),
    )
