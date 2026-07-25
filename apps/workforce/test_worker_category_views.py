from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import (
    WorkerCapability,
    WorkerCategory,
)
from .test_category_fixtures import (
    ensure_system_categories,
)


User = get_user_model()


class WorkerCategoryAccountantViewTests(
    TestCase
):
    password = "StrongTestPassword123!"

    @classmethod
    def setUpTestData(cls):
        ensure_system_categories()

        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

        cls.accountant = User.objects.create_user(
            username="category_accountant",
            password=cls.password,
        )
        cls.accountant.groups.add(
            Group.objects.get(
                name="Accountant"
            )
        )

        cls.manager = User.objects.create_user(
            username="category_manager",
            password=cls.password,
        )
        cls.manager.groups.add(
            Group.objects.get(
                name="Manager"
            )
        )

        cls.drive = WorkerCapability.objects.get(
            code="CAP-DRIVE"
        )
        cls.sell = WorkerCapability.objects.get(
            code="CAP-SELL"
        )
        cls.assist = WorkerCapability.objects.get(
            code="CAP-DISTRIBUTION-ASSIST"
        )
        cls.train = WorkerCapability.objects.get(
            code="CAP-TRAIN"
        )

        cls.inactive_capability = (
            WorkerCapability.objects.create(
                name="قدرة صنف معطلة",
                sort_order=995,
                is_active=False,
            )
        )

    def login_accountant(self):
        self.client.force_login(
            self.accountant
        )

    def test_login_is_required(self):
        response = self.client.get(
            reverse(
                "workforce:category_list"
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_accountant_can_view_categories(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "workforce:category_list"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            "أصناف العمال",
        )
        self.assertContains(
            response,
            "بائع ميداني",
        )

    def test_manager_cannot_access_accountant_page(
        self,
    ):
        self.client.force_login(
            self.manager
        )

        response = self.client.get(
            reverse(
                "workforce:category_list"
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_create_page_does_not_guess_next_code(
        self,
    ):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "workforce:category_create"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            "تلقائي بعد الحفظ",
        )
        self.assertNotContains(
            response,
            "WC-00011",
        )

    def test_accountant_can_create_category(
        self,
    ):
        self.login_accountant()

        response = self.client.post(
            reverse(
                "workforce:category_create"
            ),
            {
                "name": "عامل صيانة",
                "description": (
                    "صيانة تجهيزات الشركة."
                ),
                "default_capabilities": [
                    str(self.drive.pk),
                    str(self.assist.pk),
                ],
                "sort_order": "110",
                "is_active": "on",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "workforce:category_list"
            ),
        )

        category = WorkerCategory.objects.get(
            name="عامل صيانة"
        )

        self.assertRegex(
            category.code,
            r"^WC-\d{5,}$",
        )
        self.assertEqual(
            category.created_by,
            self.accountant,
        )
        self.assertEqual(
            category.updated_by,
            self.accountant,
        )

        capability_codes = set(
            category
            .default_capabilities
            .values_list(
                "code",
                flat=True,
            )
        )

        self.assertEqual(
            capability_codes,
            {
                "CAP-DRIVE",
                "CAP-DISTRIBUTION-ASSIST",
            },
        )

    def test_accountant_can_update_category(
        self,
    ):
        category = WorkerCategory.objects.create(
            name="حارس",
            created_by=self.manager,
            updated_by=self.manager,
        )
        category.default_capabilities.add(
            self.drive
        )

        original_code = category.code

        self.login_accountant()

        response = self.client.post(
            reverse(
                "workforce:category_update",
                args=(category.pk,),
            ),
            {
                "name": "حارس المقر",
                "description": (
                    "حراسة مقر الشركة."
                ),
                "default_capabilities": [
                    str(self.train.pk),
                ],
                "sort_order": "120",
                "is_active": "on",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "workforce:category_list"
            ),
        )

        category.refresh_from_db()

        self.assertEqual(
            category.code,
            original_code,
        )
        self.assertEqual(
            category.name,
            "حارس المقر",
        )
        self.assertEqual(
            category.updated_by,
            self.accountant,
        )
        self.assertEqual(
            category.created_by,
            self.manager,
        )

        capability_codes = set(
            category
            .default_capabilities
            .values_list(
                "code",
                flat=True,
            )
        )

        self.assertEqual(
            capability_codes,
            {
                "CAP-TRAIN",
            },
        )

    def test_edit_form_keeps_selected_inactive_capability(
        self,
    ):
        category = WorkerCategory.objects.create(
            name="صنف بقدرة معطلة",
            sort_order=970,
        )
        category.default_capabilities.add(
            self.inactive_capability
        )

        self.login_accountant()

        response = self.client.get(
            reverse(
                "workforce:category_update",
                args=(category.pk,),
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        form = response.context["form"]

        available_ids = set(
            form.fields[
                "default_capabilities"
            ].queryset.values_list(
                "pk",
                flat=True,
            )
        )

        selected_ids = {
            str(value)
            for value in (
                form[
                    "default_capabilities"
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
                "workforce:category_create"
            )
        )

        form = response.context["form"]

        available_ids = set(
            form.fields[
                "default_capabilities"
            ].queryset.values_list(
                "pk",
                flat=True,
            )
        )

        self.assertNotIn(
            self.inactive_capability.pk,
            available_ids,
        )

    def test_accountant_can_toggle_status(self):
        category = WorkerCategory.objects.get(
            code="SELLER"
        )

        self.login_accountant()

        response = self.client.post(
            reverse(
                "workforce:category_toggle_status",
                args=(category.pk,),
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "workforce:category_list"
            ),
        )

        category.refresh_from_db()

        self.assertFalse(
            category.is_active
        )
        self.assertEqual(
            category.updated_by,
            self.accountant,
        )

    def test_toggle_status_requires_post(self):
        category = WorkerCategory.objects.get(
            code="SELLER"
        )

        self.login_accountant()

        response = self.client.get(
            reverse(
                "workforce:category_toggle_status",
                args=(category.pk,),
            )
        )

        self.assertEqual(
            response.status_code,
            405,
        )


class WorkerCategoryRolePermissionTests(
    TestCase
):
    def test_seed_roles_assigns_expected_permissions(
        self,
    ):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

        accountant = Group.objects.get(
            name="Accountant"
        )
        manager = Group.objects.get(
            name="Manager"
        )

        accountant_permissions = set(
            accountant.permissions.filter(
                content_type__app_label=(
                    "workforce"
                ),
                content_type__model=(
                    "workercategory"
                ),
            ).values_list(
                "codename",
                flat=True,
            )
        )

        manager_permissions = set(
            manager.permissions.filter(
                content_type__app_label=(
                    "workforce"
                ),
                content_type__model=(
                    "workercategory"
                ),
            ).values_list(
                "codename",
                flat=True,
            )
        )

        self.assertEqual(
            accountant_permissions,
            {
                "view_workercategory",
                "add_workercategory",
                "change_workercategory",
            },
        )

        self.assertEqual(
            manager_permissions,
            {
                "view_workercategory",
            },
        )
