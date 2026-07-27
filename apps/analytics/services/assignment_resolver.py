from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Iterable

from apps.fleet.models import (
    Truck,
    TruckCrewAssignment,
)
from apps.workforce.models import Worker


class AssignmentResolutionStatus(StrEnum):
    MATCHED = "MATCHED"
    MISSING_TRUCK = "MISSING_TRUCK"
    INVALID_PERIOD = "INVALID_PERIOD"
    NO_ASSIGNMENT = "NO_ASSIGNMENT"
    PARTIAL_COVERAGE = "PARTIAL_COVERAGE"
    MULTIPLE_ASSIGNMENTS = "MULTIPLE_ASSIGNMENTS"
    AMBIGUOUS_ASSIGNMENT = "AMBIGUOUS_ASSIGNMENT"


@dataclass(frozen=True, slots=True)
class AssignmentResolution:
    status: AssignmentResolutionStatus
    worker: Worker | None = None
    assignment: TruckCrewAssignment | None = None
    matching_assignment_ids: tuple[int, ...] = ()

    @property
    def is_matched(self) -> bool:
        return (
            self.status == AssignmentResolutionStatus.MATCHED
            and self.worker is not None
            and self.assignment is not None
        )


AssignmentIndex = dict[
    int,
    tuple[TruckCrewAssignment, ...],
]


def build_assignment_index(
    assignments: Iterable[TruckCrewAssignment] | None = None,
) -> AssignmentIndex:
    """
    Build an in-memory primary-seller assignment index grouped by truck.

    Historical assignments are included even when the worker or
    truck is currently inactive.
    """
    if assignments is None:
        assignments = (
            TruckCrewAssignment.objects
            .filter(is_primary_seller=True)
            .select_related("worker", "truck")
            .order_by(
                "truck_id",
                "start_date",
                "id",
            )
        )

    buckets: dict[
        int,
        list[TruckCrewAssignment],
    ] = {}

    for assignment in assignments:
        if assignment.truck_id is None:
            continue

        buckets.setdefault(
            assignment.truck_id,
            [],
        ).append(assignment)

    return {
        truck_id: tuple(items)
        for truck_id, items in buckets.items()
    }


def _assignment_ids(
    assignments: Iterable[TruckCrewAssignment],
) -> tuple[int, ...]:
    return tuple(
        sorted(
            assignment.pk
            for assignment in assignments
            if assignment.pk is not None
        )
    )


def resolve_worker_for_date(
    truck: Truck | None,
    event_date: date,
    *,
    assignment_index: AssignmentIndex | None = None,
) -> AssignmentResolution:
    """
    Resolve the primary seller assigned to a truck on an exact date.

    Intended for reports containing an exact date, such as
    SALES and POS.
    """
    if truck is None or truck.pk is None:
        return AssignmentResolution(
            status=AssignmentResolutionStatus.MISSING_TRUCK,
        )

    if assignment_index is None:
        assignment_index = build_assignment_index()

    matches = tuple(
        assignment
        for assignment in assignment_index.get(
            truck.pk,
            (),
        )
        if (
            assignment.start_date <= event_date
            and (
                assignment.end_date is None
                or assignment.end_date >= event_date
            )
        )
    )

    matching_ids = _assignment_ids(matches)

    if not matches:
        return AssignmentResolution(
            status=AssignmentResolutionStatus.NO_ASSIGNMENT,
        )

    if len(matches) > 1:
        return AssignmentResolution(
            status=(
                AssignmentResolutionStatus.AMBIGUOUS_ASSIGNMENT
            ),
            matching_assignment_ids=matching_ids,
        )

    assignment = matches[0]

    return AssignmentResolution(
        status=AssignmentResolutionStatus.MATCHED,
        worker=assignment.worker,
        assignment=assignment,
        matching_assignment_ids=matching_ids,
    )


def resolve_worker_for_period(
    truck: Truck | None,
    period_start: date,
    period_end: date,
    *,
    assignment_index: AssignmentIndex | None = None,
) -> AssignmentResolution:
    """
    Resolve a primary seller only when one assignment covers the entire period.

    Intended for period-level reports without an exact row date,
    especially ITEMS, CHARGEMENT and OPENING_STOCK.
    """
    if truck is None or truck.pk is None:
        return AssignmentResolution(
            status=AssignmentResolutionStatus.MISSING_TRUCK,
        )

    if period_end < period_start:
        return AssignmentResolution(
            status=AssignmentResolutionStatus.INVALID_PERIOD,
        )

    if assignment_index is None:
        assignment_index = build_assignment_index()

    overlapping = tuple(
        assignment
        for assignment in assignment_index.get(
            truck.pk,
            (),
        )
        if (
            assignment.start_date <= period_end
            and (
                assignment.end_date is None
                or assignment.end_date >= period_start
            )
        )
    )

    matching_ids = _assignment_ids(overlapping)

    if not overlapping:
        return AssignmentResolution(
            status=AssignmentResolutionStatus.NO_ASSIGNMENT,
        )

    if len(overlapping) > 1:
        return AssignmentResolution(
            status=(
                AssignmentResolutionStatus.MULTIPLE_ASSIGNMENTS
            ),
            matching_assignment_ids=matching_ids,
        )

    assignment = overlapping[0]

    covers_entire_period = (
        assignment.start_date <= period_start
        and (
            assignment.end_date is None
            or assignment.end_date >= period_end
        )
    )

    if not covers_entire_period:
        return AssignmentResolution(
            status=AssignmentResolutionStatus.PARTIAL_COVERAGE,
            matching_assignment_ids=matching_ids,
        )

    return AssignmentResolution(
        status=AssignmentResolutionStatus.MATCHED,
        worker=assignment.worker,
        assignment=assignment,
        matching_assignment_ids=matching_ids,
    )
