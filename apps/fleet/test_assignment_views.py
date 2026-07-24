from datetime import date, timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.workforce.models import Worker

from .models import (
    Truck,
    WorkerTruckAssignment,
)


User = get_user_model()


class AccountantAssignmentViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

        cls.accountant = User.objects.create_user(
            username="assignment_accountant",
            password="StrongPass123!",
        )
        cls.accountant.groups.add(
            Group.objects.get(
                name="Accountant"
            )
        )

        cls.manager = User.objects.create_user(
            username="assignment_manager",
            password="StrongPass123!",
        )
        cls.manager.groups.add(
            Group.objects.get(
                name="Manager"
            )
        )

        cls.superuser = User.objects.create_superuser(
            username="assignment_superuser",
            email="assignment@example.com",
            password="StrongPass123!",
        )

        cls.worker_one = Worker.objects.create(
            employee_code="DW-TEST01",
            first_name="Ahmed",
            last_name="Mansouri",
            is_active=True,
        )

        cls.worker_two = Worker.objects.create(
            employee_code="DW-TEST02",
            first_name="Youcef",
            last_name="Amrani",
            is_active=True,
        )

        cls.inactive_worker = Worker.objects.create(
            employee_code="DW-TEST03",
            first_name="Inactive",
            last_name="Worker",
            is_active=False,
        )

        cls.truck_one = Truck.objects.create(
            internal_code="BIFA PSLIV01",
            registration_number="ASSIGN-TRUCK-001",
            brand="Iveco",
            model="Daily",
            is_active=True,
        )

        cls.truck_two = Truck.objects.create(
            internal_code="BIFA PSLIV02",
            registration_number="ASSIGN-TRUCK-002",
            brand="Iveco",
            model="Daily",
            is_active=True,
        )

        cls.inactive_truck = Truck.objects.create(
            internal_code="BIFA PSLIV03",
            registration_number="ASSIGN-TRUCK-003",
            brand="Iveco",
            model="Daily",
            is_active=False,
        )

        cls.current_assignment = (
            WorkerTruckAssignment.objects.create(
                worker=cls.worker_one,
                truck=cls.truck_one,
                start_date=(
                    date.today()
                    - timedelta(days=10)
                ),
                end_date=None,
                notes="Current assignment",
            )
        )

    def login_accountant(self):
        self.client.force_login(
            self.accountant
        )

    def test_anonymous_user_is_redirected(self):
        response = self.client.get(
            reverse(
                "fleet:assignment_list"
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_manager_cannot_access_assignments(self):
        self.client.force_login(
            self.manager
        )

        response = self.client.get(
            reverse(
                "fleet:assignment_list"
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_accountant_can_open_assignment_list(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "fleet:assignment_list"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertTemplateUsed(
            response,
            "fleet/assignment_list.html",
        )
        self.assertContains(
            response,
            self.worker_one.full_name,
        )
        self.assertContains(
            response,
            self.truck_one.internal_code,
        )

    def test_superuser_can_open_assignment_list(self):
        self.client.force_login(
            self.superuser
        )

        response = self.client.get(
            reverse(
                "fleet:assignment_list"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_assignment_statistics_are_correct(self):
        ended_worker = Worker.objects.create(
            employee_code="DW-END01",
            first_name="Ended",
            last_name="Seller",
        )

        ended_truck = Truck.objects.create(
            internal_code="NITA ENDED01",
            registration_number="ENDED-001",
            brand="Isuzu",
        )

        WorkerTruckAssignment.objects.create(
            worker=ended_worker,
            truck=ended_truck,
            start_date=(
                date.today()
                - timedelta(days=20)
            ),
            end_date=(
                date.today()
                - timedelta(days=5)
            ),
        )

        upcoming_worker = Worker.objects.create(
            employee_code="DW-UP01",
            first_name="Upcoming",
            last_name="Seller",
        )

        upcoming_truck = Truck.objects.create(
            internal_code="NITA FUTURE01",
            registration_number="FUTURE-001",
            brand="Isuzu",
        )

        WorkerTruckAssignment.objects.create(
            worker=upcoming_worker,
            truck=upcoming_truck,
            start_date=(
                date.today()
                + timedelta(days=5)
            ),
            end_date=None,
        )

        self.login_accountant()

        response = self.client.get(
            reverse(
                "fleet:assignment_list"
            )
        )

        self.assertEqual(
            response.context[
                "total_assignments"
            ],
            3,
        )
        self.assertEqual(
            response.context[
                "current_assignments"
            ],
            1,
        )
        self.assertEqual(
            response.context[
                "upcoming_assignments"
            ],
            1,
        )
        self.assertEqual(
            response.context[
                "ended_assignments"
            ],
            1,
        )

    def test_assignment_list_supports_search(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "fleet:assignment_list"
            ),
            {
                "q": "DW-TEST01",
            },
        )

        self.assertContains(
            response,
            self.worker_one.full_name,
        )
        self.assertContains(
            response,
            self.truck_one.internal_code,
        )

    def test_assignment_list_supports_status_filter(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "fleet:assignment_list"
            ),
            {
                "status": "current",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            len(
                response.context[
                    "assignments"
                ]
            ),
            1,
        )

    def test_create_form_excludes_inactive_choices(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "fleet:assignment_create"
            )
        )

        form = response.context["form"]

        self.assertIn(
            self.worker_one,
            form.fields[
                "worker"
            ].queryset,
        )
        self.assertNotIn(
            self.inactive_worker,
            form.fields[
                "worker"
            ].queryset,
        )
        self.assertIn(
            self.truck_two,
            form.fields[
                "truck"
            ].queryset,
        )
        self.assertNotIn(
            self.inactive_truck,
            form.fields[
                "truck"
            ].queryset,
        )

    def test_accountant_can_create_assignment(self):
        self.login_accountant()

        response = self.client.post(
            reverse(
                "fleet:assignment_create"
            ),
            {
                "worker": self.worker_two.pk,
                "truck": self.truck_two.pk,
                "start_date": (
                    date.today()
                    .isoformat()
                ),
                "end_date": "",
                "notes": "New assignment",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "fleet:assignment_list"
            ),
        )

        self.assertTrue(
            WorkerTruckAssignment.objects.filter(
                worker=self.worker_two,
                truck=self.truck_two,
                notes="New assignment",
            ).exists()
        )

    def test_overlapping_truck_is_rejected(self):
        initial_count = (
            WorkerTruckAssignment.objects.count()
        )

        self.login_accountant()

        response = self.client.post(
            reverse(
                "fleet:assignment_create"
            ),
            {
                "worker": self.worker_two.pk,
                "truck": self.truck_one.pk,
                "start_date": (
                    date.today()
                    .isoformat()
                ),
                "end_date": "",
                "notes": "",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertTrue(
            response.context[
                "form"
            ].errors
        )
        self.assertEqual(
            WorkerTruckAssignment.objects.count(),
            initial_count,
        )

    def test_overlapping_worker_is_rejected(self):
        initial_count = (
            WorkerTruckAssignment.objects.count()
        )

        self.login_accountant()

        response = self.client.post(
            reverse(
                "fleet:assignment_create"
            ),
            {
                "worker": self.worker_one.pk,
                "truck": self.truck_two.pk,
                "start_date": (
                    date.today()
                    .isoformat()
                ),
                "end_date": "",
                "notes": "",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertTrue(
            response.context[
                "form"
            ].errors
        )
        self.assertEqual(
            WorkerTruckAssignment.objects.count(),
            initial_count,
        )

    def test_new_worker_can_start_next_day(self):
        self.current_assignment.end_date = (
            date.today()
        )
        self.current_assignment.save()

        next_day = (
            date.today()
            + timedelta(days=1)
        )

        self.login_accountant()

        response = self.client.post(
            reverse(
                "fleet:assignment_create"
            ),
            {
                "worker": self.worker_two.pk,
                "truck": self.truck_one.pk,
                "start_date": (
                    next_day.isoformat()
                ),
                "end_date": "",
                "notes": "Replacement seller",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "fleet:assignment_list"
            ),
        )

        self.assertTrue(
            WorkerTruckAssignment.objects.filter(
                worker=self.worker_two,
                truck=self.truck_one,
                start_date=next_day,
            ).exists()
        )

    def test_accountant_can_update_assignment(self):
        self.login_accountant()

        response = self.client.post(
            reverse(
                "fleet:assignment_update",
                args=[
                    self.current_assignment.pk
                ],
            ),
            {
                "worker": self.worker_one.pk,
                "truck": self.truck_one.pk,
                "start_date": (
                    self.current_assignment
                    .start_date
                    .isoformat()
                ),
                "end_date": "",
                "notes": "Updated assignment",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "fleet:assignment_list"
            ),
        )

        self.current_assignment.refresh_from_db()

        self.assertEqual(
            self.current_assignment.notes,
            "Updated assignment",
        )

    def test_accountant_can_end_assignment(self):
        original_id = (
            self.current_assignment.pk
        )

        self.login_accountant()

        response = self.client.post(
            reverse(
                "fleet:assignment_end",
                args=[
                    self.current_assignment.pk
                ],
            ),
            {
                "end_date": (
                    date.today()
                    .isoformat()
                ),
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "fleet:assignment_list"
            ),
        )

        self.current_assignment.refresh_from_db()

        self.assertEqual(
            self.current_assignment.pk,
            original_id,
        )
        self.assertEqual(
            self.current_assignment.end_date,
            date.today(),
        )
        self.assertTrue(
            WorkerTruckAssignment.objects.filter(
                pk=original_id
            ).exists()
        )

    def test_end_date_before_start_is_rejected(self):
        invalid_end_date = (
            self.current_assignment.start_date
            - timedelta(days=1)
        )

        self.login_accountant()

        response = self.client.post(
            reverse(
                "fleet:assignment_end",
                args=[
                    self.current_assignment.pk
                ],
            ),
            {
                "end_date": (
                    invalid_end_date.isoformat()
                ),
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.current_assignment.refresh_from_db()

        self.assertIsNone(
            self.current_assignment.end_date
        )

    def test_assignment_templates_have_no_literal_unicode_escapes(
        self,
    ):
        self.login_accountant()

        for url_name in (
            "fleet:assignment_list",
            "fleet:assignment_create",
        ):
            response = self.client.get(
                reverse(url_name)
            )

            rendered_html = (
                response.content.decode(
                    "utf-8"
                )
            )

            self.assertNotIn(
                r"\u0627",
                rendered_html,
            )
