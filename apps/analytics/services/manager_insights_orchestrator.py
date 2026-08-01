from dataclasses import dataclass
from datetime import date

from .manager_dashboard import (
    ManagerDashboardResult,
    build_manager_dashboard,
)
from .manager_insights import (
    InsightCategory,
    ManagerInsight,
    detect_data_quality_insights,
    detect_mobility_insights,
    detect_operational_insights,
    detect_worker_visit_insights,
)
from .worker_truck_mobility import (
    WorkerTruckMobilityResult,
    build_worker_truck_mobility,
)


@dataclass(frozen=True, slots=True)
class ManagerInsightsResult:
    requested_period_start: date | None
    requested_period_end: date | None
    brand_id: int | None
    insights: tuple[ManagerInsight, ...]

    @property
    def has_insights(self) -> bool:
        return bool(self.insights)

    @property
    def insight_count(self) -> int:
        return len(self.insights)

    def by_category(
        self,
        category: InsightCategory,
    ) -> tuple[ManagerInsight, ...]:
        return tuple(
            insight
            for insight in self.insights
            if insight.category == category
        )


def _validate_mobility_period(
    *,
    dashboard_result: ManagerDashboardResult,
    mobility_result: WorkerTruckMobilityResult,
) -> None:
    dashboard_period = (
        dashboard_result.requested_period_start,
        dashboard_result.requested_period_end,
    )
    mobility_period = (
        mobility_result.period_start,
        mobility_result.period_end,
    )

    if dashboard_period != mobility_period:
        raise ValueError(
            "mobility_result period must match "
            "dashboard_result period."
        )


def _validate_mobility_brand(
    *,
    dashboard_result: ManagerDashboardResult,
    mobility_result: WorkerTruckMobilityResult,
) -> None:
    if dashboard_result.brand_id is None:
        return

    mismatched_brand_ids = {
        comparison.brand_id
        for comparison in mobility_result.comparisons
        if comparison.brand_id != dashboard_result.brand_id
    }

    if mismatched_brand_ids:
        raise ValueError(
            "mobility_result brands must match "
            "dashboard_result brand."
        )


def combine_manager_insights(
    *,
    dashboard_result: ManagerDashboardResult,
    mobility_result: WorkerTruckMobilityResult | None = None,
) -> ManagerInsightsResult:
    """
    Combine deterministic manager insight families.

    Detector order is intentionally stable. No global score or
    arbitrary cross-category ranking is introduced here.
    """
    if mobility_result is not None:
        _validate_mobility_period(
            dashboard_result=dashboard_result,
            mobility_result=mobility_result,
        )
        _validate_mobility_brand(
            dashboard_result=dashboard_result,
            mobility_result=mobility_result,
        )

    insights: list[ManagerInsight] = []

    insights.extend(
        detect_data_quality_insights(
            data_quality=dashboard_result.data_quality,
            period_start=(
                dashboard_result.requested_period_start
            ),
            period_end=(
                dashboard_result.requested_period_end
            ),
        )
    )

    insights.extend(
        detect_operational_insights(
            operational_result=(
                dashboard_result.operational
            ),
        )
    )

    insights.extend(
        detect_worker_visit_insights(
            performance_result=(
                dashboard_result.worker_performance
            ),
        )
    )

    if mobility_result is not None:
        insights.extend(
            detect_mobility_insights(
                mobility_result=mobility_result,
            )
        )

    return ManagerInsightsResult(
        requested_period_start=(
            dashboard_result.requested_period_start
        ),
        requested_period_end=(
            dashboard_result.requested_period_end
        ),
        brand_id=dashboard_result.brand_id,
        insights=tuple(insights),
    )


def build_manager_insights(
    *,
    period_start: date | None = None,
    period_end: date | None = None,
    brand_id: int | None = None,
) -> ManagerInsightsResult:
    """
    Build the shared manager analytical read model once, then
    derive deterministic insight families from those results.

    Mobility requires a fully bounded period. When either period
    boundary is missing, mobility is intentionally omitted rather
    than inferring dates from available data.
    """
    if (
        period_start is not None
        and period_end is not None
        and period_end < period_start
    ):
        raise ValueError(
            "period_end cannot be before period_start."
        )

    dashboard_result = build_manager_dashboard(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
    )

    mobility_result = None

    if (
        period_start is not None
        and period_end is not None
    ):
        mobility_result = build_worker_truck_mobility(
            period_start=period_start,
            period_end=period_end,
            sales_daily=(
                dashboard_result.sales
                .by_date_brand_truck_worker
            ),
            visit_daily=(
                dashboard_result.visits
                .by_date_brand_truck_worker
            ),
        )

    return combine_manager_insights(
        dashboard_result=dashboard_result,
        mobility_result=mobility_result,
    )
