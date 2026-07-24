from datetime import date
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.workforce.models import Worker

from .models import Truck, WorkerTruckAssignment


User = get_user_model()


class AccountantTruckViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

        cls.accountant = User.objects.create_user(
            username="truck_accountant",
            password="StrongPass123!",
        )
        cls.accountant.groups.add(
            Group.objects.get(
                name="Accountant"
            )
        )

        cls.manager = User.objects.create_user(
            username="truck_manager",
            password="StrongPass123!",
        )
        cls.manager.groups.add(
            Group.objects.get(
                name="Manager"
            )
        )

        cls.superuser = User.objects.create_superuser(
            username="truck_superuser",
            email="truck-superuser@example.com",
            password="StrongPass123!",
        )

        cls.worker = Worker.objects.create(
            first_name="Ahmed",
            last_name="Mansouri",
            phone="0550000001",
        )

        cls.truck = Truck.objects.create(
            internal_code="BIFA PSLIV01",
            registration_number="001234-116-43",
            brand="Iveco",
            model="Daily",
            manufacturing_year=2020,
            is_active=True,
        )

        WorkerTruckAssignment.objects.create(
            worker=cls.worker,
            truck=cls.truck,
            start_date=date.today(),
        )

    def login_accountant(self):
        self.client.force_login(
            self.accountant
        )

    def test_anonymous_user_is_redirected(self):
        response = self.client.get(
            reverse(
                "fleet:truck_list"
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_manager_cannot_access_truck_area(self):
        self.client.force_login(
            self.manager
        )

        response = self.client.get(
            reverse(
                "fleet:truck_list"
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_accountant_can_open_truck_list(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "fleet:truck_list"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertTemplateUsed(
            response,
            "fleet/truck_list.html",
        )
        self.assertContains(
            response,
            self.truck.internal_code,
        )
        self.assertContains(
            response,
            self.truck.registration_number,
        )

    def test_superuser_can_open_truck_list(self):
        self.client.force_login(
            self.superuser
        )

        response = self.client.get(
            reverse(
                "fleet:truck_list"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_truck_list_shows_current_worker(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "fleet:truck_list"
            )
        )

        self.assertContains(
            response,
            self.worker.full_name,
        )
        self.assertContains(
            response,
            self.worker.employee_code,
        )

    def test_assigned_truck_statistic_is_correct(self):
        Truck.objects.create(
            internal_code="BIFA PSLIV02",
            registration_number="009999-116-43",
            brand="Iveco",
            model="Daily",
        )

        self.login_accountant()

        response = self.client.get(
            reverse(
                "fleet:truck_list"
            )
        )

        self.assertEqual(
            response.context[
                "assigned_truck_count"
            ],
            1,
        )

    def test_truck_list_supports_search(self):
        other_truck = Truck.objects.create(
            internal_code="NITA PSLIV02",
            registration_number="008888-116-43",
            brand="Isuzu",
            model="NPR",
        )

        self.login_accountant()

        response = self.client.get(
            reverse(
                "fleet:truck_list"
            ),
            {
                "q": "NITA PSLIV02",
            },
        )

        self.assertContains(
            response,
            other_truck.internal_code,
        )
        self.assertNotContains(
            response,
            self.truck.internal_code,
        )

    def test_truck_list_supports_status_filter(self):
        inactive_truck = Truck.objects.create(
            internal_code="BIFA PSLIV03",
            registration_number="007777-116-43",
            brand="Iveco",
            model="Daily",
            is_active=False,
        )

        self.login_accountant()

        response = self.client.get(
            reverse(
                "fleet:truck_list"
            ),
            {
                "status": "inactive",
            },
        )

        self.assertContains(
            response,
            inactive_truck.internal_code,
        )
        self.assertNotContains(
            response,
            self.truck.internal_code,
        )

    def test_create_form_contains_excel_code_notice(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "fleet:truck_create"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertTemplateUsed(
            response,
            "fleet/truck_form.html",
        )
        self.assertContains(
            response,
            "BIFA PSLIV01",
        )

        normalized_html = " ".join(
            response.content
            .decode("utf-8")
            .split()
        )

        self.assertIn(
            "\u062a\u0646\u0628\u064a\u0647 "
            "\u0645\u0647\u0645",
            normalized_html,
        )

        self.assertNotIn(
            r"\u062a",
            normalized_html,
        )


    def test_create_form_requires_internal_code(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "fleet:truck_create"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertTrue(
            response.context[
                "form"
            ].fields[
                "internal_code"
            ].required
        )

    def test_blank_internal_code_is_rejected(self):
        self.login_accountant()

        response = self.client.post(
            reverse(
                "fleet:truck_create"
            ),
            {
                "internal_code": "",
                "registration_number": (
                    "TEST-NO-CODE-001"
                ),
                "brand": "Isuzu",
                "model": "NPR",
                "manufacturing_year": "2021",
                "is_active": "on",
                "notes": "",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertIn(
            "internal_code",
            response.context[
                "form"
            ].errors,
        )

        self.assertFalse(
            Truck.objects.filter(
                registration_number=(
                    "TEST-NO-CODE-001"
                )
            ).exists()
        )

    def test_accountant_can_create_truck(self):
        self.login_accountant()

        response = self.client.post(
            reverse(
                "fleet:truck_create"
            ),
            {
                "internal_code": (
                    "  bifa psliv10  "
                ),
                "registration_number": (
                    "  abc-123  "
                ),
                "brand": "  Isuzu  ",
                "model": "  NPR  ",
                "manufacturing_year": "2021",
                "is_active": "on",
                "notes": "  New truck  ",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "fleet:truck_list"
            ),
        )

        truck = Truck.objects.get(
            internal_code="BIFA PSLIV10"
        )

        self.assertEqual(
            truck.registration_number,
            "ABC-123",
        )
        self.assertEqual(
            truck.brand,
            "Isuzu",
        )
        self.assertEqual(
            truck.model,
            "NPR",
        )
        self.assertEqual(
            truck.notes,
            "New truck",
        )
        self.assertTrue(
            truck.is_active
        )

    def test_accountant_can_update_truck(self):
        self.login_accountant()

        response = self.client.post(
            reverse(
                "fleet:truck_update",
                args=[self.truck.pk],
            ),
            {
                "internal_code": (
                    self.truck.internal_code
                ),
                "registration_number": (
                    self.truck.registration_number
                ),
                "brand": "Iveco",
                "model": "Eurocargo",
                "manufacturing_year": "2020",
                "is_active": "on",
                "notes": "Updated truck",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "fleet:truck_list"
            ),
        )

        self.truck.refresh_from_db()

        self.assertEqual(
            self.truck.model,
            "Eurocargo",
        )
        self.assertEqual(
            self.truck.notes,
            "Updated truck",
        )

    def test_accountant_can_toggle_truck_status(self):
        self.login_accountant()

        response = self.client.post(
            reverse(
                "fleet:truck_toggle_status",
                args=[self.truck.pk],
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "fleet:truck_list"
            ),
        )

        self.truck.refresh_from_db()

        self.assertFalse(
            self.truck.is_active
        )

        self.client.post(
            reverse(
                "fleet:truck_toggle_status",
                args=[self.truck.pk],
            )
        )

        self.truck.refresh_from_db()

        self.assertTrue(
            self.truck.is_active
        )

    def test_toggle_truck_status_rejects_get(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "fleet:truck_toggle_status",
                args=[self.truck.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            405,
        )

        self.truck.refresh_from_db()

        self.assertTrue(
            self.truck.is_active
        )
