from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.analytics.services.manager_insights_orchestrator import (
    combine_manager_insights,
)


class ManagerInsightsSummaryPropagationTests(SimpleTestCase):
    def test_combine_carries_dashboard_summary(self):
        summary = object()
        dashboard = SimpleNamespace(
            requested_period_start=date(2026, 4, 4),
            requested_period_end=date(2026, 8, 26),
            brand_id=None,
            summary=summary,
            data_quality=object(),
            operational=object(),
            worker_performance=object(),
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
        ):
            result = combine_manager_insights(
                dashboard_result=dashboard,
            )

        self.assertIs(result.summary, summary)
