from django.contrib.auth import get_user_model
from django.contrib.auth.models import (
    Group,
    Permission,
)
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import WorkerCategory
from .test_category_fixtures import (
    ensure_system_categories,
)


class WorkerCategoryAccountantViewTests(
    TestCase
):
    password = "StrongTestPassword123!"

    @classmethod
    def setUpTestData(cls):
        ensure_system_categories()

        User = get_user_model()

        cls.accountant = (
            User.objects.create_user(
                username="category_accountant",
                password=cls.password,
            )
        )

        accountant_group = (
            Group.objects.create(
                name="Accountant"
            )
        )

        category_permissions = (
            Permission.objects.filter(
                content_type__app_label=(
                    "workforce"
                ),
                content_type__model=(
                    "workercategory"
                ),
                codename__in=(
                    "view_workercategory",
                    "add_workercategory",
                    "change_workercategory",
                ),
            )
        )

        accountant_group.permissions.set(
            category_permissions
        )

        cls.accountant.groups.add(
            accountant_group
        )

        cls.manager = (
            User.objects.create_user(
                username="category_manager",
                password=cls.password,
            )
        )

        manager_group = Group.objects.create(
            name="Manager"
        )

        view_permission = Permission.objects.get(
            content_type__app_label=(
                "workforce"
            ),
            content_type__model=(
                "workercategory"
            ),
            codename="view_workercategory",
        )

        manager_group.permissions.add(
            view_permission
        )

        cls.manager.groups.add(
            manager_group
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
        self.client.login(
            username=self.accountant.username,
            password=self.password,
        )

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
            "\u0623\u0635\u0646\u0627\u0641 "
            "\u0627\u0644\u0639\u0645\u0627\u0644",
        )

        self.assertContains(
            response,
            "\u0628\u0627\u0626\u0639 "
            "\u0645\u064a\u062f\u0627\u0646\u064a",
        )

    def test_manager_cannot_access_accountant_page(
        self,
    ):
        self.client.login(
            username=self.manager.username,
            password=self.password,
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
        self.client.login(
            username=self.accountant.username,
            password=self.password,
        )

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
            (
                "\u062a\u0644\u0642\u0627\u0626\u064a "
                "\u0628\u0639\u062f "
                "\u0627\u0644\u062d\u0641\u0638"
            ),
        )

        self.assertNotContains(
            response,
            "WC-00011",
        )

    def test_accountant_can_create_category(self):
        self.client.login(
            username=self.accountant.username,
            password=self.password,
        )

        response = self.client.post(
            reverse(
                "workforce:category_create"
            ),
            {
                "name": (
                    "\u0639\u0627\u0645\u0644 "
                    "\u0635\u064a\u0627\u0646\u0629"
                ),
                "description": (
                    "\u0635\u064a\u0627\u0646\u0629 "
                    "\u062a\u062c\u0647\u064a\u0632\u0627\u062a "
                    "\u0627\u0644\u0634\u0631\u0643\u0629."
                ),
                "default_can_drive": "on",
                "default_can_assist_distribution": (
                    "on"
                ),
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

        category = (
            WorkerCategory.objects.get(
                name=(
                    "\u0639\u0627\u0645\u0644 "
                    "\u0635\u064a\u0627\u0646\u0629"
                )
            )
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

        self.assertTrue(
            category.default_can_drive
        )

        self.assertTrue(
            category
            .default_can_assist_distribution
        )

    def test_accountant_can_update_category(self):
        category = WorkerCategory.objects.create(
            name="\u062d\u0627\u0631\u0633",
            created_by=self.manager,
            updated_by=self.manager,
        )

        original_code = category.code

        self.client.login(
            username=self.accountant.username,
            password=self.password,
        )

        response = self.client.post(
            reverse(
                "workforce:category_update",
                args=[category.pk],
            ),
            {
                "name": (
                    "\u062d\u0627\u0631\u0633 "
                    "\u0627\u0644\u0645\u0642\u0631"
                ),
                "description": (
                    "\u062d\u0631\u0627\u0633\u0629 "
                    "\u0645\u0642\u0631 "
                    "\u0627\u0644\u0634\u0631\u0643\u0629."
                ),
                "default_can_train_workers": (
                    "on"
                ),
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
            (
                "\u062d\u0627\u0631\u0633 "
                "\u0627\u0644\u0645\u0642\u0631"
            ),
        )

        self.assertEqual(
            category.updated_by,
            self.accountant,
        )

        self.assertEqual(
            category.created_by,
            self.manager,
        )

    def test_accountant_can_toggle_status(self):
        category = WorkerCategory.objects.get(
            code="SELLER"
        )

        self.client.login(
            username=self.accountant.username,
            password=self.password,
        )

        response = self.client.post(
            reverse(
                "workforce:category_toggle_status",
                args=[category.pk],
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

        self.client.login(
            username=self.accountant.username,
            password=self.password,
        )

        response = self.client.get(
            reverse(
                "workforce:category_toggle_status",
                args=[category.pk],
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
            verbosity=0,
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
