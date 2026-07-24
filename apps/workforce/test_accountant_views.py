from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Worker


User = get_user_model()


class AccountantWorkerViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

        cls.accountant = User.objects.create_user(
            username="worker_accountant",
            password="StrongPass123!",
        )
        cls.accountant.groups.add(
            Group.objects.get(
                name="Accountant"
            )
        )

        cls.manager = User.objects.create_user(
            username="worker_manager",
            password="StrongPass123!",
        )
        cls.manager.groups.add(
            Group.objects.get(
                name="Manager"
            )
        )

        cls.superuser = User.objects.create_superuser(
            username="worker_superuser",
            email="superuser@example.com",
            password="StrongPass123!",
        )

        cls.worker = Worker.objects.create(
            employee_code="SELLER-001",
            first_name="Ahmed",
            last_name="Mansouri",
            phone="0550000001",
            is_active=True,
        )

    def login_accountant(self):
        self.client.force_login(
            self.accountant
        )

    def test_anonymous_user_is_redirected(self):
        response = self.client.get(
            reverse(
                "workforce:worker_list"
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_manager_cannot_access_worker_area(self):
        self.client.force_login(
            self.manager
        )

        response = self.client.get(
            reverse(
                "workforce:worker_list"
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_accountant_can_open_worker_list(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "workforce:worker_list"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertTemplateUsed(
            response,
            "workforce/worker_list.html",
        )
        self.assertContains(
            response,
            self.worker.full_name,
        )

    def test_superuser_can_open_worker_list(self):
        self.client.force_login(
            self.superuser
        )

        response = self.client.get(
            reverse(
                "workforce:worker_list"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_worker_list_supports_search(self):
        Worker.objects.create(
            employee_code="SELLER-002",
            first_name="Karim",
            last_name="Brahimi",
            phone="0550000002",
        )

        self.login_accountant()

        response = self.client.get(
            reverse(
                "workforce:worker_list"
            ),
            {
                "q": "SELLER-002",
            },
        )

        self.assertContains(
            response,
            "Karim",
        )
        self.assertNotContains(
            response,
            "Ahmed",
        )

    def test_worker_list_supports_status_filter(self):
        inactive_worker = Worker.objects.create(
            employee_code="SELLER-003",
            first_name="Sofiane",
            last_name="Khelifi",
            is_active=False,
        )

        self.login_accountant()

        response = self.client.get(
            reverse(
                "workforce:worker_list"
            ),
            {
                "status": "inactive",
            },
        )

        self.assertContains(
            response,
            inactive_worker.full_name,
        )
        self.assertNotContains(
            response,
            self.worker.full_name,
        )



    def test_create_form_has_no_literal_unicode_escapes(self):
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

        self.assertNotContains(
            response,
            r"\u0627",
        )

        rendered_html = (
            response.content.decode("utf-8")
        )

        normalized_html = " ".join(
            rendered_html.split()
        )

        self.assertIn(
            "\u0627\u0644\u0631\u0645\u0632 "
            "\u0627\u0644\u062f\u0627\u062e\u0644\u064a",
            normalized_html,
        )

        self.assertIn(
            "\u0633\u064a\u0646\u0634\u0626 "
            "\u0627\u0644\u0646\u0638\u0627\u0645 "
            "\u0627\u0644\u0631\u0645\u0632 "
            "\u062a\u0644\u0642\u0627\u0626\u064a\u064b\u0627",
            normalized_html,
        )

    def test_create_form_explains_automatic_code(self):
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
        self.assertNotContains(
            response,
            'name="employee_code"',
        )
        self.assertContains(
            response,
            "DW-00001",
        )

    def test_update_form_shows_code_as_read_only(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "workforce:worker_update",
                args=[self.worker.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            self.worker.employee_code,
        )
        self.assertNotContains(
            response,
            'name="employee_code"',
        )

    def test_accountant_can_create_worker(self):
        self.login_accountant()

        response = self.client.post(
            reverse(
                "workforce:worker_create"
            ),
            {
                "first_name": "  Youcef  ",
                "last_name": "  Amrani  ",
                "phone": "  0550000010  ",
                "is_active": "on",
                "notes": "  New seller  ",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "workforce:worker_list"
            ),
        )

        worker = Worker.objects.get(
            first_name="Youcef",
            last_name="Amrani",
        )

        self.assertRegex(
            worker.employee_code,
            r"^DW-\d{5}$",
        )

        self.assertEqual(
            worker.first_name,
            "Youcef",
        )
        self.assertEqual(
            worker.last_name,
            "Amrani",
        )
        self.assertEqual(
            worker.phone,
            "0550000010",
        )
        self.assertEqual(
            worker.notes,
            "New seller",
        )
        self.assertTrue(
            worker.is_active
        )

    def test_accountant_can_update_worker(self):
        self.login_accountant()

        response = self.client.post(
            reverse(
                "workforce:worker_update",
                args=[self.worker.pk],
            ),
            {
                "employee_code": "SELLER-001",
                "first_name": "Ahmed",
                "last_name": "Mansouri",
                "phone": "0660000001",
                "is_active": "on",
                "notes": "Updated",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "workforce:worker_list"
            ),
        )

        self.worker.refresh_from_db()

        self.assertEqual(
            self.worker.phone,
            "0660000001",
        )
        self.assertEqual(
            self.worker.notes,
            "Updated",
        )

    def test_accountant_can_toggle_worker_status(self):
        self.login_accountant()

        response = self.client.post(
            reverse(
                "workforce:worker_toggle_status",
                args=[self.worker.pk],
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "workforce:worker_list"
            ),
        )

        self.worker.refresh_from_db()

        self.assertFalse(
            self.worker.is_active
        )

        self.client.post(
            reverse(
                "workforce:worker_toggle_status",
                args=[self.worker.pk],
            )
        )

        self.worker.refresh_from_db()

        self.assertTrue(
            self.worker.is_active
        )

    def test_toggle_worker_status_rejects_get(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "workforce:worker_toggle_status",
                args=[self.worker.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            405,
        )

        self.worker.refresh_from_db()

        self.assertTrue(
            self.worker.is_active
        )
