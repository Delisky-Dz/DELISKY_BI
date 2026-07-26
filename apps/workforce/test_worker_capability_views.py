from datetime import date
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import (
    Worker,
    WorkerCapability,
    WorkerCategory,
    WorkerPositionPeriod,
)

from .test_category_fixtures import ensure_system_categories


User = get_user_model()


class WorkerCapabilityViewTests(TestCase):
    password = "StrongCapabilityPassword123!"

    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

        ensure_system_categories()

        cls.accountant = User.objects.create_user(
            username="capability_accountant",
            password=cls.password,
        )
        cls.accountant.groups.add(
            Group.objects.get(
                name="Accountant"
            )
        )

        cls.drive = WorkerCapability.objects.get(
            code="CAP-DRIVE"
        )
        cls.sell = WorkerCapability.objects.get(
            code="CAP-SELL"
        )
        cls.warehouse = (
            WorkerCapability.objects.get(
                code="CAP-WAREHOUSE"
            )
        )
        cls.assist = WorkerCapability.objects.get(
            code="CAP-DISTRIBUTION-ASSIST"
        )
        cls.train = WorkerCapability.objects.get(
            code="CAP-TRAIN"
        )

        cls.inactive_capability = (
            WorkerCapability.objects.create(
                name="قدرة معطلة للاختبار",
                description=(
                    "قدرة معطلة للتأكد من "
                    "الحفاظ على الارتباطات."
                ),
                sort_order=990,
                is_active=False,
            )
        )

        cls.worker = Worker.objects.create(
            employee_code="CAP-WORKER-001",
            first_name="Capability",
            last_name="Worker",
            phone="0550000991",
            is_active=True,
        )
        cls.worker.capabilities.set(
            (
                cls.drive,
                cls.warehouse,
            )
        )

        cls.category = WorkerCategory.objects.create(
            code="CAPABILITY_ROLE",
            name="منصب تجريبي مستقل",
            sort_order=980,
        )
        cls.category.default_capabilities.set(
            (
                cls.sell,
                cls.assist,
            )
        )

    def login_accountant(self):
        self.client.force_login(
            self.accountant
        )

    def test_create_form_uses_dynamic_capabilities(
        self,
    ):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "workforce:worker_create"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        form = response.context["form"]

        self.assertIn(
            "capabilities",
            form.fields,
        )

        self.assertEqual(
            tuple(form.fields),
            (
                "first_name",
                "last_name",
                "phone",
                "capabilities",
                "is_active",
                "notes",
            ),
        )

        available_ids = set(
            form.fields[
                "capabilities"
            ].queryset.values_list(
                "pk",
                flat=True,
            )
        )

        self.assertIn(
            self.drive.pk,
            available_ids,
        )
        self.assertNotIn(
            self.inactive_capability.pk,
            available_ids,
        )

        self.assertContains(
            response,
            "قدرات العامل",
        )

    def test_accountant_creates_worker_with_capabilities(
        self,
    ):
        self.login_accountant()

        response = self.client.post(
            reverse(
                "workforce:worker_create"
            ),
            {
                "first_name": "أحمد",
                "last_name": "قدرات",
                "phone": "0550000992",
                "capabilities": [
                    str(self.drive.pk),
                    str(self.sell.pk),
                    str(self.assist.pk),
                ],
                "is_active": "on",
                "notes": (
                    "عامل بقدرات ديناميكية"
                ),
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "workforce:worker_list"
            ),
        )

        worker = Worker.objects.get(
            phone="0550000992"
        )

        actual_codes = set(
            worker.capabilities.values_list(
                "code",
                flat=True,
            )
        )

        self.assertEqual(
            actual_codes,
            {
                "CAP-DRIVE",
                "CAP-SELL",
                "CAP-DISTRIBUTION-ASSIST",
            },
        )

    def test_accountant_updates_worker_capabilities(
        self,
    ):
        self.login_accountant()

        response = self.client.post(
            reverse(
                "workforce:worker_update",
                args=(self.worker.pk,),
            ),
            {
                "first_name": (
                    self.worker.first_name
                ),
                "last_name": (
                    self.worker.last_name
                ),
                "phone": self.worker.phone,
                "capabilities": [
                    str(self.sell.pk),
                    str(self.assist.pk),
                    str(self.train.pk),
                ],
                "is_active": "on",
                "notes": "تم تعديل القدرات",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "workforce:worker_list"
            ),
        )

        self.worker.refresh_from_db()

        actual_codes = set(
            self.worker.capabilities.values_list(
                "code",
                flat=True,
            )
        )

        self.assertEqual(
            actual_codes,
            {
                "CAP-SELL",
                "CAP-DISTRIBUTION-ASSIST",
                "CAP-TRAIN",
            },
        )

    def test_worker_detail_displays_only_assigned_capabilities(
        self,
    ):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "workforce:worker_detail",
                args=(self.worker.pk,),
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "قدرات العامل",
        )
        self.assertContains(
            response,
            self.drive.name,
        )
        self.assertContains(
            response,
            self.warehouse.name,
        )
        self.assertNotContains(
            response,
            self.sell.name,
        )

    def test_position_does_not_overwrite_capabilities(
        self,
    ):
        before_codes = set(
            self.worker.capabilities.values_list(
                "code",
                flat=True,
            )
        )

        WorkerPositionPeriod.objects.create(
            worker=self.worker,
            category=self.category,
            start_date=date.today(),
            end_date=None,
        )

        self.worker.refresh_from_db()

        after_codes = set(
            self.worker.capabilities.values_list(
                "code",
                flat=True,
            )
        )

        category_codes = set(
            self.category
            .default_capabilities
            .values_list(
                "code",
                flat=True,
            )
        )

        self.assertEqual(
            after_codes,
            before_codes,
        )
        self.assertEqual(
            category_codes,
            {
                "CAP-SELL",
                "CAP-DISTRIBUTION-ASSIST",
            },
        )

    def test_edit_form_keeps_selected_inactive_capability(
        self,
    ):
        self.worker.capabilities.add(
            self.inactive_capability
        )

        self.login_accountant()

        response = self.client.get(
            reverse(
                "workforce:worker_update",
                args=(self.worker.pk,),
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        form = response.context["form"]

        available_ids = set(
            form.fields[
                "capabilities"
            ].queryset.values_list(
                "pk",
                flat=True,
            )
        )

        selected_ids = {
            str(value)
            for value in (
                form[
                    "capabilities"
                ].value()
                or []
            )
        }

        self.assertIn(
            self.inactive_capability.pk,
            available_ids,
        )
        self.assertIn(
            str(
                self.inactive_capability.pk
            ),
            selected_ids,
        )
        self.assertContains(
            response,
            "معطلة",
        )

    def test_create_form_excludes_inactive_capability(
        self,
    ):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "workforce:worker_create"
            )
        )

        form = response.context["form"]

        available_ids = set(
            form.fields[
                "capabilities"
            ].queryset.values_list(
                "pk",
                flat=True,
            )
        )

        self.assertNotIn(
            self.inactive_capability.pk,
            available_ids,
        )
