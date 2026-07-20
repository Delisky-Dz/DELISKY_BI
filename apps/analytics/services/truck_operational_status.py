from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Iterable

from apps.imports.models import (
    ImportReportType,
    ImportRow,
    ImportRowStatus,
)

from .approved_data_source import get_approved_activity_rows
from .report_rows import parse_sales_row
from .truck_resolver import (
    TruckCodeIndex,
    build_truck_code_index,
    resolve_truck_by_van,
)
from .typed_values import read_required_lookup_text


class TruckOperationalStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CONFIRMED_STOPPED = "CONFIRMED_STOPPED"
    POSSIBLE_STOPPED = "POSSIBLE_STOPPED"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"


class OperationalEvidenceType(StrEnum):
    SALES_ACTIVITY = "SALES_ACTIVITY"
    AUTHORITATIVE_STOPPED = "AUTHORITATIVE_STOPPED"
    POSSIBLE_STOPPED = "POSSIBLE_STOPPED"


@dataclass(frozen=True, slots=True)
class BrandTruckOperationalState:
    brand_id: int
    truck_id: int
    status: TruckOperationalStatus
    sales_activity_count: int
    sales_total: Decimal
    authoritative_stopped_count: int
    possible_stopped_count: int
    activity_row_ids: tuple[int, ...]
    authoritative_stopped_row_ids: tuple[int, ...]
    possible_stopped_row_ids: tuple[int, ...]

    @property
    def is_confirmed_stopped(self) -> bool:
        return (
            self.status
            == TruckOperationalStatus.CONFIRMED_STOPPED
        )

    @property
    def has_conflicting_evidence(self) -> bool:
        return (
            self.status
            == TruckOperationalStatus.CONFLICTING_EVIDENCE
        )


@dataclass(frozen=True, slots=True)
class OperationalAttributionIssue:
    code: str
    import_row_id: int
    batch_id: int
    excel_row_number: int
    brand_id: int
    normalized_van: str
    matching_truck_ids: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class TruckOperationalStatusResult:
    requested_period_start: date | None
    requested_period_end: date | None
    source_row_count: int
    included_evidence_row_count: int
    ignored_accepted_non_sales_count: int
    outside_requested_period_count: int
    partial_overlap_excluded_count: int
    states: tuple[BrandTruckOperationalState, ...]
    attribution_issues: tuple[
        OperationalAttributionIssue,
        ...,
    ]

    @property
    def confirmed_stopped(self) -> tuple[
        BrandTruckOperationalState,
        ...,
    ]:
        return tuple(
            state
            for state in self.states
            if state.status
            == TruckOperationalStatus.CONFIRMED_STOPPED
        )

    @property
    def active(self) -> tuple[
        BrandTruckOperationalState,
        ...,
    ]:
        return tuple(
            state
            for state in self.states
            if state.status
            == TruckOperationalStatus.ACTIVE
        )

    @property
    def possible_stopped(self) -> tuple[
        BrandTruckOperationalState,
        ...,
    ]:
        return tuple(
            state
            for state in self.states
            if state.status
            == TruckOperationalStatus.POSSIBLE_STOPPED
        )

    @property
    def conflicting(self) -> tuple[
        BrandTruckOperationalState,
        ...,
    ]:
        return tuple(
            state
            for state in self.states
            if state.status
            == TruckOperationalStatus.CONFLICTING_EVIDENCE
        )


@dataclass(slots=True)
class _OperationalAccumulator:
    sales_activity_count: int = 0
    sales_total: Decimal = field(
        default_factory=lambda: Decimal("0")
    )
    authoritative_stopped_count: int = 0
    possible_stopped_count: int = 0
    activity_row_ids: list[int] = field(
        default_factory=list
    )
    authoritative_stopped_row_ids: list[int] = field(
        default_factory=list
    )
    possible_stopped_row_ids: list[int] = field(
        default_factory=list
    )

    def add_sales_activity(
        self,
        *,
        row_id: int,
        total: Decimal,
    ) -> None:
        self.sales_activity_count += 1
        self.sales_total += total
        self.activity_row_ids.append(row_id)

    def add_stopped_evidence(
        self,
        *,
        row_id: int,
        authoritative: bool,
    ) -> None:
        if authoritative:
            self.authoritative_stopped_count += 1
            self.authoritative_stopped_row_ids.append(
                row_id
            )
        else:
            self.possible_stopped_count += 1
            self.possible_stopped_row_ids.append(
                row_id
            )

    def resolve_status(self) -> TruckOperationalStatus:
        has_activity = self.sales_activity_count > 0
        has_authoritative_stop = (
            self.authoritative_stopped_count > 0
        )
        has_possible_stop = self.possible_stopped_count > 0

        if has_activity and has_authoritative_stop:
            return (
                TruckOperationalStatus.CONFLICTING_EVIDENCE
            )

        if has_authoritative_stop:
            return TruckOperationalStatus.CONFIRMED_STOPPED

        if has_activity:
            return TruckOperationalStatus.ACTIVE

        if has_possible_stop:
            return TruckOperationalStatus.POSSIBLE_STOPPED

        raise ValueError(
            "Operational state has no usable evidence."
        )


def _is_authoritative_stopped_row(
    row: ImportRow,
) -> bool:
    if row.batch.report_type != ImportReportType.SALES:
        return False

    for issue in row.issues:
        if not isinstance(issue, dict):
            continue

        details = issue.get("details")

        if not isinstance(details, dict):
            details = {}

        if (
            issue.get("code")
            == "truck_stopped_for_period"
            and details.get("authoritative") is True
        ):
            return True

    return False


def _period_relation(
    *,
    batch_start: date,
    batch_end: date,
    requested_start: date | None,
    requested_end: date | None,
) -> str:
    if (
        requested_start is not None
        and batch_end < requested_start
    ):
        return "OUTSIDE"

    if (
        requested_end is not None
        and batch_start > requested_end
    ):
        return "OUTSIDE"

    if (
        requested_start is not None
        and batch_start < requested_start
    ):
        return "PARTIAL"
    
    if (
        requested_end is not None
        and batch_end > requested_end
    ):
        return "PARTIAL"

    return "INCLUDED"


def determine_truck_operational_status(
    *,
    period_start: date | None = None,
    period_end: date | None = None,
    brand_id: int | None = None,
    rows: Iterable[ImportRow] | None = None,
    truck_index: TruckCodeIndex | None = None,
) -> TruckOperationalStatusResult:
    """
    Determine truck operational states from approved activity rows.

    Accepted SALES rows prove activity on their exact sale date.
    SALES STOPPED rows are authoritative for their complete batch
    period. STOPPED rows from other reports remain possible
    indicators only.
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
        rows = get_approved_activity_rows(
            brand_id=brand_id,
            period_start=period_start,
            period_end=period_end,
        )

    if truck_index is None:
        truck_index = build_truck_code_index()

    buckets: dict[
        tuple[int, int],
        _OperationalAccumulator,
    ] = {}

    attribution_issues: list[
        OperationalAttributionIssue
    ] = []

    source_row_count = 0
    included_evidence_row_count = 0
    ignored_accepted_non_sales_count = 0
    outside_requested_period_count = 0
    partial_overlap_excluded_count = 0

    for row in rows:
        source_row_count += 1

        if row.status == ImportRowStatus.ACCEPTED:
            if row.batch.report_type != ImportReportType.SALES:
                ignored_accepted_non_sales_count += 1
                continue

            sale = parse_sales_row(row)
            sale_date = sale.sale_datetime.date()

            if (
                period_start is not None
                and sale_date < period_start
            ):
                outside_requested_period_count += 1
                continue

            if (
                period_end is not None
                and sale_date > period_end
            ):
                outside_requested_period_count += 1
                continue

            normalized_van = sale.van_normalized
            total = sale.total
            evidence_type = (
                OperationalEvidenceType.SALES_ACTIVITY
            )

        elif row.status == ImportRowStatus.STOPPED:
            relation = _period_relation(
                batch_start=row.batch.period_start,
                batch_end=row.batch.period_end,
                requested_start=period_start,
                requested_end=period_end,
            )

            if relation == "OUTSIDE":
                outside_requested_period_count += 1
                continue

            if relation == "PARTIAL":
                partial_overlap_excluded_count += 1
                continue

            normalized_van = read_required_lookup_text(
                row.cleaned_data,
                "van_normalized",
            )
            total = Decimal("0")

            if _is_authoritative_stopped_row(row):
                evidence_type = (
                    OperationalEvidenceType
                    .AUTHORITATIVE_STOPPED
                )
            else:
                evidence_type = (
                    OperationalEvidenceType.POSSIBLE_STOPPED
                )

        else:
            continue

        truck_resolution = resolve_truck_by_van(
            normalized_van,
            truck_index=truck_index,
        )

        if not truck_resolution.is_matched:
            attribution_issues.append(
                OperationalAttributionIssue(
                    code=truck_resolution.status.value,
                    import_row_id=row.pk,
                    batch_id=row.batch_id,
                    excel_row_number=row.excel_row_number,
                    brand_id=row.batch.brand_id,
                    normalized_van=normalized_van,
                    matching_truck_ids=(
                        truck_resolution.matching_truck_ids
                    ),
                )
            )
            continue

        included_evidence_row_count += 1

        truck_id = truck_resolution.truck.pk
        key = (
            row.batch.brand_id,
            truck_id,
        )

        accumulator = buckets.get(key)

        if accumulator is None:
            accumulator = _OperationalAccumulator()
            buckets[key] = accumulator

        if (
            evidence_type
            == OperationalEvidenceType.SALES_ACTIVITY
        ):
            accumulator.add_sales_activity(
                row_id=row.pk,
                total=total,
            )
        else:
            accumulator.add_stopped_evidence(
                row_id=row.pk,
                authoritative=(
                    evidence_type
                    == OperationalEvidenceType
                    .AUTHORITATIVE_STOPPED
                ),
            )

    states = tuple(
        BrandTruckOperationalState(
            brand_id=key[0],
            truck_id=key[1],
            status=accumulator.resolve_status(),
            sales_activity_count=(
                accumulator.sales_activity_count
            ),
            sales_total=accumulator.sales_total,
            authoritative_stopped_count=(
                accumulator.authoritative_stopped_count
            ),
            possible_stopped_count=(
                accumulator.possible_stopped_count
            ),
            activity_row_ids=tuple(
                sorted(accumulator.activity_row_ids)
            ),
            authoritative_stopped_row_ids=tuple(
                sorted(
                    accumulator
                    .authoritative_stopped_row_ids
                )
            ),
            possible_stopped_row_ids=tuple(
                sorted(
                    accumulator.possible_stopped_row_ids
                )
            ),
        )
        for key, accumulator in sorted(
            buckets.items()
        )
    )

    return TruckOperationalStatusResult(
        requested_period_start=period_start,
        requested_period_end=period_end,
        source_row_count=source_row_count,
        included_evidence_row_count=(
            included_evidence_row_count
        ),
        ignored_accepted_non_sales_count=(
            ignored_accepted_non_sales_count
        ),
        outside_requested_period_count=(
            outside_requested_period_count
        ),
        partial_overlap_excluded_count=(
            partial_overlap_excluded_count
        ),
        states=states,
        attribution_issues=tuple(
            attribution_issues
        ),
    )
