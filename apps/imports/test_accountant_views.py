from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import (
    SimpleUploadedFile,
)
from django.test import TestCase
from django.urls import reverse

from .models import (
    DistributionBrand,
    ImportBatch,
    ImportBatchStatus,
    ImportReportType,
)
from .services.batch_approval import (
    ImportBatchApprovalError,
)
from .services.batch_review import (
    ImportBatchReviewError,
)


class AccountantImportViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()

        accountant_group = Group.objects.create(
            name="Accountant"
        )

        manager_group = Group.objects.create(
            name="Manager"
        )

        cls.accountant = user_model.objects.create_user(
            username="accountant-view",
            password="test-pass-123",
            is_active=True,
        )
        cls.accountant.groups.add(accountant_group)

        cls.manager = user_model.objects.create_user(
            username="manager-view",
            password="test-pass-123",
            is_active=True,
        )
        cls.manager.groups.add(manager_group)

        cls.superuser = user_model.objects.create_superuser(
            username="superuser-view",
            email="admin@example.com",
            password="test-pass-123",
        )

        cls.brand = DistributionBrand.objects.create(
            code="BIFA",
            name="BIFA",
        )

        cls.batch = ImportBatch.objects.create(
            brand=cls.brand,
            report_type=ImportReportType.SALES,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
            original_filename=(
                "Sales_BIFA_2026-07-01_"
                "2026-07-07.xlsx"
            ),
            worksheet_name="Sheet1",
            file_size_bytes=128,
            file_sha256="a" * 64,
            content_sha256="b" * 64,
            status=ImportBatchStatus.REVIEWED,
            total_rows=1,
            accepted_rows=1,
            excluded_rows=0,
            stopped_rows=0,
            warning_count=0,
            error_count=0,
            review_summary={
                "can_approve": True,
                "issue_groups": [],
            },
            uploaded_by=cls.accountant,
            reviewed_by=cls.accountant,
        )

    def login_accountant(self):
        self.client.force_login(
            self.accountant
        )

    def test_anonymous_home_redirects_to_login(self):
        response = self.client.get(
            reverse(
                "imports:accountant_home"
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_accountant_can_open_home(self):
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
            "\u0645\u0631\u0643\u0632 "
            "\u0627\u0633\u062a\u064a\u0631\u0627\u062f "
            "\u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a",
        )

    def test_superuser_can_open_home(self):
        self.client.force_login(
            self.superuser
        )

        response = self.client.get(
            reverse(
                "imports:accountant_home"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_manager_cannot_open_home(self):
        self.client.force_login(
            self.manager
        )

        response = self.client.get(
            reverse(
                "imports:accountant_home"
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_post_without_file_shows_form_error(self):
        self.login_accountant()

        response = self.client.post(
            reverse(
                "imports:accountant_home"
            ),
            data={},
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertTrue(
            response.context[
                "upload_form"
            ].errors
        )

    @patch(
        "apps.imports.views."
        "create_or_update_import_review"
    )
    def test_valid_upload_redirects_to_detail(
        self,
        review_mock,
    ):
        self.login_accountant()

        review_mock.return_value = SimpleNamespace(
            batch=self.batch,
            created=True,
        )

        source_file = SimpleUploadedFile(
            (
                "Sales_BIFA_2026-07-01_"
                "2026-07-07.xlsx"
            ),
            b"temporary-test-content",
            content_type=(
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            ),
        )

        response = self.client.post(
            reverse(
                "imports:accountant_home"
            ),
            data={
                "source_file": source_file,
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "imports:batch_detail",
                args=[self.batch.pk],
            ),
            fetch_redirect_response=False,
        )

        review_mock.assert_called_once()

        kwargs = review_mock.call_args.kwargs

        self.assertEqual(
            kwargs["uploaded_by"],
            self.accountant,
        )
        self.assertEqual(
            kwargs["reviewed_by"],
            self.accountant,
        )

    @patch(
        "apps.imports.views."
        "create_or_update_import_review"
    )
    def test_review_error_is_shown_in_form(
        self,
        review_mock,
    ):
        self.login_accountant()

        review_mock.side_effect = (
            ImportBatchReviewError(
                "preflight_failed",
                "Preflight failed.",
                details={
                    "errors": [
                        {
                            "stage": "filename",
                            "code": (
                                "invalid_filename_format"
                            ),
                            "message": "Invalid name.",
                            "details": {},
                        }
                    ]
                },
            )
        )

        source_file = SimpleUploadedFile(
            "invalid.xlsx",
            b"temporary-test-content",
        )

        response = self.client.post(
            reverse(
                "imports:accountant_home"
            ),
            data={
                "source_file": source_file,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertTrue(
            response.context[
                "upload_form"
            ].non_field_errors()
        )
        self.assertEqual(
            len(
                response.context[
                    "service_error_details"
                ]
            ),
            1,
        )

    def test_accountant_can_open_batch_detail(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "imports:batch_detail",
                args=[self.batch.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            response.context["batch"],
            self.batch,
        )
        self.assertTrue(
            response.context["can_approve"]
        )

    def test_manager_cannot_open_batch_detail(self):
        self.client.force_login(
            self.manager
        )

        response = self.client.get(
            reverse(
                "imports:batch_detail",
                args=[self.batch.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_approve_endpoint_rejects_get(self):
        self.login_accountant()

        response = self.client.get(
            reverse(
                "imports:approve_batch",
                args=[self.batch.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            405,
        )

    @patch(
        "apps.imports.views."
        "approve_import_batch"
    )
    def test_accountant_can_approve_batch(
        self,
        approve_mock,
    ):
        self.login_accountant()

        approve_mock.return_value = SimpleNamespace(
            batch=self.batch,
        )

        response = self.client.post(
            reverse(
                "imports:approve_batch",
                args=[self.batch.pk],
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "imports:batch_detail",
                args=[self.batch.pk],
            ),
            fetch_redirect_response=False,
        )

        approve_mock.assert_called_once_with(
            self.batch.pk,
            approved_by=self.accountant,
        )

    @patch(
        "apps.imports.views."
        "approve_import_batch"
    )
    def test_approval_error_redirects_safely(
        self,
        approve_mock,
    ):
        self.login_accountant()

        approve_mock.side_effect = (
            ImportBatchApprovalError(
                "batch_not_reviewed",
                "Not reviewed.",
            )
        )

        response = self.client.post(
            reverse(
                "imports:approve_batch",
                args=[self.batch.pk],
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "imports:batch_detail",
                args=[self.batch.pk],
            ),
            fetch_redirect_response=False,
        )
