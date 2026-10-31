from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, SimpleTestCase
from django.urls import reverse

from apps.imports.models import DistributionBrand
from .manager_print import table, MOVEMENT_COLUMNS
from . import manager_fleet_products as fleet
from .test_manager_dashboard_restructure import _product_performance_item


class ManagerPrintTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = get_user_model().objects.create_user(username="print-manager")
        cls.manager.groups.add(Group.objects.get_or_create(name="Manager")[0])
        cls.admin = get_user_model().objects.create_user(username="print-admin", is_superuser=True)
        cls.other = get_user_model().objects.create_user(username="print-other")
        cls.brand = DistributionBrand.objects.create(code="BIFA", name="BIFA")

    def setUp(self):
        self.client.force_login(self.manager)
        self.url = reverse("dashboard:manager_print")
        self.filters = {"period_start": "2026-08-27", "period_end": "2026-10-22", "brand": ""}

    def test_manager_can_print_and_all_brands_header(self):
        response = self.client.get(self.url, self.filters)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "جميع العلامات")
        self.assertContains(response, "تقرير DELISKY — لوحة المدير")
        self.assertContains(response, "DELISKY_Manager_Report_2026-08-27_2026-10-22")
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, "غير متاح")
        self.assertEqual(response.context["period_start"], date(2026, 8, 27))
        self.assertEqual(response.context["period_end"], date(2026, 10, 22))
        for forbidden in ("Ask DELISKY", "Marketing Helper", "sidebar", "<nav", "<form"):
            self.assertNotContains(response, forbidden)
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_super_admin_can_print(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url, self.filters).status_code, 200)

    @patch("apps.dashboard.manager_print.build_print_context")
    def test_unauthorized_does_not_build_report(self, build):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url, self.filters).status_code, 403)
        build.assert_not_called()
        self.client.logout()
        self.assertEqual(self.client.get(self.url, self.filters).status_code, 302)
        build.assert_not_called()

    @patch("apps.dashboard.manager_print.build_print_context")
    def test_invalid_or_missing_period_does_not_build(self, build):
        for data in ({}, {**self.filters, "period_end": "2026-01-01"},
                     {**self.filters, "period_start": "bad"},
                     {**self.filters, "brand": "999999"}):
            with self.subTest(data=data):
                self.assertEqual(self.client.get(self.url, data).status_code, 400)
        build.assert_not_called()

    @patch("apps.dashboard.manager_views.aggregate_sales", wraps=None)
    def test_brand_and_dates_pass_to_same_analytics(self, aggregate):
        from apps.analytics.services.sales_aggregation import aggregate_sales
        aggregate.side_effect = aggregate_sales
        response = self.client.get(self.url, {**self.filters, "brand": self.brand.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BIFA")
        self.assertEqual(response.context["brand_id"], self.brand.pk)
        self.assertEqual(aggregate.call_args_list[0].kwargs["period_start"], date(2026, 8, 27))
        self.assertEqual(aggregate.call_args_list[0].kwargs["period_end"], date(2026, 10, 22))
        self.assertEqual(aggregate.call_args_list[0].kwargs["brand_id"], self.brand.pk)

    @patch("apps.dashboard.manager_print.build_print_context")
    @patch("apps.dashboard.manager_views.aggregate_sales")
    def test_initial_manager_remains_lazy(self, aggregate, build):
        response = self.client.get(reverse("dashboard:manager_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "طباعة التقرير")
        aggregate.assert_not_called()
        build.assert_not_called()

    def test_button_only_after_successful_run(self):
        url = reverse("dashboard:manager_dashboard")
        response = self.client.get(url, {**self.filters, "run": "1"})
        self.assertContains(response, "طباعة التقرير")
        self.assertContains(response, 'target="_blank"')
        self.assertContains(response, "period_start=2026-08-27")
        self.assertContains(response, "period_end=2026-10-22")
        self.assertNotContains(self.client.get(url, self.filters), "طباعة التقرير")
        self.assertNotContains(self.client.get(url, {**self.filters, "run": "1", "period_end": "bad"}), "طباعة التقرير", status_code=400)

    def test_overview_reuses_original_presenter_and_results(self):
        from . import manager_views
        with patch.object(manager_views, "_present_overview_summary", wraps=manager_views._present_overview_summary) as presenter:
            response = self.client.get(self.url, self.filters)
        self.assertEqual(response.status_code, 200)
        presenter.assert_called_once()
        self.assertEqual(response.context["overview_summary"].total_sales,
                         presenter.call_args.args[0].overall.total_sales)
        self.assertIsNone(response.context["overview_summary"].visit_success_percentage)


class PrintPresentationTests(SimpleTestCase):
    def test_landscape_and_pagination_css(self):
        css = (Path(__file__).parent / "static/dashboard/css/manager_print.css").read_text()
        for expected in ("A4 landscape", "table-header-group", "break-inside: avoid", "overflow-wrap: anywhere", ".no-print", "print-color-adjust: exact"):
            self.assertIn(expected, css)

    def test_missing_coverage_not_rendered_as_zero(self):
        row = SimpleNamespace(truck_name="T1", article="P1", supplied_quantity=Decimal(10),
                              sold_quantity=Decimal(0), quantity_gap=Decimal(10),
                              sold_to_supplied_percentage=None, has_sales_coverage=False)
        cells = table("test", [row], MOVEMENT_COLUMNS)["rows"][0]
        self.assertEqual(cells[3:6], ["غير متاح"] * 3)
        self.assertEqual(cells[-1], "لا توجد تغطية")

    @patch("apps.dashboard.manager_fleet_products._load_trucks", return_value={})
    def test_print_includes_rows_beyond_screen_limit(self, trucks):
        products = SimpleNamespace(truck_products=tuple(
            _product_performance_item(sales_coverage=True, article=f"Product {i}", normalized=f"p{i}")
            for i in range(125)))
        self.assertEqual(len(fleet._load_vs_sales_rows(products)), 100)
        self.assertEqual(len(fleet._load_vs_sales_rows(products, limit=None)), 125)
        self.assertEqual(len(fleet._not_sold_groups(products)[0].products), 10)
        self.assertEqual(len(fleet._not_sold_groups(products, limit=None)[0].products), 125)
