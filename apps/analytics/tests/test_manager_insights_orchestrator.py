from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.analytics.services.manager_insights import (
    InsightCategory,
    InsightConfidence,
    InsightEvidence,
    InsightSeverity,
    ManagerInsight,
)
from apps.analytics.services.manager_insights_orchestrator import (
    ManagerInsightsResult,
    build_manager_insights,
    combine_manager_insights,
)
from apps.analytics.services.worker_truck_mobility import (
    MobilityTransitionType,
    MobilityWindowMetrics,
    WorkerTruckMobilityComparison,
    WorkerTruckMobilityResult,
)


class ManagerInsightsOrchestratorTests(SimpleTestCase):
    def make_insight(
        self,
        code,
        category,
    ):
        return ManagerInsight(
            code=code,
            category=category,
            severity=InsightSeverity.ATTENTION,
            confidence=InsightConfidence.HIGH,
            title=code,
            summary=code,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
            evidence=(
                InsightEvidence(
                    key="value",
                    label="Value",
                    value=1,
                    source="test",
                ),
            ),
        )

    def make_dashboard(
        self,
        *,
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 7),
    ):
        return SimpleNamespace(
            requested_period_start=period_start,
            requested_period_end=period_end,
            brand_id=1,
            data_quality=object(),
            operational=object(),
            worker_performance=object(),
            sales=SimpleNamespace(
                by_date_brand_truck_worker=(
                    "daily-sales",
                )
            ),
            visits=SimpleNamespace(
                by_date_brand_truck_worker=(
                    "daily-visits",
                )
            ),
        )

    def test_combine_keeps_detector_family_order(self):
        dashboard = self.make_dashboard()

        mobility = WorkerTruckMobilityResult(
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
            comparisons=(),
        )

        data_quality = self.make_insight(
            "DATA",
            InsightCategory.DATA_QUALITY,
        )
        operational = self.make_insight(
            "OPERATIONS",
            InsightCategory.OPERATIONS,
        )
        visits = self.make_insight(
            "VISITS",
            InsightCategory.VISITS,
        )
        mobility_insight = self.make_insight(
            "MOBILITY",
            InsightCategory.MOBILITY,
        )

        with (
            patch(
                "apps.analytics.services."
                "manager_insights_orchestrator."
                "detect_data_quality_insights",
                return_value=(data_quality,),
            ),
            patch(
                "apps.analytics.services."
                "manager_insights_orchestrator."
                "detect_operational_insights",
                return_value=(operational,),
            ),
            patch(
                "apps.analytics.services."
                "manager_insights_orchestrator."
                "detect_worker_visit_insights",
                return_value=(visits,),
            ),
            patch(
                "apps.analytics.services."
                "manager_insights_orchestrator."
                "detect_mobility_insights",
                return_value=(mobility_insight,),
            ),
        ):
            result = combine_manager_insights(
                dashboard_result=dashboard,
                mobility_result=mobility,
            )

        self.assertEqual(
            tuple(
                insight.code
                for insight in result.insights
            ),
            (
                "DATA",
                "OPERATIONS",
                "VISITS",
                "MOBILITY",
            ),
        )

    def test_result_can_filter_by_category(self):
        result = ManagerInsightsResult(
            requested_period_start=date(2026, 7, 1),
            requested_period_end=date(2026, 7, 7),
            brand_id=1,
            insights=(
                self.make_insight(
                    "VISITS",
                    InsightCategory.VISITS,
                ),
                self.make_insight(
                    "MOBILITY",
                    InsightCategory.MOBILITY,
                ),
            ),
        )

        self.assertTrue(result.has_insights)
        self.assertEqual(
            result.insight_count,
            2,
        )
        self.assertEqual(
            tuple(
                item.code
                for item in result.by_category(
                    InsightCategory.MOBILITY
                )
            ),
            ("MOBILITY",),
        )

    def make_mobility_comparison(
        self,
        *,
        brand_id,
    ):
        before = MobilityWindowMetrics(
            brand_id=brand_id,
            worker_id=10,
            truck_id=20,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 2),
            working_day_count=2,
            sales_measurement_day_count=0,
            visit_measurement_day_count=0,
            sales_total=None,
            sale_record_count=None,
            positive_sale_record_count=None,
            zero_total_record_count=None,
            pos_record_count=None,
            visited_record_count=None,
            not_visited_record_count=None,
            unique_client_day_count=None,
        )
        after = MobilityWindowMetrics(
            brand_id=brand_id,
            worker_id=10,
            truck_id=21,
            period_start=date(2026, 7, 4),
            period_end=date(2026, 7, 5),
            working_day_count=2,
            sales_measurement_day_count=0,
            visit_measurement_day_count=0,
            sales_total=None,
            sale_record_count=None,
            positive_sale_record_count=None,
            zero_total_record_count=None,
            pos_record_count=None,
            visited_record_count=None,
            not_visited_record_count=None,
            unique_client_day_count=None,
        )

        return WorkerTruckMobilityComparison(
            transition_type=(
                MobilityTransitionType
                .WORKER_CHANGED_TRUCK
            ),
            brand_id=brand_id,
            change_date=date(2026, 7, 4),
            gap_working_day_count=0,
            before=before,
            after=after,
        )

    def test_filtered_dashboard_rejects_other_mobility_brand(
        self,
    ):
        dashboard = self.make_dashboard()

        mobility = WorkerTruckMobilityResult(
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
            comparisons=(
                self.make_mobility_comparison(
                    brand_id=2,
                ),
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "mobility_result brands must match",
        ):
            combine_manager_insights(
                dashboard_result=dashboard,
                mobility_result=mobility,
            )

    def test_unfiltered_dashboard_allows_multiple_mobility_brands(
        self,
    ):
        dashboard = self.make_dashboard()
        dashboard.brand_id = None

        mobility = WorkerTruckMobilityResult(
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
            comparisons=(
                self.make_mobility_comparison(
                    brand_id=1,
                ),
                self.make_mobility_comparison(
                    brand_id=2,
                ),
            ),
        )

        with (
            patch(
                "apps.analytics.services."
                "manager_insights_orchestrator."
                "detect_data_quality_insights",
                return_value=(),
            ),
            patch(
                "apps.analytics.services."
                "manager_insights_orchestrator."
                "detect_operational_insights",
                return_value=(),
            ),
            patch(
                "apps.analytics.services."
                "manager_insights_orchestrator."
                "detect_worker_visit_insights",
                return_value=(),
            ),
            patch(
                "apps.analytics.services."
                "manager_insights_orchestrator."
                "detect_mobility_insights",
                return_value=(),
            ),
        ):
            result = combine_manager_insights(
                dashboard_result=dashboard,
                mobility_result=mobility,
            )

        self.assertEqual(result.brand_id, None)

    def test_mobility_period_must_match_dashboard(self):
        dashboard = self.make_dashboard()

        mobility = WorkerTruckMobilityResult(
            period_start=date(2026, 7, 2),
            period_end=date(2026, 7, 7),
            comparisons=(),
        )

        with self.assertRaisesRegex(
            ValueError,
            "mobility_result period must match",
        ):
            combine_manager_insights(
                dashboard_result=dashboard,
                mobility_result=mobility,
            )

    def test_bounded_build_reuses_dashboard_daily_rows(
        self,
    ):
        dashboard = self.make_dashboard()

        mobility = WorkerTruckMobilityResult(
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
            comparisons=(),
        )

        with (
            patch(
                "apps.analytics.services."
                "manager_insights_orchestrator."
                "build_manager_dashboard",
                return_value=dashboard,
            ) as dashboard_builder,
            patch(
                "apps.analytics.services."
                "manager_insights_orchestrator."
                "build_worker_truck_mobility",
                return_value=mobility,
            ) as mobility_builder,
            patch(
                "apps.analytics.services."
                "manager_insights_orchestrator."
                "combine_manager_insights",
                return_value=ManagerInsightsResult(
                    requested_period_start=(
                        date(2026, 7, 1)
                    ),
                    requested_period_end=(
                        date(2026, 7, 7)
                    ),
                    brand_id=1,
                    insights=(),
                ),
            ),
        ):
            build_manager_insights(
                period_start=date(2026, 7, 1),
                period_end=date(2026, 7, 7),
                brand_id=1,
            )

        dashboard_builder.assert_called_once_with(
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
            brand_id=1,
        )

        mobility_builder.assert_called_once_with(
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
            sales_daily=("daily-sales",),
            visit_daily=("daily-visits",),
        )

    def test_unbounded_build_omits_mobility(self):
        dashboard = self.make_dashboard(
            period_start=None,
            period_end=None,
        )

        with (
            patch(
                "apps.analytics.services."
                "manager_insights_orchestrator."
                "build_manager_dashboard",
                return_value=dashboard,
            ),
            patch(
                "apps.analytics.services."
                "manager_insights_orchestrator."
                "build_worker_truck_mobility",
            ) as mobility_builder,
            patch(
                "apps.analytics.services."
                "manager_insights_orchestrator."
                "combine_manager_insights",
                return_value=ManagerInsightsResult(
                    requested_period_start=None,
                    requested_period_end=None,
                    brand_id=1,
                    insights=(),
                ),
            ) as combine,
        ):
            build_manager_insights(
                brand_id=1,
            )

        mobility_builder.assert_not_called()

        self.assertIsNone(
            combine.call_args.kwargs[
                "mobility_result"
            ]
        )

    def test_invalid_period_is_rejected_before_building_dashboard(
        self,
    ):
        with patch(
            "apps.analytics.services."
            "manager_insights_orchestrator."
            "build_manager_dashboard",
        ) as dashboard_builder:
            with self.assertRaisesRegex(
                ValueError,
                "period_end cannot be before period_start",
            ):
                build_manager_insights(
                    period_start=date(2026, 7, 10),
                    period_end=date(2026, 7, 1),
                )

        dashboard_builder.assert_not_called()
