from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse


class ManagerDashboardAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

        cls.User = get_user_model()

        cls.manager = cls._create_user(
            username="dashboard_manager",
            role_name="Manager",
        )
        cls.accountant = cls._create_user(
            username="dashboard_accountant",
            role_name="Accountant",
        )
        cls.ordinary_user = cls.User.objects.create_user(
            username="dashboard_ordinary",
            password="Temporary-Test-Password-2026",
            is_active=True,
        )
        cls.superuser = cls.User.objects.create_superuser(
            username="dashboard_superuser",
            password="Temporary-Test-Password-2026",
        )

    @classmethod
    def _create_user(cls, *, username, role_name):
        user = cls.User.objects.create_user(
            username=username,
            password="Temporary-Test-Password-2026",
            is_active=True,
        )
        user.groups.add(
            Group.objects.get(name=role_name)
        )
        return user

    def dashboard_url(self):
        return reverse(
            "dashboard:manager_dashboard"
        )

    def test_anonymous_user_is_redirected(self):
        response = self.client.get(
            self.dashboard_url()
        )

        self.assertEqual(response.status_code, 302)

    def test_manager_can_open_dashboard(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            self.dashboard_url()
        )

        self.assertEqual(response.status_code, 200)

    def test_superuser_can_open_dashboard(self):
        self.client.force_login(self.superuser)

        response = self.client.get(
            self.dashboard_url()
        )

        self.assertEqual(response.status_code, 200)

    def test_accountant_cannot_open_dashboard(self):
        self.client.force_login(self.accountant)

        response = self.client.get(
            self.dashboard_url()
        )

        self.assertEqual(response.status_code, 403)

    def test_ordinary_user_cannot_open_dashboard(self):
        self.client.force_login(self.ordinary_user)

        response = self.client.get(
            self.dashboard_url()
        )

        self.assertEqual(response.status_code, 403)


from datetime import date

from apps.imports.models import DistributionBrand

from .forms import ManagerDashboardFilterForm


class ManagerDashboardFilterFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.active_brand = DistributionBrand.objects.create(
            code="ACTIVE",
            name="Active Brand",
            is_active=True,
        )
        cls.inactive_brand = DistributionBrand.objects.create(
            code="INACTIVE",
            name="Inactive Brand",
            is_active=False,
        )

    def test_empty_filter_is_valid(self):
        form = ManagerDashboardFilterForm(data={})

        self.assertTrue(form.is_valid())
        self.assertIsNone(
            form.cleaned_data["period_start"]
        )
        self.assertIsNone(
            form.cleaned_data["period_end"]
        )
        self.assertIsNone(
            form.cleaned_data["brand"]
        )

    def test_period_end_cannot_precede_period_start(self):
        form = ManagerDashboardFilterForm(
            data={
                "period_start": "2026-07-20",
                "period_end": "2026-07-19",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            "تاريخ النهاية لا يمكن أن يسبق تاريخ البداية.",
            form.non_field_errors(),
        )

    def test_equal_start_and_end_dates_are_valid(self):
        form = ManagerDashboardFilterForm(
            data={
                "period_start": "2026-07-20",
                "period_end": "2026-07-20",
            }
        )

        self.assertTrue(form.is_valid())
        self.assertEqual(
            form.cleaned_data["period_start"],
            date(2026, 7, 20),
        )
        self.assertEqual(
            form.cleaned_data["period_end"],
            date(2026, 7, 20),
        )

    def test_only_active_brands_are_available(self):
        form = ManagerDashboardFilterForm()

        available_brand_ids = set(
            form.fields["brand"]
            .queryset
            .values_list("pk", flat=True)
        )

        self.assertIn(
            self.active_brand.pk,
            available_brand_ids,
        )
        self.assertNotIn(
            self.inactive_brand.pk,
            available_brand_ids,
        )

    def test_active_brand_can_be_selected(self):
        form = ManagerDashboardFilterForm(
            data={
                "brand": str(self.active_brand.pk),
            }
        )

        self.assertTrue(form.is_valid())
        self.assertEqual(
            form.cleaned_data["brand"],
            self.active_brand,
        )


from unittest.mock import patch


class ManagerDashboardViewFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

        User = get_user_model()

        cls.manager = User.objects.create_user(
            username="dashboard_filter_manager",
            password="Temporary-Test-Password-2026",
            is_active=True,
        )
        cls.manager.groups.add(
            Group.objects.get(name="Manager")
        )

        cls.active_brand = (
            DistributionBrand.objects.create(
                code="VIEW-FILTER",
                name="View Filter Brand",
                is_active=True,
            )
        )

    def setUp(self):
        self.client.force_login(self.manager)

    def dashboard_url(self):
        return reverse(
            "dashboard:manager_dashboard"
        )

    @patch(
        "apps.dashboard.views.build_manager_dashboard"
    )
    def test_empty_filters_call_dashboard_service(
        self,
        mocked_build_dashboard,
    ):
        response = self.client.get(
            self.dashboard_url()
        )

        self.assertEqual(response.status_code, 200)

        mocked_build_dashboard.assert_called_once_with(
            period_start=None,
            period_end=None,
            brand_id=None,
            product_limit=10,
        )

    @patch(
        "apps.dashboard.views.build_manager_dashboard"
    )
    def test_valid_filters_are_passed_to_service(
        self,
        mocked_build_dashboard,
    ):
        response = self.client.get(
            self.dashboard_url(),
            {
                "period_start": "2026-07-01",
                "period_end": "2026-07-20",
                "brand": str(self.active_brand.pk),
            },
        )

        self.assertEqual(response.status_code, 200)

        mocked_build_dashboard.assert_called_once_with(
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 20),
            brand_id=self.active_brand.pk,
            product_limit=10,
        )

    @patch(
        "apps.dashboard.views.build_manager_dashboard"
    )
    def test_invalid_period_does_not_call_service(
        self,
        mocked_build_dashboard,
    ):
        response = self.client.get(
            self.dashboard_url(),
            {
                "period_start": "2026-07-20",
                "period_end": "2026-07-01",
            },
        )

        self.assertEqual(response.status_code, 400)
        mocked_build_dashboard.assert_not_called()


class ManagerDashboardTemplateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

        User = get_user_model()

        cls.manager = User.objects.create_user(
            username="dashboard_template_manager",
            password="Temporary-Test-Password-2026",
            is_active=True,
        )
        cls.manager.groups.add(
            Group.objects.get(name="Manager")
        )

    def setUp(self):
        self.client.force_login(self.manager)

    def dashboard_url(self):
        return reverse(
            "dashboard:manager_dashboard"
        )

    @patch(
        "apps.dashboard.views.build_manager_dashboard"
    )
    def test_dashboard_uses_expected_template_and_context(
        self,
        mocked_build_dashboard,
    ):
        dashboard_result = object()
        mocked_build_dashboard.return_value = (
            dashboard_result
        )

        response = self.client.get(
            self.dashboard_url()
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "dashboard/manager_dashboard.html",
        )
        self.assertIsInstance(
            response.context["filter_form"],
            ManagerDashboardFilterForm,
        )
        self.assertIs(
            response.context["dashboard_result"],
            dashboard_result,
        )

    @patch(
        "apps.dashboard.views.build_manager_dashboard"
    )
    def test_invalid_filter_renders_errors_without_result(
        self,
        mocked_build_dashboard,
    ):
        response = self.client.get(
            self.dashboard_url(),
            {
                "period_start": "2026-07-20",
                "period_end": "2026-07-01",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(
            response,
            "dashboard/manager_dashboard.html",
        )
        self.assertIsNone(
            response.context["dashboard_result"]
        )
        self.assertIn(
            "تاريخ النهاية لا يمكن أن يسبق تاريخ البداية.",
            response.context[
                "filter_form"
            ].non_field_errors(),
        )
        mocked_build_dashboard.assert_not_called()


from decimal import Decimal

from django.test import SimpleTestCase

from apps.analytics.services.manager_dashboard import (
    ManagerDashboardSummary,
)

from .presenters import (
    present_manager_dashboard_summary,
)


class ManagerDashboardSummaryPresenterTests(
    SimpleTestCase
):
    def build_summary(
        self,
        *,
        total_sales=Decimal("1200.00"),
        sale_record_count=4,
        positive_sale_record_count=3,
        zero_total_record_count=1,
        pos_record_count=5,
        visited_record_count=3,
        not_visited_record_count=2,
    ):
        return ManagerDashboardSummary(
            total_sales=total_sales,
            sale_record_count=sale_record_count,
            positive_sale_record_count=(
                positive_sale_record_count
            ),
            zero_total_record_count=(
                zero_total_record_count
            ),
            worker_count=6,
            measured_sales_worker_count=5,
            pos_record_count=pos_record_count,
            visited_record_count=visited_record_count,
            not_visited_record_count=(
                not_visited_record_count
            ),
            distinct_brand_client_count=25,
            worker_not_sold_product_count=8,
            truck_not_sold_product_count=10,
            worker_negative_gap_product_count=2,
            truck_negative_gap_product_count=3,
            confirmed_stopped_truck_count=1,
            possible_stopped_truck_count=2,
            conflicting_truck_state_count=1,
        )

    def test_summary_values_are_prepared_for_template(
        self,
    ):
        presentation = (
            present_manager_dashboard_summary(
                self.build_summary()
            )
        )

        self.assertEqual(
            presentation.total_sales,
            Decimal("1200.00"),
        )
        self.assertEqual(
            presentation.average_sale_value,
            Decimal("300.00"),
        )
        self.assertEqual(
            presentation.average_positive_sale_value,
            Decimal("400.00"),
        )
        self.assertEqual(
            presentation.visit_success_percentage,
            Decimal("60"),
        )
        self.assertEqual(
            presentation.non_visit_percentage,
            Decimal("40"),
        )

    def test_missing_measurements_remain_none(
        self,
    ):
        presentation = (
            present_manager_dashboard_summary(
                self.build_summary(
                    total_sales=Decimal("0"),
                    sale_record_count=0,
                    positive_sale_record_count=0,
                    zero_total_record_count=0,
                    pos_record_count=0,
                    visited_record_count=0,
                    not_visited_record_count=0,
                )
            )
        )

        self.assertIsNone(
            presentation.average_sale_value
        )
        self.assertIsNone(
            presentation.average_positive_sale_value
        )
        self.assertIsNone(
            presentation.visit_success_percentage
        )
        self.assertIsNone(
            presentation.non_visit_percentage
        )

    def test_attention_counts_are_preserved(
        self,
    ):
        presentation = (
            present_manager_dashboard_summary(
                self.build_summary()
            )
        )

        self.assertEqual(
            presentation.worker_not_sold_product_count,
            8,
        )
        self.assertEqual(
            presentation.truck_not_sold_product_count,
            10,
        )
        self.assertEqual(
            presentation.worker_negative_gap_product_count,
            2,
        )
        self.assertEqual(
            presentation.confirmed_stopped_truck_count,
            1,
        )
        self.assertEqual(
            presentation.possible_stopped_truck_count,
            2,
        )
        self.assertEqual(
            presentation.conflicting_truck_state_count,
            1,
        )


from types import SimpleNamespace


class ManagerDashboardSummaryViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

        User = get_user_model()

        cls.manager = User.objects.create_user(
            username="dashboard_summary_manager",
            password="Temporary-Test-Password-2026",
            is_active=True,
        )
        cls.manager.groups.add(
            Group.objects.get(name="Manager")
        )

    def setUp(self):
        self.client.force_login(self.manager)

    def dashboard_url(self):
        return reverse(
            "dashboard:manager_dashboard"
        )

    @patch(
        "apps.dashboard.views."
        "present_manager_dashboard_summary"
    )
    @patch(
        "apps.dashboard.views.build_manager_dashboard"
    )
    def test_summary_is_presented_and_added_to_context(
        self,
        mocked_build_dashboard,
        mocked_present_summary,
    ):
        raw_summary = object()
        dashboard_result = SimpleNamespace(
            summary=raw_summary,
        )
        summary_presentation = object()

        mocked_build_dashboard.return_value = (
            dashboard_result
        )
        mocked_present_summary.return_value = (
            summary_presentation
        )

        response = self.client.get(
            self.dashboard_url()
        )

        self.assertEqual(response.status_code, 200)
        mocked_present_summary.assert_called_once_with(
            raw_summary
        )
        self.assertIs(
            response.context["summary"],
            summary_presentation,
        )

    @patch(
        "apps.dashboard.views."
        "present_manager_dashboard_summary"
    )
    @patch(
        "apps.dashboard.views.build_manager_dashboard"
    )
    def test_summary_cards_are_rendered(
        self,
        mocked_build_dashboard,
        mocked_present_summary,
    ):
        mocked_build_dashboard.return_value = (
            SimpleNamespace(
                summary=object(),
            )
        )

        mocked_present_summary.return_value = (
            SimpleNamespace(
                total_sales=Decimal("1200.00"),
                sale_record_count=4,
                positive_sale_record_count=3,
                zero_total_record_count=1,
                average_sale_value=Decimal("300.00"),
                average_positive_sale_value=(
                    Decimal("400.00")
                ),
                worker_count=6,
                measured_sales_worker_count=5,
                pos_record_count=5,
                visited_record_count=3,
                not_visited_record_count=2,
                visit_success_percentage=Decimal("60"),
                non_visit_percentage=Decimal("40"),
                distinct_brand_client_count=25,
                worker_not_sold_product_count=8,
                truck_not_sold_product_count=10,
                worker_negative_gap_product_count=2,
                truck_negative_gap_product_count=3,
                confirmed_stopped_truck_count=1,
                possible_stopped_truck_count=2,
                conflicting_truck_state_count=1,
            )
        )

        response = self.client.get(
            self.dashboard_url()
        )

        self.assertContains(
            response,
            "إجمالي المبيعات",
        )
        self.assertContains(
            response,
            "1200.00",
        )
        self.assertContains(
            response,
            "نسبة نجاح الزيارة",
        )
        self.assertContains(
            response,
            "60.0%",
        )
        self.assertContains(
            response,
            "المنتجات غير المباعة حسب البائع",
        )
        self.assertContains(
            response,
            "الشاحنة المتوقفة لا تُعتبر فشلًا للبائع",
        )


class ManagerDashboardTemplateStructureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

        User = get_user_model()

        cls.manager = User.objects.create_user(
            username="dashboard_structure_manager",
            password="Temporary-Test-Password-2026",
            is_active=True,
        )
        cls.manager.groups.add(
            Group.objects.get(name="Manager")
        )

    def setUp(self):
        self.client.force_login(self.manager)

    @patch(
        "apps.dashboard.views."
        "present_manager_dashboard_summary"
    )
    @patch(
        "apps.dashboard.views.build_manager_dashboard"
    )
    def test_dashboard_uses_base_and_summary_partials(
        self,
        mocked_build_dashboard,
        mocked_present_summary,
    ):
        mocked_build_dashboard.return_value = (
            SimpleNamespace(summary=object())
        )

        mocked_present_summary.return_value = (
            SimpleNamespace(
                total_sales=Decimal("1200.00"),
                sale_record_count=4,
                positive_sale_record_count=3,
                zero_total_record_count=1,
                average_positive_sale_value=(
                    Decimal("400.00")
                ),
                worker_count=6,
                measured_sales_worker_count=5,
                pos_record_count=5,
                visited_record_count=3,
                not_visited_record_count=2,
                visit_success_percentage=Decimal("60"),
                non_visit_percentage=Decimal("40"),
                distinct_brand_client_count=25,
                worker_not_sold_product_count=8,
                truck_not_sold_product_count=10,
                worker_negative_gap_product_count=2,
                truck_negative_gap_product_count=3,
                confirmed_stopped_truck_count=1,
                possible_stopped_truck_count=2,
                conflicting_truck_state_count=1,
            )
        )

        response = self.client.get(
            reverse("dashboard:manager_dashboard")
        )

        self.assertEqual(response.status_code, 200)

        expected_templates = (
            "dashboard/base.html",
            "dashboard/manager_dashboard.html",
            "dashboard/partials/filter_form.html",
            "dashboard/partials/sales_summary.html",
            "dashboard/partials/visits_summary.html",
            "dashboard/partials/workers_summary.html",
            "dashboard/partials/attention_summary.html",
            "dashboard/partials/truck_status.html",
        )

        for template_name in expected_templates:
            self.assertTemplateUsed(
                response,
                template_name,
            )


from apps.analytics.services.manager_dashboard import (
    AnalyticalCoverageSummary,
)
from apps.analytics.services.worker_performance import (
    PerformanceDataQualitySummary,
)

from .presenters import (
    present_analytical_coverage,
    present_data_quality,
)


class AnalyticalCoveragePresenterTests(SimpleTestCase):
    def build_coverage(self):
        return AnalyticalCoverageSummary(
            sales_source_row_count=100,
            sales_included_row_count=80,
            sales_outside_period_count=20,

            pos_source_row_count=60,
            pos_included_row_count=50,
            pos_outside_period_count=10,

            items_source_row_count=70,
            items_included_row_count=55,
            items_outside_period_count=10,
            items_partial_overlap_count=5,

            opening_stock_source_row_count=20,
            opening_stock_included_row_count=15,
            opening_stock_outside_period_count=3,
            opening_stock_partial_overlap_count=2,

            chargement_source_row_count=40,
            chargement_included_row_count=32,
            chargement_outside_period_count=5,
            chargement_partial_overlap_count=3,

            operational_source_row_count=30,
            operational_included_row_count=24,
            operational_outside_period_count=4,
            operational_partial_overlap_count=2,
        )

    def test_coverage_values_are_preserved(self):
        presentation = present_analytical_coverage(
            self.build_coverage()
        )

        self.assertEqual(
            presentation.sales_source_row_count,
            100,
        )
        self.assertEqual(
            presentation.sales_included_row_count,
            80,
        )
        self.assertEqual(
            presentation.items_partial_overlap_count,
            5,
        )
        self.assertEqual(
            presentation.chargement_included_row_count,
            32,
        )

    def test_period_exclusion_total_is_presented(self):
        presentation = present_analytical_coverage(
            self.build_coverage()
        )

        self.assertEqual(
            presentation.period_excluded_row_count,
            64,
        )
        self.assertTrue(
            presentation.has_partial_period_exclusions
        )


class DataQualityPresenterTests(SimpleTestCase):
    def build_data_quality(self):
        return PerformanceDataQualitySummary(
            sales_attribution_issue_count=2,
            pos_attribution_issue_count=3,
            items_attribution_issue_count=4,
            opening_stock_attribution_issue_count=1,
            chargement_attribution_issue_count=2,
            operational_attribution_issue_count=1,
            pos_numeric_message_warning_count=5,
            pos_duplicate_same_day_warning_count=6,
        )

    def test_data_quality_values_are_preserved(self):
        presentation = present_data_quality(
            self.build_data_quality()
        )

        self.assertEqual(
            presentation.sales_attribution_issue_count,
            2,
        )
        self.assertEqual(
            presentation.pos_attribution_issue_count,
            3,
        )
        self.assertEqual(
            presentation.pos_numeric_message_warning_count,
            5,
        )
        self.assertEqual(
            presentation.pos_duplicate_same_day_warning_count,
            6,
        )

    def test_data_quality_totals_are_presented(self):
        presentation = present_data_quality(
            self.build_data_quality()
        )

        self.assertEqual(
            presentation.attribution_issue_count,
            13,
        )
        self.assertEqual(
            presentation.warning_count,
            11,
        )
        self.assertEqual(
            presentation.total_issue_and_warning_count,
            24,
        )


class ManagerDashboardCoverageAndQualityViewTests(
    TestCase
):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

        User = get_user_model()

        cls.manager = User.objects.create_user(
            username="dashboard_quality_manager",
            password="Temporary-Test-Password-2026",
            is_active=True,
        )
        cls.manager.groups.add(
            Group.objects.get(name="Manager")
        )

    def setUp(self):
        self.client.force_login(self.manager)

    def dashboard_url(self):
        return reverse(
            "dashboard:manager_dashboard"
        )

    @patch(
        "apps.dashboard.views.present_data_quality"
    )
    @patch(
        "apps.dashboard.views."
        "present_analytical_coverage"
    )
    @patch(
        "apps.dashboard.views."
        "present_manager_dashboard_summary"
    )
    @patch(
        "apps.dashboard.views.build_manager_dashboard"
    )
    def test_coverage_and_quality_are_added_to_context(
        self,
        mocked_build_dashboard,
        mocked_present_summary,
        mocked_present_coverage,
        mocked_present_data_quality,
    ):
        raw_summary = object()
        raw_coverage = object()
        raw_data_quality = object()

        summary_presentation = object()
        coverage_presentation = object()
        data_quality_presentation = object()

        mocked_build_dashboard.return_value = (
            SimpleNamespace(
                summary=raw_summary,
                coverage=raw_coverage,
                data_quality=raw_data_quality,
            )
        )

        mocked_present_summary.return_value = (
            summary_presentation
        )
        mocked_present_coverage.return_value = (
            coverage_presentation
        )
        mocked_present_data_quality.return_value = (
            data_quality_presentation
        )

        response = self.client.get(
            self.dashboard_url()
        )

        self.assertEqual(response.status_code, 200)

        mocked_present_coverage.assert_called_once_with(
            raw_coverage
        )
        mocked_present_data_quality.assert_called_once_with(
            raw_data_quality
        )

        self.assertIs(
            response.context["coverage"],
            coverage_presentation,
        )
        self.assertIs(
            response.context["data_quality"],
            data_quality_presentation,
        )

    @patch(
        "apps.dashboard.views.present_data_quality"
    )
    @patch(
        "apps.dashboard.views."
        "present_analytical_coverage"
    )
    @patch(
        "apps.dashboard.views."
        "present_manager_dashboard_summary"
    )
    @patch(
        "apps.dashboard.views.build_manager_dashboard"
    )
    def test_coverage_and_quality_partials_are_rendered(
        self,
        mocked_build_dashboard,
        mocked_present_summary,
        mocked_present_coverage,
        mocked_present_data_quality,
    ):
        mocked_build_dashboard.return_value = (
            SimpleNamespace(
                summary=object(),
                coverage=object(),
                data_quality=object(),
            )
        )

        mocked_present_summary.return_value = None

        mocked_present_coverage.return_value = (
            SimpleNamespace(
                sales_source_row_count=100,
                sales_included_row_count=80,
                sales_outside_period_count=20,
                pos_source_row_count=60,
                pos_included_row_count=50,
                pos_outside_period_count=10,
                items_source_row_count=70,
                items_included_row_count=55,
                items_outside_period_count=10,
                items_partial_overlap_count=5,
                opening_stock_source_row_count=20,
                opening_stock_included_row_count=15,
                opening_stock_outside_period_count=3,
                opening_stock_partial_overlap_count=2,
                chargement_source_row_count=40,
                chargement_included_row_count=32,
                chargement_outside_period_count=5,
                chargement_partial_overlap_count=3,
                operational_source_row_count=30,
                operational_included_row_count=24,
                operational_outside_period_count=4,
                operational_partial_overlap_count=2,
                period_excluded_row_count=64,
                has_partial_period_exclusions=True,
            )
        )

        mocked_present_data_quality.return_value = (
            SimpleNamespace(
                sales_attribution_issue_count=2,
                pos_attribution_issue_count=3,
                items_attribution_issue_count=4,
                opening_stock_attribution_issue_count=1,
                chargement_attribution_issue_count=2,
                operational_attribution_issue_count=1,
                pos_numeric_message_warning_count=5,
                pos_duplicate_same_day_warning_count=6,
                attribution_issue_count=13,
                warning_count=11,
                total_issue_and_warning_count=24,
            )
        )

        response = self.client.get(
            self.dashboard_url()
        )

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "dashboard/partials/coverage_summary.html",
        )
        self.assertTemplateUsed(
            response,
            "dashboard/partials/data_quality_summary.html",
        )

        self.assertContains(
            response,
            "التغطية الزمنية والاستبعادات",
        )
        self.assertContains(
            response,
            "جودة البيانات والتحذيرات",
        )
        self.assertContains(
            response,
            "64",
        )
        self.assertContains(
            response,
            "لا يتم حذف",
        )


from apps.analytics.services.worker_performance import (
    WorkerPerformanceKpi,
)

from .presenters import present_worker_ranking


class WorkerRankingPresenterTests(SimpleTestCase):
    def build_kpi(self, **overrides):
        values = {
            "worker_id": 7,
            "total_sales": Decimal("1500.00"),
            "sale_record_count": 5,
            "positive_sale_record_count": 4,
            "zero_total_record_count": 1,
            "pos_record_count": 5,
            "visited_record_count": 3,
            "not_visited_record_count": 2,
            "unique_client_day_count": 4,
            "distinct_brand_client_count": 4,
            "brand_product_count": 6,
            "sold_product_count": 4,
            "not_sold_product_count": 2,
            "negative_gap_product_count": 1,
            "sold_without_supply_context_count": 1,
        }
        values.update(overrides)

        return WorkerPerformanceKpi(**values)

    def test_worker_name_and_metrics_are_presented(self):
        worker = SimpleNamespace(
            first_name="Ahmed",
            last_name="Benali",
            employee_code="EMP-007",
        )

        presentation = present_worker_ranking(
            self.build_kpi(),
            {7: worker},
        )

        self.assertEqual(
            presentation.worker_name,
            "Ahmed Benali",
        )
        self.assertEqual(
            presentation.employee_code,
            "EMP-007",
        )
        self.assertEqual(
            presentation.average_positive_sale_value,
            Decimal("375.00"),
        )
        self.assertEqual(
            presentation.visit_success_percentage,
            Decimal("60"),
        )
        self.assertEqual(
            presentation.non_visit_percentage,
            Decimal("40"),
        )
        self.assertEqual(
            presentation.zero_total_sale_percentage,
            Decimal("20"),
        )

    def test_employee_code_is_used_when_name_is_empty(self):
        worker = SimpleNamespace(
            first_name="",
            last_name="",
            employee_code="EMP-007",
        )

        presentation = present_worker_ranking(
            self.build_kpi(),
            {7: worker},
        )

        self.assertEqual(
            presentation.worker_name,
            "EMP-007",
        )

    def test_missing_worker_has_safe_fallback_name(self):
        presentation = present_worker_ranking(
            self.build_kpi(),
            {},
        )

        self.assertEqual(
            presentation.worker_name,
            "البائع رقم 7",
        )
        self.assertIsNone(
            presentation.employee_code
        )

    def test_missing_measurements_remain_none(self):
        presentation = present_worker_ranking(
            self.build_kpi(
                total_sales=Decimal("0"),
                sale_record_count=0,
                positive_sale_record_count=0,
                zero_total_record_count=0,
                pos_record_count=0,
                visited_record_count=0,
                not_visited_record_count=0,
            ),
            {},
        )

        self.assertFalse(
            presentation.has_sales_measurement
        )
        self.assertFalse(
            presentation.has_visit_measurement
        )
        self.assertIsNone(
            presentation.average_positive_sale_value
        )
        self.assertIsNone(
            presentation.visit_success_percentage
        )
        self.assertIsNone(
            presentation.non_visit_percentage
        )
        self.assertIsNone(
            presentation.zero_total_sale_percentage
        )


from unittest.mock import Mock


class ManagerDashboardWorkerRankingViewTests(
    TestCase
):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

        User = get_user_model()

        cls.manager = User.objects.create_user(
            username="dashboard_ranking_manager",
            password="Temporary-Test-Password-2026",
            is_active=True,
        )
        cls.manager.groups.add(
            Group.objects.get(name="Manager")
        )

    def setUp(self):
        self.client.force_login(self.manager)

    def dashboard_url(self):
        return reverse(
            "dashboard:manager_dashboard"
        )

    def build_kpi(
        self,
        *,
        worker_id,
        total_sales,
        not_sold_product_count,
        not_visited_record_count,
    ):
        return WorkerPerformanceKpi(
            worker_id=worker_id,
            total_sales=Decimal(total_sales),
            sale_record_count=5,
            positive_sale_record_count=4,
            zero_total_record_count=1,
            pos_record_count=5,
            visited_record_count=(
                5 - not_visited_record_count
            ),
            not_visited_record_count=(
                not_visited_record_count
            ),
            unique_client_day_count=5,
            distinct_brand_client_count=4,
            brand_product_count=6,
            sold_product_count=(
                6 - not_sold_product_count
            ),
            not_sold_product_count=(
                not_sold_product_count
            ),
            negative_gap_product_count=1,
            sold_without_supply_context_count=0,
        )

    @patch(
        "apps.dashboard.views.Worker.objects.filter"
    )
    @patch(
        "apps.dashboard.views.build_manager_dashboard"
    )
    def test_rankings_use_one_worker_lookup_and_render(
        self,
        mocked_build_dashboard,
        mocked_worker_filter,
    ):
        first_kpi = self.build_kpi(
            worker_id=7,
            total_sales="1500.00",
            not_sold_product_count=1,
            not_visited_record_count=1,
        )
        second_kpi = self.build_kpi(
            worker_id=8,
            total_sales="700.00",
            not_sold_product_count=4,
            not_visited_record_count=3,
        )

        top_sales_method = Mock(
            return_value=(first_kpi,)
        )
        lowest_sales_method = Mock(
            return_value=(second_kpi,)
        )
        highest_non_visit_method = Mock(
            return_value=(second_kpi,)
        )
        most_not_sold_method = Mock(
            return_value=(second_kpi,)
        )

        mocked_build_dashboard.return_value = (
            SimpleNamespace(
                summary=None,
                coverage=None,
                data_quality=None,
                top_sales_workers=top_sales_method,
                lowest_sales_workers=(
                    lowest_sales_method
                ),
                highest_non_visit_rate_workers=(
                    highest_non_visit_method
                ),
                worker_performance=SimpleNamespace(
                    most_not_sold_products_workers=(
                        most_not_sold_method
                    )
                ),
            )
        )

        mocked_worker_filter.return_value = [
            SimpleNamespace(
                pk=7,
                first_name="Ahmed",
                last_name="Benali",
                employee_code="EMP-007",
            ),
            SimpleNamespace(
                pk=8,
                first_name="Karim",
                last_name="Mansouri",
                employee_code="EMP-008",
            ),
        ]

        response = self.client.get(
            self.dashboard_url()
        )

        self.assertEqual(response.status_code, 200)

        mocked_worker_filter.assert_called_once_with(
            pk__in={7, 8},
        )

        top_sales_method.assert_called_once_with(
            limit=10,
        )
        lowest_sales_method.assert_called_once_with(
            limit=10,
        )
        highest_non_visit_method.assert_called_once_with(
            limit=10,
            minimum_pos_records=3,
        )
        most_not_sold_method.assert_called_once_with(
            limit=10,
        )

        self.assertEqual(
            response.context[
                "top_sales_workers"
            ][0].worker_name,
            "Ahmed Benali",
        )
        self.assertEqual(
            response.context[
                "lowest_sales_workers"
            ][0].worker_name,
            "Karim Mansouri",
        )

        self.assertTemplateUsed(
            response,
            "dashboard/partials/worker_rankings.html",
        )
        self.assertContains(
            response,
            "أعلى البائعين مبيعًا",
        )
        self.assertContains(
            response,
            "أقل البائعين مبيعًا ضمن المقاس أداؤهم",
        )
        self.assertContains(
            response,
            "Ahmed Benali",
        )
        self.assertContains(
            response,
            "Karim Mansouri",
        )

    @patch(
        "apps.dashboard.views.Worker.objects.filter"
    )
    @patch(
        "apps.dashboard.views.build_manager_dashboard"
    )
    def test_empty_rankings_do_not_query_workers(
        self,
        mocked_build_dashboard,
        mocked_worker_filter,
    ):
        mocked_build_dashboard.return_value = (
            SimpleNamespace(
                summary=None,
                coverage=None,
                data_quality=None,
                top_sales_workers=Mock(
                    return_value=()
                ),
                lowest_sales_workers=Mock(
                    return_value=()
                ),
                highest_non_visit_rate_workers=Mock(
                    return_value=()
                ),
                worker_performance=SimpleNamespace(
                    most_not_sold_products_workers=Mock(
                        return_value=()
                    )
                ),
            )
        )

        response = self.client.get(
            self.dashboard_url()
        )

        self.assertEqual(response.status_code, 200)
        mocked_worker_filter.assert_not_called()

        self.assertEqual(
            response.context["top_sales_workers"],
            (),
        )
        self.assertEqual(
            response.context["lowest_sales_workers"],
            (),
        )
        self.assertTemplateNotUsed(
            response,
            "dashboard/partials/worker_rankings.html",
        )


from apps.analytics.services.manager_dashboard import (
    WorkerDashboardCard,
)
from apps.analytics.services.product_performance import (
    ProductQuantityContext,
    WorkerProductPerformance,
)

from .presenters import (
    present_worker_dashboard_card,
    present_worker_product,
)


class WorkerDashboardCardPresenterTests(
    SimpleTestCase
):
    def build_kpi(self):
        return WorkerPerformanceKpi(
            worker_id=7,
            total_sales=Decimal("1500.00"),
            sale_record_count=5,
            positive_sale_record_count=4,
            zero_total_record_count=1,
            pos_record_count=5,
            visited_record_count=3,
            not_visited_record_count=2,
            unique_client_day_count=4,
            distinct_brand_client_count=4,
            brand_product_count=6,
            sold_product_count=4,
            not_sold_product_count=2,
            negative_gap_product_count=1,
            sold_without_supply_context_count=1,
        )

    def build_product(
        self,
        *,
        opening,
        chargement,
        sold,
        article="Test Product",
        brand_id=3,
    ):
        return WorkerProductPerformance(
            brand_id=brand_id,
            worker_id=7,
            article=article,
            article_normalized=article.lower(),
            quantities=ProductQuantityContext(
                opening_quantity=Decimal(opening),
                chargement_quantity=Decimal(
                    chargement
                ),
                sold_quantity=Decimal(sold),
            ),
        )

    def test_product_quantities_are_presented(self):
        product = self.build_product(
            opening="10",
            chargement="5",
            sold="3",
        )

        presentation = present_worker_product(
            product,
            {
                3: SimpleNamespace(
                    name="BIFA",
                    code="BIFA",
                )
            },
        )

        self.assertEqual(
            presentation.brand_name,
            "BIFA",
        )
        self.assertEqual(
            presentation.supplied_quantity,
            Decimal("15"),
        )
        self.assertEqual(
            presentation.sold_quantity,
            Decimal("3"),
        )
        self.assertEqual(
            presentation.analytical_quantity_gap,
            Decimal("12"),
        )
        self.assertEqual(
            presentation.sold_to_supplied_percentage,
            Decimal("20"),
        )

    def test_missing_brand_has_safe_name(self):
        product = self.build_product(
            opening="4",
            chargement="0",
            sold="0",
            brand_id=9,
        )

        presentation = present_worker_product(
            product,
            {},
        )

        self.assertEqual(
            presentation.brand_name,
            "العلامة رقم 9",
        )
        self.assertTrue(
            presentation.is_not_sold
        )

    def test_worker_card_identity_and_flags_are_presented(
        self,
    ):
        not_sold_product = self.build_product(
            opening="10",
            chargement="0",
            sold="0",
            article="Unsold Product",
        )
        least_sold_product = self.build_product(
            opening="10",
            chargement="0",
            sold="1",
            article="Least Sold Product",
        )
        negative_gap_product = self.build_product(
            opening="1",
            chargement="0",
            sold="3",
            article="Negative Gap Product",
        )
        no_supply_product = self.build_product(
            opening="0",
            chargement="0",
            sold="2",
            article="No Supply Product",
        )

        card = WorkerDashboardCard(
            kpi=self.build_kpi(),
            not_sold_products=(
                not_sold_product,
            ),
            least_sold_products=(
                least_sold_product,
            ),
            negative_gap_products=(
                negative_gap_product,
            ),
            sold_without_supply_context_products=(
                no_supply_product,
            ),
        )

        presentation = (
            present_worker_dashboard_card(
                card,
                {
                    7: SimpleNamespace(
                        first_name="Ahmed",
                        last_name="Benali",
                        employee_code="EMP-007",
                    )
                },
                {
                    3: SimpleNamespace(
                        name="BIFA",
                        code="BIFA",
                    )
                },
            )
        )

        self.assertEqual(
            presentation.worker_name,
            "Ahmed Benali",
        )
        self.assertEqual(
            presentation.employee_code,
            "EMP-007",
        )
        self.assertEqual(
            presentation.metrics.total_sales,
            Decimal("1500.00"),
        )

        self.assertEqual(
            presentation
            .not_sold_products[0]
            .article,
            "Unsold Product",
        )
        self.assertEqual(
            presentation
            .least_sold_products[0]
            .sold_quantity,
            Decimal("1"),
        )
        self.assertTrue(
            presentation
            .negative_gap_products[0]
            .has_negative_quantity_gap
        )
        self.assertTrue(
            presentation
            .sold_without_supply_context_products[0]
            .is_sold_without_supply_context
        )

        self.assertTrue(
            presentation.has_product_attention_items
        )
        self.assertTrue(
            presentation.has_non_visit_attention
        )
        self.assertTrue(
            presentation.has_sales_measurement
        )
        self.assertTrue(
            presentation.has_visit_measurement
        )
        self.assertTrue(
            presentation.has_product_measurement
        )


class ManagerDashboardWorkerCardViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

        User = get_user_model()

        cls.manager = User.objects.create_user(
            username="dashboard_card_manager",
            password="Temporary-Test-Password-2026",
            is_active=True,
        )
        cls.manager.groups.add(
            Group.objects.get(name="Manager")
        )

    def setUp(self):
        self.client.force_login(self.manager)

    def dashboard_url(self):
        return reverse(
            "dashboard:manager_dashboard"
        )

    def build_kpi(self):
        return WorkerPerformanceKpi(
            worker_id=7,
            total_sales=Decimal("1500.00"),
            sale_record_count=5,
            positive_sale_record_count=4,
            zero_total_record_count=1,
            pos_record_count=5,
            visited_record_count=3,
            not_visited_record_count=2,
            unique_client_day_count=4,
            distinct_brand_client_count=4,
            brand_product_count=4,
            sold_product_count=3,
            not_sold_product_count=1,
            negative_gap_product_count=1,
            sold_without_supply_context_count=1,
        )

    def build_product(
        self,
        *,
        article,
        opening,
        chargement,
        sold,
    ):
        return WorkerProductPerformance(
            brand_id=3,
            worker_id=7,
            article=article,
            article_normalized=article.lower(),
            quantities=ProductQuantityContext(
                opening_quantity=Decimal(opening),
                chargement_quantity=Decimal(chargement),
                sold_quantity=Decimal(sold),
            ),
        )

    @patch(
        "apps.dashboard.views._load_brands_by_id"
    )
    @patch(
        "apps.dashboard.views._load_workers_by_id"
    )
    @patch(
        "apps.dashboard.views.build_manager_dashboard"
    )
    def test_worker_cards_use_shared_lookups_and_render(
        self,
        mocked_build_dashboard,
        mocked_load_workers,
        mocked_load_brands,
    ):
        not_sold = self.build_product(
            article="Unsold Product",
            opening="10",
            chargement="0",
            sold="0",
        )
        least_sold = self.build_product(
            article="Least Sold Product",
            opening="10",
            chargement="0",
            sold="1",
        )
        negative_gap = self.build_product(
            article="Negative Gap Product",
            opening="1",
            chargement="0",
            sold="3",
        )
        no_supply = self.build_product(
            article="No Supply Product",
            opening="0",
            chargement="0",
            sold="2",
        )

        kpi = self.build_kpi()

        card = WorkerDashboardCard(
            kpi=kpi,
            not_sold_products=(not_sold,),
            least_sold_products=(least_sold,),
            negative_gap_products=(negative_gap,),
            sold_without_supply_context_products=(
                no_supply,
            ),
        )

        mocked_build_dashboard.return_value = (
            SimpleNamespace(
                summary=None,
                coverage=None,
                data_quality=None,
                worker_cards=(card,),
                top_sales_workers=Mock(
                    return_value=(kpi,)
                ),
                lowest_sales_workers=Mock(
                    return_value=()
                ),
                highest_non_visit_rate_workers=Mock(
                    return_value=()
                ),
                worker_performance=SimpleNamespace(
                    most_not_sold_products_workers=Mock(
                        return_value=()
                    )
                ),
            )
        )

        mocked_load_workers.return_value = {
            7: SimpleNamespace(
                pk=7,
                first_name="Ahmed",
                last_name="Benali",
                employee_code="EMP-007",
            )
        }

        mocked_load_brands.return_value = {
            3: SimpleNamespace(
                pk=3,
                name="BIFA",
                code="BIFA",
            )
        }

        response = self.client.get(
            self.dashboard_url()
        )

        self.assertEqual(response.status_code, 200)

        mocked_load_workers.assert_called_once_with(
            {7},
        )
        mocked_load_brands.assert_called_once_with(
            {3},
        )

        self.assertEqual(
            len(response.context["worker_cards"]),
            1,
        )
        self.assertEqual(
            response.context[
                "worker_cards"
            ][0].worker_name,
            "Ahmed Benali",
        )

        self.assertTemplateUsed(
            response,
            "dashboard/partials/worker_cards.html",
        )
        self.assertContains(
            response,
            "بطاقات البائعين",
        )
        self.assertContains(
            response,
            "Ahmed Benali",
        )
        self.assertContains(
            response,
            "BIFA",
        )
        self.assertContains(
            response,
            "Unsold Product",
        )
        self.assertContains(
            response,
            "Least Sold Product",
        )
        self.assertContains(
            response,
            "Negative Gap Product",
        )
        self.assertContains(
            response,
            "No Supply Product",
        )

    @patch(
        "apps.dashboard.views._load_brands_by_id"
    )
    @patch(
        "apps.dashboard.views._load_workers_by_id"
    )
    @patch(
        "apps.dashboard.views.build_manager_dashboard"
    )
    def test_empty_cards_and_rankings_skip_lookups(
        self,
        mocked_build_dashboard,
        mocked_load_workers,
        mocked_load_brands,
    ):
        mocked_build_dashboard.return_value = (
            SimpleNamespace(
                summary=None,
                coverage=None,
                data_quality=None,
                worker_cards=(),
                top_sales_workers=Mock(
                    return_value=()
                ),
                lowest_sales_workers=Mock(
                    return_value=()
                ),
                highest_non_visit_rate_workers=Mock(
                    return_value=()
                ),
                worker_performance=SimpleNamespace(
                    most_not_sold_products_workers=Mock(
                        return_value=()
                    )
                ),
            )
        )

        response = self.client.get(
            self.dashboard_url()
        )

        self.assertEqual(response.status_code, 200)
        mocked_load_workers.assert_called_once_with(set())
        mocked_load_brands.assert_called_once_with(set())

        self.assertEqual(
            response.context["worker_cards"],
            (),
        )
        self.assertTemplateNotUsed(
            response,
            "dashboard/partials/worker_cards.html",
        )


from types import SimpleNamespace

from apps.analytics.services.sales_aggregation import (
    BrandSalesTotal,
    SalesAggregationResult,
    SalesMetrics,
)

from .presenters import present_brand_sales_chart


class BrandSalesChartPresenterTests(SimpleTestCase):
    def build_metrics(
        self,
        total_sales,
        *,
        sale_record_count=1,
        positive_sale_record_count=1,
        zero_total_record_count=0,
    ):
        return SalesMetrics(
            total_sales=Decimal(total_sales),
            sale_record_count=sale_record_count,
            positive_sale_record_count=(
                positive_sale_record_count
            ),
            zero_total_record_count=(
                zero_total_record_count
            ),
        )

    def build_sales_result(
        self,
        *,
        overall_total,
        by_brand,
    ):
        return SalesAggregationResult(
            requested_period_start=None,
            requested_period_end=None,
            source_row_count=sum(
                item.metrics.sale_record_count
                for item in by_brand
            ),
            included_row_count=sum(
                item.metrics.sale_record_count
                for item in by_brand
            ),
            outside_requested_period_count=0,
            overall=self.build_metrics(
                overall_total,
                sale_record_count=sum(
                    item.metrics.sale_record_count
                    for item in by_brand
                ),
                positive_sale_record_count=sum(
                    item.metrics
                    .positive_sale_record_count
                    for item in by_brand
                ),
                zero_total_record_count=sum(
                    item.metrics.zero_total_record_count
                    for item in by_brand
                ),
            ),
            by_brand=tuple(by_brand),
            by_truck=(),
            by_worker=(),
            by_brand_truck=(),
            by_brand_worker=(),
            by_brand_truck_worker=(),
            attribution_issues=(),
        )

    def test_brand_sales_are_sorted_and_percentages_are_presented(
        self,
    ):
        result = self.build_sales_result(
            overall_total="1000",
            by_brand=(
                BrandSalesTotal(
                    brand_id=1,
                    metrics=self.build_metrics(
                        "250",
                    ),
                ),
                BrandSalesTotal(
                    brand_id=2,
                    metrics=self.build_metrics(
                        "500",
                        sale_record_count=2,
                        positive_sale_record_count=2,
                    ),
                ),
                BrandSalesTotal(
                    brand_id=3,
                    metrics=self.build_metrics(
                        "250",
                    ),
                ),
            ),
        )

        brands_by_id = {
            1: SimpleNamespace(name="NITA", code="NITA"),
            2: SimpleNamespace(name="BIFA", code="BIFA"),
            3: SimpleNamespace(
                name="DELISKY",
                code="DELISKY",
            ),
        }

        presentation = present_brand_sales_chart(
            result,
            brands_by_id,
        )

        self.assertEqual(
            [item.brand_id for item in presentation],
            [2, 3, 1],
        )
        self.assertEqual(
            presentation[0].contribution_percentage,
            Decimal("50.0"),
        )
        self.assertEqual(
            presentation[0].relative_bar_percentage,
            Decimal("100"),
        )
        self.assertEqual(
            presentation[1].relative_bar_percentage,
            Decimal("50.0"),
        )
        self.assertEqual(
            presentation[0].sale_record_count,
            2,
        )

    def test_missing_brand_uses_safe_arabic_fallback(
        self,
    ):
        result = self.build_sales_result(
            overall_total="100",
            by_brand=(
                BrandSalesTotal(
                    brand_id=99,
                    metrics=self.build_metrics("100"),
                ),
            ),
        )

        presentation = present_brand_sales_chart(
            result,
            {},
        )

        self.assertEqual(
            presentation[0].brand_name,
            "\u0627\u0644\u0639\u0644\u0627\u0645\u0629 "
            "\u0631\u0642\u0645 99",
        )

    def test_zero_overall_sales_has_safe_empty_percentages(
        self,
    ):
        result = self.build_sales_result(
            overall_total="0",
            by_brand=(
                BrandSalesTotal(
                    brand_id=1,
                    metrics=self.build_metrics(
                        "0",
                        positive_sale_record_count=0,
                        zero_total_record_count=1,
                    ),
                ),
            ),
        )

        presentation = present_brand_sales_chart(
            result,
            {
                1: SimpleNamespace(
                    name="BIFA",
                    code="BIFA",
                ),
            },
        )

        self.assertIsNone(
            presentation[0].contribution_percentage
        )
        self.assertEqual(
            presentation[0].relative_bar_percentage,
            Decimal("0"),
        )



class BrandSalesChartViewIntegrationTests(
    SimpleTestCase
):
    def build_sales_result(
        self,
        *,
        overall_total="1000",
        by_brand=(),
    ):
        sale_record_count = sum(
            item.metrics.sale_record_count
            for item in by_brand
        )
        positive_sale_record_count = sum(
            item.metrics.positive_sale_record_count
            for item in by_brand
        )
        zero_total_record_count = sum(
            item.metrics.zero_total_record_count
            for item in by_brand
        )

        return SalesAggregationResult(
            requested_period_start=None,
            requested_period_end=None,
            source_row_count=sale_record_count,
            included_row_count=sale_record_count,
            outside_requested_period_count=0,
            overall=SalesMetrics(
                total_sales=Decimal(overall_total),
                sale_record_count=sale_record_count,
                positive_sale_record_count=(
                    positive_sale_record_count
                ),
                zero_total_record_count=(
                    zero_total_record_count
                ),
            ),
            by_brand=tuple(by_brand),
            by_truck=(),
            by_worker=(),
            by_brand_truck=(),
            by_brand_worker=(),
            by_brand_truck_worker=(),
            attribution_issues=(),
        )

    def build_dashboard_result(
        self,
        sales,
    ):
        return SimpleNamespace(
            sales=sales,
            worker_cards=(),
            top_sales_workers=Mock(
                return_value=()
            ),
            lowest_sales_workers=Mock(
                return_value=()
            ),
            highest_non_visit_rate_workers=Mock(
                return_value=()
            ),
            worker_performance=SimpleNamespace(
                most_not_sold_products_workers=Mock(
                    return_value=()
                )
            ),
        )

    @patch(
        "apps.dashboard.views._load_brands_by_id"
    )
    @patch(
        "apps.dashboard.views._load_workers_by_id"
    )
    def test_sales_chart_uses_shared_brand_lookup(
        self,
        mocked_load_workers,
        mocked_load_brands,
    ):
        from .views import _build_worker_presentations

        sales = self.build_sales_result(
            by_brand=(
                BrandSalesTotal(
                    brand_id=1,
                    metrics=SalesMetrics(
                        total_sales=Decimal("250"),
                        sale_record_count=1,
                        positive_sale_record_count=1,
                        zero_total_record_count=0,
                    ),
                ),
                BrandSalesTotal(
                    brand_id=2,
                    metrics=SalesMetrics(
                        total_sales=Decimal("750"),
                        sale_record_count=2,
                        positive_sale_record_count=2,
                        zero_total_record_count=0,
                    ),
                ),
            ),
        )

        mocked_load_workers.return_value = {}
        mocked_load_brands.return_value = {
            1: SimpleNamespace(
                name="NITA",
                code="NITA",
            ),
            2: SimpleNamespace(
                name="BIFA",
                code="BIFA",
            ),
        }

        result = _build_worker_presentations(
            self.build_dashboard_result(sales)
        )

        mocked_load_workers.assert_called_once_with(
            set()
        )
        mocked_load_brands.assert_called_once_with(
            {1, 2}
        )

        self.assertEqual(
            [
                item.brand_name
                for item in result[
                    "brand_sales_chart"
                ]
            ],
            ["BIFA", "NITA"],
        )

        self.assertEqual(
            result[
                "brand_sales_chart"
            ][0].contribution_percentage,
            Decimal("75.00"),
        )

    @patch(
        "apps.dashboard.views._load_brands_by_id"
    )
    @patch(
        "apps.dashboard.views._load_workers_by_id"
    )
    def test_empty_sales_produces_empty_chart(
        self,
        mocked_load_workers,
        mocked_load_brands,
    ):
        from .views import _build_worker_presentations

        mocked_load_workers.return_value = {}
        mocked_load_brands.return_value = {}

        result = _build_worker_presentations(
            self.build_dashboard_result(
                self.build_sales_result(
                    overall_total="0",
                    by_brand=(),
                )
            )
        )

        mocked_load_brands.assert_called_once_with(
            set()
        )

        self.assertEqual(
            result["brand_sales_chart"],
            (),
        )
