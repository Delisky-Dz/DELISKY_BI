from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import WorkerCapability


User = get_user_model()


class WorkerCapabilityManagementViewTests(
    TestCase
):
    password = "StrongCapabilityManage123!"

    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

        cls.accountant = User.objects.create_user(
            username="capability_manager_accountant",
            password=cls.password,
        )
        cls.accountant.groups.add(
            Group.objects.get(
                name="Accountant"
            )
        )

        cls.manager = User.objects.create_user(
            username="capability_view_manager",
            password=cls.password,
        )
        cls.manager.groups.add(
            Group.objects.get(
                name="Manager"
            )
        )

        cls.capability = (
            WorkerCapability.objects.create(
                name="قدرة اختبارية",
                description="وصف القدرة الاختبارية",
                sort_order=900,
                is_active=True,
                is_system=False,
                created_by=cls.accountant,
                updated_by=cls.accountant,
            )
        )

    def login_accountant(self):
        self.client.force_login(
            self.accountant
        )

    def test_login_is_required(self):
        response = self.client.get(
            reverse(
                "workforce:capability_list"
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_accountant_can_view_capabilities(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "workforce:capability_list"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            "إدارة قدرات العمال",
        )
        self.assertContains(
            response,
            self.capability.name,
        )

    def test_manager_cannot_access_accountant_page(
        self,
    ):
        self.client.force_login(
            self.manager
        )

        response = self.client.get(
            reverse(
                "workforce:capability_list"
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_accountant_can_create_capability(self):
        self.login_accountant()

        response = self.client.post(
            reverse(
                "workforce:capability_create"
            ),
            {
                "name": "التحصيل",
                "description": (
                    "تحصيل المبالغ من الزبائن."
                ),
                "sort_order": "60",
                "is_active": "on",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "workforce:capability_list"
            ),
        )

        capability = (
            WorkerCapability.objects.get(
                name="التحصيل"
            )
        )

        self.assertRegex(
            capability.code,
            r"^CAP-\d{5,}$",
        )
        self.assertEqual(
            capability.created_by,
            self.accountant,
        )
        self.assertEqual(
            capability.updated_by,
            self.accountant,
        )
        self.assertTrue(
            capability.is_active
        )
        self.assertFalse(
            capability.is_system
        )

    def test_accountant_can_update_capability(self):
        original_code = self.capability.code

        self.login_accountant()

        response = self.client.post(
            reverse(
                "workforce:capability_update",
                args=(self.capability.pk,),
            ),
            {
                "name": "قدرة اختبارية معدلة",
                "description": "وصف جديد",
                "sort_order": "901",
                "is_active": "on",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "workforce:capability_list"
            ),
        )

        self.capability.refresh_from_db()

        self.assertEqual(
            self.capability.code,
            original_code,
        )
        self.assertEqual(
            self.capability.name,
            "قدرة اختبارية معدلة",
        )
        self.assertEqual(
            self.capability.updated_by,
            self.accountant,
        )

    def test_accountant_can_toggle_status(self):
        self.login_accountant()

        response = self.client.post(
            reverse(
                "workforce:capability_toggle_status",
                args=(self.capability.pk,),
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "workforce:capability_list"
            ),
        )

        self.capability.refresh_from_db()

        self.assertFalse(
            self.capability.is_active
        )
        self.assertEqual(
            self.capability.updated_by,
            self.accountant,
        )

    def test_toggle_status_requires_post(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "workforce:capability_toggle_status",
                args=(self.capability.pk,),
            )
        )

        self.assertEqual(
            response.status_code,
            405,
        )


class WorkerCapabilityRolePermissionTests(
    TestCase
):
    def test_seed_roles_assigns_capability_permissions(
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
                    "workercapability"
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
                    "workercapability"
                ),
            ).values_list(
                "codename",
                flat=True,
            )
        )

        self.assertEqual(
            accountant_permissions,
            {
                "view_workercapability",
                "add_workercapability",
                "change_workercapability",
            },
        )

        self.assertEqual(
            manager_permissions,
            {
                "view_workercapability",
            },
        )
