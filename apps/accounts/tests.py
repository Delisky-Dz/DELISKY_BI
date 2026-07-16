from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase


class RolePermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )
        cls.User = get_user_model()

    def create_user_with_role(self, username, role_name):
        user = self.User.objects.create_user(
            username=username,
            password="Temporary-Test-Password-2026",
            is_active=True,
            is_staff=True,
            is_superuser=False,
        )
        user.groups.add(
            Group.objects.get(name=role_name)
        )
        return user

    def test_official_roles_have_expected_permission_counts(self):
        expected = {
            "Super Admin": 12,
            "Accountant": 9,
            "Manager": 3,
        }

        actual = {
            group.name: group.permissions.count()
            for group in Group.objects.filter(
                name__in=expected.keys()
            )
        }

        self.assertEqual(actual, expected)

    def test_accountant_can_view_add_and_change_but_not_delete(self):
        user = self.create_user_with_role(
            "accountant_auto_test",
            "Accountant",
        )

        models = (
            "workforce.worker",
            "fleet.truck",
            "fleet.workertruckassignment",
        )

        for model in models:
            app_label, model_name = model.split(".")

            self.assertTrue(
                user.has_perm(
                    f"{app_label}.view_{model_name}"
                )
            )
            self.assertTrue(
                user.has_perm(
                    f"{app_label}.add_{model_name}"
                )
            )
            self.assertTrue(
                user.has_perm(
                    f"{app_label}.change_{model_name}"
                )
            )
            self.assertFalse(
                user.has_perm(
                    f"{app_label}.delete_{model_name}"
                )
            )

    def test_manager_has_view_only_permissions(self):
        user = self.create_user_with_role(
            "manager_auto_test",
            "Manager",
        )

        models = (
            "workforce.worker",
            "fleet.truck",
            "fleet.workertruckassignment",
        )

        for model in models:
            app_label, model_name = model.split(".")

            self.assertTrue(
                user.has_perm(
                    f"{app_label}.view_{model_name}"
                )
            )
            self.assertFalse(
                user.has_perm(
                    f"{app_label}.add_{model_name}"
                )
            )
            self.assertFalse(
                user.has_perm(
                    f"{app_label}.change_{model_name}"
                )
            )
            self.assertFalse(
                user.has_perm(
                    f"{app_label}.delete_{model_name}"
                )
            )

    def test_superuser_has_complete_system_permissions(self):
        user = self.User.objects.create_superuser(
            username="super_admin_auto_test",
            password="Temporary-Test-Password-2026",
        )
        user.groups.add(
            Group.objects.get(name="Super Admin")
        )

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(
            user.has_perm("auth.add_user")
        )
        self.assertTrue(
            user.has_perm("workforce.delete_worker")
        )
        self.assertTrue(
            user.has_perm("fleet.delete_truck")
        )
