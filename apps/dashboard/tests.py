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
