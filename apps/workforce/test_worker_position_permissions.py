from io import StringIO

from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase


class WorkerPositionRolePermissionTests(
    TestCase
):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

    def get_permissions(self, role_name):
        role = Group.objects.get(
            name=role_name,
        )

        return set(
            role.permissions.filter(
                content_type__app_label=(
                    "workforce"
                ),
                content_type__model=(
                    "workerpositionperiod"
                ),
            ).values_list(
                "codename",
                flat=True,
            )
        )

    def test_super_admin_has_full_permissions(
        self,
    ):
        self.assertEqual(
            self.get_permissions(
                "Super Admin"
            ),
            {
                "view_workerpositionperiod",
                "add_workerpositionperiod",
                "change_workerpositionperiod",
                "delete_workerpositionperiod",
            },
        )

    def test_accountant_can_manage_positions(
        self,
    ):
        self.assertEqual(
            self.get_permissions(
                "Accountant"
            ),
            {
                "view_workerpositionperiod",
                "add_workerpositionperiod",
                "change_workerpositionperiod",
            },
        )

    def test_manager_has_read_only_permission(
        self,
    ):
        self.assertEqual(
            self.get_permissions(
                "Manager"
            ),
            {
                "view_workerpositionperiod",
            },
        )
