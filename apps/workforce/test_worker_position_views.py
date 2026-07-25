from datetime import date, timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import (
    Worker,
    WorkerCategory,
    WorkerPositionPeriod,
)


User = get_user_model()


class WorkerPositionAccountantViewTests(
    TestCase
):
    password = "StrongPositionPassword123!"

    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

        cls.accountant = User.objects.create_user(
            username="position_accountant",
            password=cls.password,
        )
        cls.accountant.groups.add(
            Group.objects.get(
                name="Accountant"
            )
        )

        cls.manager = User.objects.create_user(
            username="position_manager",
            password=cls.password,
        )
        cls.manager.groups.add(
            Group.objects.get(
                name="Manager"
            )
        )

        cls.worker = Worker.objects.create(
            employee_code="POSITION-WORKER-001",
            first_name="Position",
            last_name="Worker",
        )

        cls.category = WorkerCategory.objects.create(
            code="POSITION_TEST",
            name="Position test",
            sort_order=950,
        )

        cls.other_category = (
            WorkerCategory.objects.create(
                code="POSITION_TEST_2",
                name="Second position test",
                sort_order=951,
            )
        )

        cls.inactive_category = (
            WorkerCategory.objects.create(
                code="POSITION_INACTIVE",
                name="Inactive position",
                sort_order=952,
                is_active=False,
            )
        )

    def login_accountant(self):
        self.client.force_login(
            self.accountant
        )

    def test_detail_requires_login(self):
        response = self.client.get(
            reverse(
                "workforce:worker_detail",
                args=(self.worker.pk,),
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_manager_can_view_worker_detail(self):
        self.client.force_login(
            self.manager
        )

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
        self.assertEqual(
            response.context["worker"],
            self.worker,
        )

    def test_manager_cannot_create_position(self):
        self.client.force_login(
            self.manager
        )

        response = self.client.get(
            reverse(
                "workforce:worker_position_create",
                args=(self.worker.pk,),
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_worker_list_contains_detail_link(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "workforce:worker_list"
            )
        )

        self.assertContains(
            response,
            reverse(
                "workforce:worker_detail",
                args=(self.worker.pk,),
            ),
        )

    def test_detail_separates_position_states(self):
        today = date.today()

        previous = WorkerPositionPeriod.objects.create(
            worker=self.worker,
            category=self.category,
            start_date=(
                today - timedelta(days=20)
            ),
            end_date=(
                today - timedelta(days=1)
            ),
        )

        current = WorkerPositionPeriod.objects.create(
            worker=self.worker,
            category=self.other_category,
            start_date=today,
            end_date=(
                today + timedelta(days=5)
            ),
        )

        upcoming = WorkerPositionPeriod.objects.create(
            worker=self.worker,
            category=self.category,
            start_date=(
                today + timedelta(days=6)
            ),
            end_date=None,
        )

        self.client.force_login(
            self.manager
        )

        response = self.client.get(
            reverse(
                "workforce:worker_detail",
                args=(self.worker.pk,),
            )
        )

        self.assertEqual(
            response.context["current_position"],
            current,
        )
        self.assertEqual(
            response.context["upcoming_count"],
            1,
        )
        self.assertEqual(
            response.context["previous_count"],
            1,
        )

        positions = {
            position.pk: position.ui_status
            for position in response.context[
                "position_periods"
            ]
        }

        self.assertEqual(
            positions[previous.pk],
            "previous",
        )
        self.assertEqual(
            positions[current.pk],
            "current",
        )
        self.assertEqual(
            positions[upcoming.pk],
            "upcoming",
        )

    def test_accountant_creates_position_with_audit(
        self,
    ):
        self.login_accountant()

        response = self.client.post(
            reverse(
                "workforce:worker_position_create",
                args=(self.worker.pk,),
            ),
            {
                "category": self.category.pk,
                "start_date": "2026-01-01",
                "end_date": "",
                "notes": "  Initial role  ",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "workforce:worker_detail",
                args=(self.worker.pk,),
            ),
        )

        position = (
            WorkerPositionPeriod.objects.get(
                worker=self.worker
            )
        )

        self.assertEqual(
            position.category,
            self.category,
        )
        self.assertEqual(
            position.notes,
            "Initial role",
        )
        self.assertEqual(
            position.created_by,
            self.accountant,
        )
        self.assertEqual(
            position.updated_by,
            self.accountant,
        )

    def test_overlapping_position_returns_form_error(
        self,
    ):
        WorkerPositionPeriod.objects.create(
            worker=self.worker,
            category=self.category,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        self.login_accountant()

        response = self.client.post(
            reverse(
                "workforce:worker_position_create",
                args=(self.worker.pk,),
            ),
            {
                "category": self.other_category.pk,
                "start_date": "2026-01-15",
                "end_date": "2026-02-15",
                "notes": "",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertIn(
            "worker",
            response.context["form"].errors,
        )
        self.assertEqual(
            WorkerPositionPeriod.objects.filter(
                worker=self.worker
            ).count(),
            1,
        )

    def test_accountant_updates_position(self):
        position = WorkerPositionPeriod.objects.create(
            worker=self.worker,
            category=self.category,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        self.login_accountant()

        response = self.client.post(
            reverse(
                "workforce:worker_position_update",
                args=(
                    self.worker.pk,
                    position.pk,
                ),
            ),
            {
                "category": self.other_category.pk,
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "notes": "Updated role",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "workforce:worker_detail",
                args=(self.worker.pk,),
            ),
        )

        position.refresh_from_db()

        self.assertEqual(
            position.category,
            self.other_category,
        )
        self.assertEqual(
            position.notes,
            "Updated role",
        )
        self.assertEqual(
            position.updated_by,
            self.accountant,
        )

    def test_accountant_ends_current_position(self):
        position = WorkerPositionPeriod.objects.create(
            worker=self.worker,
            category=self.category,
            start_date=(
                date.today()
                - timedelta(days=5)
            ),
            end_date=None,
        )

        self.login_accountant()

        response = self.client.post(
            reverse(
                "workforce:worker_position_end",
                args=(
                    self.worker.pk,
                    position.pk,
                ),
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "workforce:worker_detail",
                args=(self.worker.pk,),
            ),
        )

        position.refresh_from_db()

        self.assertEqual(
            position.end_date,
            date.today(),
        )
        self.assertEqual(
            position.updated_by,
            self.accountant,
        )

    def test_create_form_excludes_inactive_category(
        self,
    ):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "workforce:worker_position_create",
                args=(self.worker.pk,),
            )
        )

        category_queryset = (
            response.context["form"]
            .fields["category"]
            .queryset
        )

        self.assertNotIn(
            self.inactive_category,
            category_queryset,
        )

    def test_update_form_keeps_selected_inactive_category(
        self,
    ):
        position = WorkerPositionPeriod.objects.create(
            worker=self.worker,
            category=self.inactive_category,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        self.login_accountant()

        response = self.client.get(
            reverse(
                "workforce:worker_position_update",
                args=(
                    self.worker.pk,
                    position.pk,
                ),
            )
        )

        category_queryset = (
            response.context["form"]
            .fields["category"]
            .queryset
        )

        self.assertIn(
            self.inactive_category,
            category_queryset,
        )
