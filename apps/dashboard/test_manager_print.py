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
        self.assertContains(response, "تقرير أداء الإدارة")
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

    def test_detail_permissions_and_no_build_for_unauthorized(self):
        detail = reverse("dashboard:manager_print_detail")
        with patch("apps.dashboard.manager_print.build_detail_context") as build:
            self.client.force_login(self.other)
            self.assertEqual(self.client.get(detail, self.filters).status_code, 403)
            self.client.logout()
            self.assertEqual(self.client.get(detail, self.filters).status_code, 302)
            build.assert_not_called()
        for user in (self.manager, self.admin):
            self.client.force_login(user)
            response = self.client.get(detail, self.filters)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "هذا تقرير تفصيلي وقد يحتوي عددًا كبيرًا من الصفحات.")
            self.assertContains(response, "جميع العلامات")
            for forbidden in ("Ask DELISKY", "Marketing Helper", "sidebar", "<nav", "<form"):
                self.assertNotContains(response, forbidden)
            self.assertIn("no-store", response.headers["Cache-Control"])

    def test_detail_filters_and_invalid_period(self):
        detail = reverse("dashboard:manager_print_detail")
        response = self.client.get(detail, {**self.filters, "brand": self.brand.pk})
        self.assertEqual(response.context["brand_id"], self.brand.pk)
        self.assertEqual(response.context["period_end"], date(2026, 10, 22))
        self.assertContains(response, "brand=" + str(self.brand.pk))
        with patch("apps.dashboard.manager_print.build_detail_context") as build:
            for data in ({}, {**self.filters, "period_start": "invalid"}, {**self.filters, "brand": "999999"}):
                self.assertEqual(self.client.get(detail, data).status_code, 400)
            build.assert_not_called()

    def test_executive_sections_and_filtered_detail_link(self):
        with patch("apps.dashboard.manager_print.build_detail_context") as detail:
            response = self.client.get(self.url, {**self.filters, "brand": self.brand.pk})
            detail.assert_not_called()
        for label in ("الملخص التنفيذي", "أولويات اجتماع المدير", "أقل المبيعات", "متابعة الزيارات",
                      "منتجات غير مباعة", "متابعة الزبائن", "نقاط تحتاج تدخل", "التقرير التفصيلي الكامل",
                      "آخر بيانات معتمدة متوفرة حتى:", "Headers and footers", "طباعة / حفظ PDF"):
            self.assertContains(response, label)
        self.assertContains(response, reverse("dashboard:manager_print_detail"))
        self.assertContains(response, "period_start=2026-08-27")
        self.assertContains(response, "brand=" + str(self.brand.pk))
        self.assertIsNone(response.context["overview_summary"].visit_success_percentage)
        self.assertContains(response, "تغطية غير متاحة")

    def test_approved_date_is_brand_scoped_and_independent_of_window(self):
        from .manager_print import _availability
        latest = SimpleNamespace(latest_period_end=date(2026, 10, 22))
        scope = dict(period_start=date(2026, 11, 1), period_end=date(2026, 11, 18), brand_id=self.brand.pk)
        with patch("apps.dashboard.manager_follow_up._source_status_rows", return_value=[latest]) as source:
            context = _availability(scope)
            source.assert_called_once_with(brand_id=self.brand.pk)
        self.assertEqual(context["latest_approved_date"], date(2026, 10, 22))
        self.assertTrue(context["beyond_coverage"])
        with patch("apps.dashboard.manager_print._availability", return_value=context):
            response = self.client.get(self.url, self.filters)
            self.assertContains(response, "22/10/2026")
            self.assertContains(response, "تنبيه: الفترة المختارة تمتد بعد آخر تاريخ بيانات معتمدة.")
        with patch("apps.dashboard.manager_follow_up._source_status_rows", return_value=[]):
            context = _availability(scope)
            self.assertIsNone(context["latest_approved_date"])
            self.assertFalse(context["beyond_coverage"])
        with patch("apps.dashboard.manager_follow_up._source_status_rows", return_value=[latest]):
            self.assertFalse(_availability({**scope, "period_end": date(2026, 10, 22)})["beyond_coverage"])

    def test_default_limits_clients_but_detail_keeps_every_row(self):
        row = SimpleNamespace(brand_name="BIFA", client_name="Client", total_sales=Decimal(10),
                              sale_record_count=1, visit_record_count=3, visited_record_count=1,
                              not_visited_record_count=3, total_record_count=4,
                              unique_client_day_count=4, visit_success_percentage=Decimal(25), brand_id=1,
                              previous_sales=Decimal(20), current_sales=Decimal(10), change_percentage=Decimal(-50))
        rows = [row] * 27
        with patch("apps.dashboard.manager_clients._top_clients", return_value=rows), \
             patch("apps.dashboard.manager_clients._client_sales_rows", return_value=rows), \
             patch("apps.dashboard.manager_clients._client_visit_rows", return_value=rows), \
             patch("apps.dashboard.manager_clients._declining_clients", return_value=rows), \
             patch("apps.dashboard.manager_clients._stopped_clients", return_value=rows), \
             patch("apps.dashboard.manager_clients._visited_without_sales", return_value=rows):
            response = self.client.get(self.url, self.filters)
            self.assertEqual([len(t["rows"]) for t in response.context["client_tables"]], [10] * 5)
            response = self.client.get(reverse("dashboard:manager_print_detail"), self.filters)
            client_section = next(s for s in response.context["sections"] if s["title"] == "العملاء")
            self.assertEqual([len(t["rows"]) for t in client_section["tables"]], [27] * 5)

    def test_product_presenter_limits_are_only_removed_for_detail(self):
        from . import manager_print
        from . import manager_sellers
        from . import manager_follow_up
        for detailed in (False, True):
            with self.subTest(detailed=detailed), \
                 patch.object(fleet, "_load_vs_sales_rows", wraps=fleet._load_vs_sales_rows) as load, \
                 patch.object(fleet, "_slow_moving_rows", wraps=fleet._slow_moving_rows) as slow, \
                 patch.object(fleet, "_not_sold_groups", wraps=fleet._not_sold_groups) as unsold, \
                 patch.object(manager_sellers, "_present_not_sold_groups", wraps=manager_sellers._present_not_sold_groups) as groups, \
                 patch.object(manager_follow_up, "_gap_rows", wraps=manager_follow_up._gap_rows) as gaps:
                response = self.client.get(reverse("dashboard:manager_print_detail") if detailed else self.url, self.filters)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(slow.call_args.kwargs["limit"], None if detailed else 15)
                self.assertEqual(unsold.call_args.kwargs["limit"], None if detailed else 15)
                self.assertEqual(groups.call_args.kwargs["limit"], None if detailed else 5)
                self.assertEqual(gaps.call_args.kwargs["limit"], None if detailed else 15)
                if detailed:
                    self.assertIsNone(load.call_args.kwargs["limit"])
                else:
                    load.assert_not_called()

    def test_unsold_groups_limit_and_remaining_counts(self):
        from . import manager_sellers
        groups = [manager_sellers.SellerNotSoldGroup(i, f"Seller {i}", None, 26,
                  tuple(manager_sellers.SellerNotSoldProductRow(f"Product {j}", Decimal(10), Decimal(0))
                        for j in range(5))) for i in range(9)]
        with patch.object(manager_sellers, "_present_not_sold_groups", return_value=groups):
            response = self.client.get(self.url, self.filters)
            self.assertEqual(len(response.context["unsold_attention"]), 5)
            self.assertTrue(all(g["remaining"] == 21 for g in response.context["unsold_attention"]))
            self.assertContains(response, "+ 21 منتجات أخرى")
            self.assertNotContains(response, "Seller 8")

    def test_empty_client_categories_pack_into_cards_and_quality_remains(self):
        response = self.client.get(self.url, self.filters)
        self.assertContains(response, 'class="client-empty-grid"')
        self.assertContains(response, 'class="empty-state compact-empty"', count=5)
        self.assertContains(response, "لا توجد حالات في الفترة", count=5)
        client_section = response.content.decode().split("متابعة الزبائن</h2>", 1)[1].split("</section>", 1)[0]
        self.assertNotIn('class="print-table-block"', client_section)
        self.assertContains(response, 'class="quality-card"', count=6)
        for label in ("إسناد المبيعات", "إسناد POS", "إسناد Items", "إسناد Chargement",
                      "تحذيرات الاستيراد", "أخطاء", "المخزون الافتتاحي", "الحالة التشغيلية",
                      "تحذيرات POS", "الصفوف المشمولة", "حالة المصادر المعتمدة"):
            self.assertContains(response, label)
        self.assertContains(response, "dashboard/css/manager_print.css")
        self.assertContains(response, 'class="print-kpi-card', count=6)



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
