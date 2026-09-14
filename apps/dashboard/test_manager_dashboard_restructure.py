from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse


def _sales_result():
    return SimpleNamespace(
        overall=SimpleNamespace(
            total_sales=Decimal("1250.00"),
            sale_record_count=4,
            positive_sale_record_count=4,
            zero_total_record_count=0,
        ),
        by_worker=(),
        by_brand=(),
        by_brand_client=(),
        by_date=(),
    )


def _visits_result():
    return SimpleNamespace(
        overall=SimpleNamespace(
            total_record_count=5,
            visited_record_count=4,
            not_visited_record_count=1,
        ),
        by_brand_client=(),
    )


class ManagerDashboardFilterFirstTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="manager-filter-first",
            password="test-password",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)
        self.url = reverse(
            "dashboard:manager_dashboard"
        )

    @patch(
        "apps.dashboard.manager_views."
        "aggregate_pos_visits"
    )
    @patch(
        "apps.dashboard.manager_views."
        "aggregate_sales"
    )
    def test_initial_page_does_not_build_analytics(
        self,
        aggregate_sales,
        aggregate_pos_visits,
    ):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        aggregate_sales.assert_not_called()
        aggregate_pos_visits.assert_not_called()
        self.assertFalse(
            response.context["filter_requested"]
        )
        self.assertContains(
            response,
            "مرحبًا بك في لوحة إدارة DELISKY",
        )
        self.assertContains(
            response,
            "عرض التحليل",
        )

    @patch(
        "apps.dashboard.manager_views."
        "present_brand_sales_chart",
        return_value=(),
    )
    @patch(
        "apps.dashboard.manager_views."
        "present_sales_timeline",
        return_value=None,
    )
    @patch(
        "apps.dashboard.manager_views."
        "aggregate_pos_visits"
    )
    @patch(
        "apps.dashboard.manager_views."
        "aggregate_sales"
    )
    def test_explicit_filter_request_builds_only_overview_sources(
        self,
        aggregate_sales,
        aggregate_pos_visits,
        present_sales_timeline,
        present_brand_sales_chart,
    ):
        aggregate_sales.return_value = _sales_result()
        aggregate_pos_visits.return_value = _visits_result()

        response = self.client.get(
            self.url,
            {
                "run": "1",
                "period_start": "2026-04-04",
                "period_end": "2026-08-26",
                "brand": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.context["filter_requested"]
        )
        aggregate_sales.assert_called_once()
        aggregate_pos_visits.assert_called_once()

        sales_call = aggregate_sales.call_args.kwargs
        visits_call = aggregate_pos_visits.call_args.kwargs

        self.assertEqual(
            sales_call["period_start"],
            date(2026, 4, 4),
        )
        self.assertEqual(
            sales_call["period_end"],
            date(2026, 8, 26),
        )
        self.assertIsNone(sales_call["brand_id"])
        self.assertEqual(
            visits_call["period_start"],
            date(2026, 4, 4),
        )
        self.assertEqual(
            visits_call["period_end"],
            date(2026, 8, 26),
        )
        self.assertIsNone(visits_call["brand_id"])
        present_sales_timeline.assert_called_once()
        present_brand_sales_chart.assert_called_once()

    @patch(
        "apps.dashboard.manager_views."
        "aggregate_pos_visits"
    )
    @patch(
        "apps.dashboard.manager_views."
        "aggregate_sales"
    )
    def test_invalid_period_stays_lightweight(
        self,
        aggregate_sales,
        aggregate_pos_visits,
    ):
        response = self.client.get(
            self.url,
            {
                "run": "1",
                "period_start": "2026-08-26",
                "period_end": "2026-04-04",
                "brand": "",
            },
        )

        self.assertEqual(response.status_code, 400)
        aggregate_sales.assert_not_called()
        aggregate_pos_visits.assert_not_called()
        self.assertContains(
            response,
            "تعذر تطبيق الفلتر",
            status_code=400,
        )


class ManagerSectionRoutingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="manager-section-routing",
            password="test-password",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)

    def _assert_dispatch(
        self,
        *,
        section,
        item,
        patch_path,
        expected_label,
    ):
        with patch(patch_path) as builder:
            builder.return_value = HttpResponse("ok")
            url = reverse(
                "dashboard:manager_section",
                args=(section, item),
            )

            response = self.client.get(url)

            self.assertEqual(response.status_code, 200)
            builder.assert_called_once()
            kwargs = builder.call_args.kwargs
            self.assertEqual(kwargs["item"], item)
            self.assertEqual(
                kwargs["item_label"],
                expected_label,
            )

    def test_seller_section_is_dispatched(self):
        self._assert_dispatch(
            section="sellers",
            item="rankings",
            patch_path=(
                "apps.dashboard.manager_sections."
                "build_seller_section_response"
            ),
            expected_label="ترتيب البائعين",
        )

    def test_client_section_is_dispatched(self):
        self._assert_dispatch(
            section="clients",
            item="declining",
            patch_path=(
                "apps.dashboard.manager_sections."
                "build_client_section_response"
            ),
            expected_label="الزبائن المتراجعون",
        )

    def test_fleet_product_section_is_dispatched(self):
        self._assert_dispatch(
            section="fleet-products",
            item="slow-moving",
            patch_path=(
                "apps.dashboard.manager_sections."
                "build_fleet_product_section_response"
            ),
            expected_label="المنتجات ضعيفة الحركة",
        )

    def test_follow_up_section_is_dispatched(self):
        self._assert_dispatch(
            section="follow-up",
            item="data-quality",
            patch_path=(
                "apps.dashboard.manager_sections."
                "build_follow_up_section_response"
            ),
            expected_label="جودة البيانات",
        )

    def test_unknown_section_item_returns_404(self):
        url = reverse(
            "dashboard:manager_section",
            args=("clients", "unknown"),
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)
