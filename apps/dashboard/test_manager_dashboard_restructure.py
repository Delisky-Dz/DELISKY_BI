from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


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
        "build_manager_dashboard"
    )
    def test_initial_page_does_not_build_analytics(
        self,
        build_manager_dashboard,
    ):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        build_manager_dashboard.assert_not_called()
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
        "build_manager_dashboard"
    )
    def test_explicit_filter_request_builds_analytics(
        self,
        build_manager_dashboard,
    ):
        build_manager_dashboard.return_value = (
            SimpleNamespace(
                summary=None,
                coverage=None,
                data_quality=None,
                worker_cards=(),
                sales=None,
                visits=None,
                worker_performance=None,
            )
        )

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
        build_manager_dashboard.assert_called_once_with(
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
            brand_id=None,
            product_limit=10,
        )

    @patch(
        "apps.dashboard.manager_views."
        "build_manager_dashboard"
    )
    def test_invalid_period_stays_lightweight(
        self,
        build_manager_dashboard,
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
        build_manager_dashboard.assert_not_called()
        self.assertContains(
            response,
            "تعذر تطبيق الفلتر",
            status_code=400,
        )
