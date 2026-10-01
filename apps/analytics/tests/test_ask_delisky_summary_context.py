from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from apps.analytics.services.ask_delisky_context import (
    build_ask_delisky_context,
)
from apps.analytics.services.manager_dashboard import (
    ManagerDashboardSummary,
)
from apps.analytics.services.manager_insights_orchestrator import (
    ManagerInsightsResult,
)


class AskDeliskySummaryContextTests(SimpleTestCase):
    def test_context_exposes_deterministic_manager_summary(self):
        summary = ManagerDashboardSummary(
            total_sales=Decimal("260406534.35"),
            sale_record_count=25095,
            positive_sale_record_count=25089,
            zero_total_record_count=5,
            worker_count=13,
            measured_sales_worker_count=13,
            pos_record_count=89588,
            visited_record_count=77163,
            not_visited_record_count=12425,
            distinct_brand_client_count=4453,
            worker_not_sold_product_count=102,
            truck_not_sold_product_count=102,
            worker_negative_gap_product_count=100,
            truck_negative_gap_product_count=100,
            confirmed_stopped_truck_count=0,
            possible_stopped_truck_count=0,
            conflicting_truck_state_count=0,
        )

        result = ManagerInsightsResult(
            requested_period_start=date(2026, 4, 4),
            requested_period_end=date(2026, 8, 26),
            brand_id=None,
            insights=(),
            summary=summary,
        )

        payload = build_ask_delisky_context(
            insights_result=result
        ).to_payload()

        self.assertEqual(payload["schema_version"], "2")
        self.assertEqual(
            payload["summary"]["sales"]["total"],
            "260406534.35",
        )
        self.assertEqual(
            payload["summary"]["sales"]["currency"],
            "DZD",
        )
        self.assertEqual(
            payload["summary"]["sales"]["record_count"],
            25095,
        )
        self.assertEqual(
            payload["summary"]["visits"]["record_count"],
            89588,
        )
        self.assertIsInstance(
            payload["summary"]["visits"]["success_ratio"],
            str,
        )
