from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Iterable

from django.db import models

from apps.fleet.models import TruckCrewAssignment

from .business_calendar import (
    delisky_working_dates,
)
from .pos_visit_aggregation import (
    DailyBrandTruckWorkerVisitTotal,
)
from .sales_aggregation import (
    DailyBrandTruckWorkerSalesTotal,
)


class MobilityTransitionType(StrEnum):
    WORKER_CHANGED_TRUCK = "WORKER_CHANGED_TRUCK"
    TRUCK_CHANGED_WORKER = "TRUCK_CHANGED_WORKER"


@dataclass(frozen=True, slots=True)
class MobilityWindowMetrics:
    brand_id: int
    worker_id: int
    truck_id: int
    period_start: date
    period_end: date
    working_day_count: int
    sales_measurement_day_count: int
    visit_measurement_day_count: int
    sales_total: Decimal | None
    sale_record_count: int | None
    positive_sale_record_count: int | None
    zero_total_record_count: int | None
    pos_record_count: int | None
    visited_record_count: int | None
    not_visited_record_count: int | None
    unique_client_day_count: int | None

    @property
    def has_sales_measurement(self) -> bool:
        return self.sale_record_count is not None

    @property
    def has_visit_measurement(self) -> bool:
        return self.pos_record_count is not None

    @property
    def visit_success_rate(self) -> Decimal | None:
        if not self.pos_record_count:
            return None

        return (
            Decimal(self.visited_record_count or 0)
            / Decimal(self.pos_record_count)
        )

    @property
    def non_visit_rate(self) -> Decimal | None:
        if not self.pos_record_count:
            return None

        return (
            Decimal(self.not_visited_record_count or 0)
            / Decimal(self.pos_record_count)
        )


@dataclass(frozen=True, slots=True)
class WorkerTruckMobilityComparison:
    transition_type: MobilityTransitionType
    brand_id: int
    change_date: date
    gap_working_day_count: int
    before: MobilityWindowMetrics
    after: MobilityWindowMetrics

    @property
    def is_contiguous_transition(self) -> bool:
        return self.gap_working_day_count == 0

    @property
    def has_comparable_sales(self) -> bool:
        return (
            self.before.has_sales_measurement
            and self.after.has_sales_measurement
        )

    @property
    def has_comparable_visits(self) -> bool:
        return (
            self.before.has_visit_measurement
            and self.after.has_visit_measurement
        )

    @property
    def sales_total_delta(self) -> Decimal | None:
        if not self.has_comparable_sales:
            return None

        return (
            self.after.sales_total
            - self.before.sales_total
        )

    @property
    def visit_success_rate_delta(
        self,
    ) -> Decimal | None:
        if not self.has_comparable_visits:
            return None

        before_rate = self.before.visit_success_rate
        after_rate = self.after.visit_success_rate

        if before_rate is None or after_rate is None:
            return None

        return after_rate - before_rate


@dataclass(frozen=True, slots=True)
class WorkerTruckMobilityResult:
    period_start: date
    period_end: date
    comparisons: tuple[
        WorkerTruckMobilityComparison,
        ...,
    ]

    @property
    def worker_moves(self) -> tuple[
        WorkerTruckMobilityComparison,
        ...,
    ]:
        return tuple(
            comparison
            for comparison in self.comparisons
            if (
                comparison.transition_type
                == MobilityTransitionType
                .WORKER_CHANGED_TRUCK
            )
        )

    @property
    def truck_seller_changes(self) -> tuple[
        WorkerTruckMobilityComparison,
        ...,
    ]:
        return tuple(
            comparison
            for comparison in self.comparisons
            if (
                comparison.transition_type
                == MobilityTransitionType
                .TRUCK_CHANGED_WORKER
            )
        )


@dataclass(frozen=True, slots=True)
class _TransitionCandidate:
    transition_type: MobilityTransitionType
    before_assignment: TruckCrewAssignment
    after_assignment: TruckCrewAssignment


def _overlaps_period(
    assignment: TruckCrewAssignment,
    *,
    period_start: date,
    period_end: date,
) -> bool:
    assignment_end = assignment.end_date or period_end

    return (
        assignment.start_date <= period_end
        and assignment_end >= period_start
    )


def _available_assignment_period(
    assignment: TruckCrewAssignment,
    *,
    period_start: date,
    period_end: date,
) -> tuple[date, date] | None:
    start = max(
        assignment.start_date,
        period_start,
    )
    end = min(
        assignment.end_date or period_end,
        period_end,
    )

    if end < start:
        return None

    return start, end


def _equal_comparison_windows(
    before_assignment: TruckCrewAssignment,
    after_assignment: TruckCrewAssignment,
    *,
    period_start: date,
    period_end: date,
) -> tuple[
    tuple[date, ...],
    tuple[date, ...],
] | None:
    before_period = _available_assignment_period(
        before_assignment,
        period_start=period_start,
        period_end=period_end,
    )
    after_period = _available_assignment_period(
        after_assignment,
        period_start=period_start,
        period_end=period_end,
    )

    if before_period is None or after_period is None:
        return None

    before_dates = delisky_working_dates(
        before_period[0],
        before_period[1],
    )
    after_dates = delisky_working_dates(
        after_period[0],
        after_period[1],
    )

    working_day_count = min(
        len(before_dates),
        len(after_dates),
    )

    if working_day_count <= 0:
        return None

    return (
        before_dates[-working_day_count:],
        after_dates[:working_day_count],
    )


def _validate_primary_assignment_overlaps(
    assignments: Iterable[TruckCrewAssignment],
) -> None:
    primary_assignments = tuple(
        assignment
        for assignment in assignments
        if (
            assignment.is_primary_seller
            and assignment.worker_id is not None
            and assignment.truck_id is not None
        )
    )

    groups: list[
        dict[int, list[TruckCrewAssignment]]
    ] = [
        {},
        {},
    ]

    worker_groups, truck_groups = groups

    for assignment in primary_assignments:
        worker_groups.setdefault(
            assignment.worker_id,
            [],
        ).append(assignment)
        truck_groups.setdefault(
            assignment.truck_id,
            [],
        ).append(assignment)

    for grouped_assignments in (
        worker_groups.values(),
        truck_groups.values(),
    ):
        for assignments_group in grouped_assignments:
            ordered = sorted(
                assignments_group,
                key=lambda item: (
                    item.start_date,
                    item.pk or 0,
                ),
            )

            for before, after in zip(
                ordered,
                ordered[1:],
            ):
                if (
                    before.end_date is None
                    or before.end_date
                    >= after.start_date
                ):
                    raise ValueError(
                        "Overlapping primary-seller "
                        "assignments are not supported."
                    )


def _build_transition_candidates(
    assignments: Iterable[TruckCrewAssignment],
) -> tuple[_TransitionCandidate, ...]:
    primary_assignments = tuple(
        assignment
        for assignment in assignments
        if (
            assignment.is_primary_seller
            and assignment.worker_id is not None
            and assignment.truck_id is not None
        )
    )

    worker_groups: dict[
        int,
        list[TruckCrewAssignment],
    ] = {}
    truck_groups: dict[
        int,
        list[TruckCrewAssignment],
    ] = {}

    for assignment in primary_assignments:
        worker_groups.setdefault(
            assignment.worker_id,
            [],
        ).append(assignment)

        truck_groups.setdefault(
            assignment.truck_id,
            [],
        ).append(assignment)

    candidates: list[_TransitionCandidate] = []

    for worker_assignments in worker_groups.values():
        ordered = sorted(
            worker_assignments,
            key=lambda item: (
                item.start_date,
                item.pk or 0,
            ),
        )

        for before, after in zip(
            ordered,
            ordered[1:],
        ):
            if before.truck_id == after.truck_id:
                continue

            candidates.append(
                _TransitionCandidate(
                    transition_type=(
                        MobilityTransitionType
                        .WORKER_CHANGED_TRUCK
                    ),
                    before_assignment=before,
                    after_assignment=after,
                )
            )

    for truck_assignments in truck_groups.values():
        ordered = sorted(
            truck_assignments,
            key=lambda item: (
                item.start_date,
                item.pk or 0,
            ),
        )

        for before, after in zip(
            ordered,
            ordered[1:],
        ):
            if before.worker_id == after.worker_id:
                continue

            candidates.append(
                _TransitionCandidate(
                    transition_type=(
                        MobilityTransitionType
                        .TRUCK_CHANGED_WORKER
                    ),
                    before_assignment=before,
                    after_assignment=after,
                )
            )

    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                item.after_assignment.start_date,
                item.transition_type.value,
                item.before_assignment.worker_id,
                item.before_assignment.truck_id,
                item.after_assignment.worker_id,
                item.after_assignment.truck_id,
            ),
        )
    )


def _build_window_metrics(
    *,
    brand_id: int,
    worker_id: int,
    truck_id: int,
    working_dates: tuple[date, ...],
    sales_rows: tuple[
        DailyBrandTruckWorkerSalesTotal,
        ...,
    ],
    visit_rows: tuple[
        DailyBrandTruckWorkerVisitTotal,
        ...,
    ],
) -> MobilityWindowMetrics:
    if not working_dates:
        raise ValueError(
            "working_dates cannot be empty."
        )

    working_date_set = set(working_dates)
    period_start = working_dates[0]
    period_end = working_dates[-1]

    matching_sales = tuple(
        row
        for row in sales_rows
        if (
            row.brand_id == brand_id
            and row.worker_id == worker_id
            and row.truck_id == truck_id
            and row.sale_date in working_date_set
        )
    )

    matching_visits = tuple(
        row
        for row in visit_rows
        if (
            row.brand_id == brand_id
            and row.worker_id == worker_id
            and row.truck_id == truck_id
            and row.visit_date in working_date_set
        )
    )

    if matching_sales:
        sales_total = sum(
            (
                row.metrics.total_sales
                for row in matching_sales
            ),
            Decimal("0"),
        )
        sale_record_count = sum(
            row.metrics.sale_record_count
            for row in matching_sales
        )
        positive_sale_record_count = sum(
            row.metrics.positive_sale_record_count
            for row in matching_sales
        )
        zero_total_record_count = sum(
            row.metrics.zero_total_record_count
            for row in matching_sales
        )
    else:
        sales_total = None
        sale_record_count = None
        positive_sale_record_count = None
        zero_total_record_count = None

    if matching_visits:
        pos_record_count = sum(
            row.metrics.total_record_count
            for row in matching_visits
        )
        visited_record_count = sum(
            row.metrics.visited_record_count
            for row in matching_visits
        )
        not_visited_record_count = sum(
            row.metrics.not_visited_record_count
            for row in matching_visits
        )
        unique_client_day_count = sum(
            row.metrics.unique_client_day_count
            for row in matching_visits
        )
    else:
        pos_record_count = None
        visited_record_count = None
        not_visited_record_count = None
        unique_client_day_count = None

    sales_measurement_days = {
        row.sale_date
        for row in matching_sales
    }
    visit_measurement_days = {
        row.visit_date
        for row in matching_visits
    }

    return MobilityWindowMetrics(
        brand_id=brand_id,
        worker_id=worker_id,
        truck_id=truck_id,
        period_start=period_start,
        period_end=period_end,
        working_day_count=len(
            working_dates
        ),
        sales_measurement_day_count=len(
            sales_measurement_days
        ),
        visit_measurement_day_count=len(
            visit_measurement_days
        ),
        sales_total=sales_total,
        sale_record_count=sale_record_count,
        positive_sale_record_count=(
            positive_sale_record_count
        ),
        zero_total_record_count=(
            zero_total_record_count
        ),
        pos_record_count=pos_record_count,
        visited_record_count=visited_record_count,
        not_visited_record_count=(
            not_visited_record_count
        ),
        unique_client_day_count=(
            unique_client_day_count
        ),
    )


def build_worker_truck_mobility(
    *,
    period_start: date,
    period_end: date,
    sales_daily: Iterable[
        DailyBrandTruckWorkerSalesTotal
    ] = (),
    visit_daily: Iterable[
        DailyBrandTruckWorkerVisitTotal
    ] = (),
    assignments: Iterable[
        TruckCrewAssignment
    ] | None = None,
) -> WorkerTruckMobilityResult:
    """
    Build deterministic before/after mobility comparisons.

    Transitions come from historical primary-seller assignments.
    Before/after windows use the same number of DELISKY working days.
    A comparison is emitted only when at least one metric family
    is measured on both sides for the same brand.
    """
    if period_end < period_start:
        raise ValueError(
            "period_end cannot be before period_start."
        )

    if assignments is None:
        assignments = (
            TruckCrewAssignment.objects
            .filter(
                is_primary_seller=True,
                start_date__lte=period_end,
            )
            .filter(
                models.Q(end_date__isnull=True)
                | models.Q(
                    end_date__gte=period_start
                )
            )
            .order_by(
                "start_date",
                "id",
            )
        )

    assignments = tuple(
        assignment
        for assignment in assignments
        if _overlaps_period(
            assignment,
            period_start=period_start,
            period_end=period_end,
        )
    )
    _validate_primary_assignment_overlaps(
        assignments
    )

    sales_rows = tuple(sales_daily)
    visit_rows = tuple(visit_daily)

    comparisons: list[
        WorkerTruckMobilityComparison
    ] = []

    for candidate in _build_transition_candidates(
        assignments
    ):
        windows = _equal_comparison_windows(
            candidate.before_assignment,
            candidate.after_assignment,
            period_start=period_start,
            period_end=period_end,
        )

        if windows is None:
            continue

        before_window, after_window = windows

        before_assignment_end = (
            candidate.before_assignment.end_date
        )

        if before_assignment_end is None:
            continue

        gap_start = (
            before_assignment_end
            + timedelta(days=1)
        )
        gap_end = (
            candidate.after_assignment.start_date
            - timedelta(days=1)
        )

        if gap_end < gap_start:
            gap_working_day_count = 0
        else:
            gap_working_day_count = len(
                delisky_working_dates(
                    gap_start,
                    gap_end,
                )
            )

        before_worker_id = (
            candidate.before_assignment.worker_id
        )
        before_truck_id = (
            candidate.before_assignment.truck_id
        )
        after_worker_id = (
            candidate.after_assignment.worker_id
        )
        after_truck_id = (
            candidate.after_assignment.truck_id
        )

        brand_ids = sorted(
            {
                row.brand_id
                for row in sales_rows
            }
            | {
                row.brand_id
                for row in visit_rows
            }
        )

        for brand_id in brand_ids:
            before = _build_window_metrics(
                brand_id=brand_id,
                worker_id=before_worker_id,
                truck_id=before_truck_id,
                working_dates=before_window,
                sales_rows=sales_rows,
                visit_rows=visit_rows,
            )
            after = _build_window_metrics(
                brand_id=brand_id,
                worker_id=after_worker_id,
                truck_id=after_truck_id,
                working_dates=after_window,
                sales_rows=sales_rows,
                visit_rows=visit_rows,
            )

            has_comparable_sales = (
                before.has_sales_measurement
                and after.has_sales_measurement
            )
            has_comparable_visits = (
                before.has_visit_measurement
                and after.has_visit_measurement
            )

            if not (
                has_comparable_sales
                or has_comparable_visits
            ):
                continue

            comparisons.append(
                WorkerTruckMobilityComparison(
                    transition_type=(
                        candidate.transition_type
                    ),
                    brand_id=brand_id,
                    change_date=(
                        candidate.after_assignment
                        .start_date
                    ),
                    gap_working_day_count=gap_working_day_count,
                    before=before,
                    after=after,
                )
            )

    return WorkerTruckMobilityResult(
        period_start=period_start,
        period_end=period_end,
        comparisons=tuple(comparisons),
    )
