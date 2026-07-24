from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse


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
            "Super Admin": 25,
            "Accountant": 19,
            "Manager": 7,
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
            "imports.distributionbrand",
            "imports.importbatch",
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
            "imports.distributionbrand",
            "imports.importbatch",
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



class AccountAuthenticationRoutingTests(TestCase):
    password = "Safe-Test-Password-2026"

    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )
        cls.User = get_user_model()

    def create_role_user(
        self,
        username,
        role_name,
    ):
        user = self.User.objects.create_user(
            username=username,
            password=self.password,
            is_active=True,
            is_staff=True,
        )
        user.groups.add(
            Group.objects.get(name=role_name)
        )
        return user

    def test_login_page_is_available(self):
        response = self.client.get(
            reverse("accounts:login")
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            "\u062a\u0633\u062c\u064a\u0644 "
            "\u0627\u0644\u062f\u062e\u0648\u0644",
        )
        self.assertContains(
            response,
            "\u0627\u0633\u0645 "
            "\u0627\u0644\u062f\u062e\u0648\u0644",
        )

    def test_valid_login_redirects_to_role_router(
        self,
    ):
        self.create_role_user(
            "login_manager_test",
            "Manager",
        )

        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "login_manager_test",
                "password": self.password,
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:route"),
            fetch_redirect_response=False,
        )

    def test_manager_routes_to_manager_dashboard(
        self,
    ):
        user = self.create_role_user(
            "route_manager_test",
            "Manager",
        )
        self.client.force_login(user)

        response = self.client.get(
            reverse("accounts:route")
        )

        self.assertRedirects(
            response,
            reverse(
                "dashboard:manager_dashboard"
            ),
            fetch_redirect_response=False,
        )

    def test_accountant_routes_to_accountant_area(
        self,
    ):
        user = self.create_role_user(
            "route_accountant_test",
            "Accountant",
        )
        self.client.force_login(user)

        response = self.client.get(
            reverse("accounts:route")
        )

        self.assertRedirects(
            response,
            reverse("imports:accountant_home"),
            fetch_redirect_response=False,
        )

        accountant_response = self.client.get(
            reverse("imports:accountant_home")
        )

        self.assertEqual(
            accountant_response.status_code,
            200,
        )
        self.assertContains(
            accountant_response,
            "\u0648\u0627\u062c\u0647\u0629 "
            "\u0627\u0644\u0645\u062d\u0627\u0633\u0628",
        )

    def test_superuser_routes_to_admin(self):
        user = self.User.objects.create_superuser(
            username="route_superuser_test",
            password=self.password,
        )
        self.client.force_login(user)

        response = self.client.get(
            reverse("accounts:route")
        )

        self.assertRedirects(
            response,
            reverse("admin:index"),
            fetch_redirect_response=False,
        )

    def test_anonymous_router_requires_login(self):
        response = self.client.get(
            reverse("accounts:route")
        )

        expected_url = (
            reverse("accounts:login")
            + "?next="
            + reverse("accounts:route")
        )

        self.assertRedirects(
            response,
            expected_url,
            fetch_redirect_response=False,
        )

    def test_manager_cannot_access_accountant_area(
        self,
    ):
        user = self.create_role_user(
            "manager_accountant_denied_test",
            "Manager",
        )
        self.client.force_login(user)

        response = self.client.get(
            reverse("imports:accountant_home")
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_user_without_official_role_is_denied(
        self,
    ):
        user = self.User.objects.create_user(
            username="no_role_route_test",
            password=self.password,
            is_active=True,
        )
        self.client.force_login(user)

        response = self.client.get(
            reverse("accounts:route")
        )

        self.assertEqual(
            response.status_code,
            403,
        )
