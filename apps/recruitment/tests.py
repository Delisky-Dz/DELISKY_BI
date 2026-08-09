from django.test import SimpleTestCase

from .models import (
    ApplicationStatus,
    JobApplication,
    MaritalStatus,
    RequestedPosition,
)


class RecruitmentModelContractTests(SimpleTestCase):
    def test_application_defaults_to_new(self):
        application = JobApplication()

        self.assertEqual(
            application.status,
            ApplicationStatus.NEW,
        )

    def test_initial_requested_positions_are_stable(self):
        self.assertEqual(
            [value for value, _label in RequestedPosition.choices],
            [
                "SELLER",
                "DRIVER",
                "DRIVER_SELLER",
                "WAREHOUSE_KEEPER",
                "ACCOUNTING_MANAGER",
                "SALES_MANAGER",
                "SALES_SUPERVISOR",
            ],
        )

    def test_application_status_workflow_is_stable(self):
        self.assertEqual(
            [value for value, _label in ApplicationStatus.choices],
            [
                "NEW",
                "REVIEWING",
                "CONTACTED",
                "ACCEPTED",
                "REJECTED",
            ],
        )

    def test_email_and_cv_are_optional(self):
        self.assertTrue(
            JobApplication._meta.get_field("email").blank
        )
        self.assertTrue(
            JobApplication._meta.get_field("cv").blank
        )

    def test_personal_fields_do_not_create_ranking_fields(self):
        field_names = {
            field.name
            for field
            in JobApplication._meta.get_fields()
        }

        self.assertNotIn(
            "score",
            field_names,
        )
        self.assertNotIn(
            "ranking",
            field_names,
        )

    def test_marital_status_choices_are_stable(self):
        self.assertEqual(
            [value for value, _label in MaritalStatus.choices],
            [
                "SINGLE",
                "MARRIED",
                "DIVORCED",
                "WIDOWED",
            ],
        )


from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    ApplicationStatus,
    JobApplication,
)


class PublicRecruitmentApplicationTests(TestCase):
    def valid_payload(self):
        return {
            "first_name": "Ahmed",
            "last_name": "Test",
            "birth_date": "1995-01-10",
            "marital_status": "MARRIED",
            "children_count": "2",
            "phone": "0660775108",
            "email": "",
            "wilaya": "Constantine",
            "residence": "Ali Mendjeli",
            "requested_position": "SELLER",
            "experience_years": "4",
            "previous_companies": "Company A",
        }

    def test_arabic_application_page_is_available(self):
        response = self.client.get(
            "/ar/careers/apply/"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            'id="careers-application-form"',
        )

    def test_english_application_page_is_available(self):
        response = self.client.get(
            "/en/careers/apply/"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "Submit Application",
        )

    def test_valid_application_is_saved_as_new(self):
        response = self.client.post(
            "/ar/careers/apply/",
            self.valid_payload(),
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        application = (
            JobApplication.objects.get()
        )

        self.assertEqual(
            application.status,
            ApplicationStatus.NEW,
        )

        self.assertEqual(
            application.phone,
            "+213660775108",
        )

        self.assertEqual(
            application.email,
            "",
        )

    def test_invalid_phone_is_rejected(self):
        payload = self.valid_payload()
        payload["phone"] = "123"

        response = self.client.post(
            "/ar/careers/apply/",
            payload,
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            JobApplication.objects.count(),
            0,
        )

    def test_future_birth_date_is_rejected(self):
        payload = self.valid_payload()

        payload["birth_date"] = (
            timezone.localdate()
            + timedelta(days=1)
        ).isoformat()

        response = self.client.post(
            "/ar/careers/apply/",
            payload,
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            JobApplication.objects.count(),
            0,
        )

    def test_driver_requires_driving_details(self):
        payload = self.valid_payload()

        payload[
            "requested_position"
        ] = "DRIVER"

        response = self.client.post(
            "/ar/careers/apply/",
            payload,
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            JobApplication.objects.count(),
            0,
        )

    def test_non_pdf_cv_is_rejected(self):
        payload = self.valid_payload()

        fake_cv = SimpleUploadedFile(
            "cv.txt",
            b"not a pdf",
            content_type="text/plain",
        )

        response = self.client.post(
            "/ar/careers/apply/",
            {
                **payload,
                "cv": fake_cv,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            JobApplication.objects.count(),
            0,
        )


from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import (
    ApplicationStatus,
    JobApplication,
)


class AccountantRecruitmentViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()

        accountant_group = Group.objects.create(
            name="Accountant"
        )

        manager_group = Group.objects.create(
            name="Manager"
        )

        cls.accountant = (
            user_model.objects.create_user(
                username="recruitment-accountant",
                password="test-password-123",
            )
        )

        cls.accountant.groups.add(
            accountant_group
        )

        cls.manager = (
            user_model.objects.create_user(
                username="recruitment-manager",
                password="test-password-123",
            )
        )

        cls.manager.groups.add(
            manager_group
        )

        cls.application = (
            JobApplication.objects.create(
                first_name="Test",
                last_name="Candidate",
                birth_date="1995-01-10",
                marital_status="MARRIED",
                children_count=2,
                phone="+213660000001",
                wilaya="Constantine",
                residence="Ali Mendjeli",
                requested_position=(
                    "DRIVER_SELLER"
                ),
                experience_years=4,
                has_driving_license=True,
                driving_license_category="B",
                driving_experience_years=4,
            )
        )

    def login_accountant(self):
        self.client.force_login(
            self.accountant
        )

    def test_accountant_can_open_application_list(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "recruitment_accountant:list"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "Test Candidate",
        )

    def test_accountant_can_open_application_detail(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "recruitment_accountant:detail",
                args=[
                    self.application.pk
                ],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "+213660000001",
        )

    def test_manager_cannot_access_recruitment_area(self):
        self.client.force_login(
            self.manager
        )

        response = self.client.get(
            reverse(
                "recruitment_accountant:list"
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(
            reverse(
                "recruitment_accountant:list"
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_accountant_can_update_application_status(self):
        self.login_accountant()

        response = self.client.post(
            reverse(
                "recruitment_accountant:update_status",
                args=[
                    self.application.pk
                ],
            ),
            {
                "status": (
                    ApplicationStatus.REVIEWING
                )
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.application.refresh_from_db()

        self.assertEqual(
            self.application.status,
            ApplicationStatus.REVIEWING,
        )

        self.assertEqual(
            self.application.status_updated_by,
            self.accountant,
        )

    def test_status_endpoint_rejects_get(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "recruitment_accountant:update_status",
                args=[
                    self.application.pk
                ],
            )
        )

        self.assertEqual(
            response.status_code,
            405,
        )

    def test_accountant_home_shows_new_application_count(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "imports:accountant_home"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "طلبات التوظيف",
        )

        self.assertContains(
            response,
            "طلبات جديدة",
        )


class RecruitmentCvSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()

        accountant_group, _ = Group.objects.get_or_create(
            name="Accountant"
        )

        manager_group, _ = Group.objects.get_or_create(
            name="Manager"
        )

        cls.accountant = user_model.objects.create_user(
            username="cv-security-accountant",
            password="test-password-123",
        )
        cls.accountant.groups.add(
            accountant_group
        )

        cls.manager = user_model.objects.create_user(
            username="cv-security-manager",
            password="test-password-123",
        )
        cls.manager.groups.add(
            manager_group
        )

        cls.application = JobApplication.objects.create(
            first_name="CV",
            last_name="Security",
            birth_date="1995-01-10",
            marital_status="SINGLE",
            children_count=0,
            phone="+213660000099",
            wilaya="Constantine",
            residence="Constantine",
            requested_position="SELLER",
            experience_years=2,
        )

    def test_anonymous_user_cannot_download_cv(self):
        response = self.client.get(
            reverse(
                "recruitment_accountant:download_cv",
                args=[self.application.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_manager_cannot_download_cv(self):
        self.client.force_login(
            self.manager
        )

        response = self.client.get(
            reverse(
                "recruitment_accountant:download_cv",
                args=[self.application.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_accountant_gets_404_when_cv_is_missing(self):
        self.client.force_login(
            self.accountant
        )

        response = self.client.get(
            reverse(
                "recruitment_accountant:download_cv",
                args=[self.application.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )
