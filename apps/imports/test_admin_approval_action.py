from datetime import date
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase

from apps.imports.admin import ImportBatchAdmin
from apps.imports.models import (
    DistributionBrand,
    ImportBatch,
    ImportBatchStatus,
)
from apps.imports.services import ImportBatchApprovalError


class ImportBatchAdminApprovalActionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="approval-action-admin",
            email="approval-action@example.com",
            password="test-password",
        )

        self.brand = DistributionBrand.objects.create(
            code="ACTIONTEST",
            name="Action Test",
            is_active=True,
        )

        self.batch = ImportBatch.objects.create(
            brand=self.brand,
            report_type="SALES",
            period_start=date(2026, 3, 7),
            period_end=date(2026, 3, 11),
            original_filename=(
                "Sales_ACTIONTEST_"
                "2026-03-07_2026-03-11.xlsx"
            ),
            file_size_bytes=100,
            file_sha256="a" * 64,
            content_sha256="b" * 64,
            status=ImportBatchStatus.REVIEWED,
            total_rows=0,
            accepted_rows=0,
            excluded_rows=0,
            stopped_rows=0,
            warning_count=0,
            error_count=0,
            review_summary={},
            uploaded_by=self.user,
            reviewed_by=self.user,
        )

        self.factory = RequestFactory()
        self.model_admin = ImportBatchAdmin(
            ImportBatch,
            admin.site,
        )

    def make_request(self):
        request = self.factory.post("/")
        request.user = self.user

        middleware = SessionMiddleware(
            lambda current_request: None
        )
        middleware.process_request(request)
        request.session.save()

        request._messages = FallbackStorage(request)

        return request

    @patch("apps.imports.admin.approve_import_batch")
    def test_action_calls_approval_service(
        self,
        mocked_approval,
    ):
        request = self.make_request()
        queryset = ImportBatch.objects.filter(
            pk=self.batch.pk,
        )

        self.model_admin.approve_selected_batches(
            request,
            queryset,
        )

        mocked_approval.assert_called_once()

        args, kwargs = mocked_approval.call_args

        self.assertEqual(args[0].pk, self.batch.pk)
        self.assertEqual(
            kwargs["approved_by"],
            self.user,
        )

    @patch(
        "apps.imports.admin.approve_import_batch",
        side_effect=ImportBatchApprovalError(
            "test_error",
            "Approval failed",
        ),
    )
    def test_action_handles_approval_error(
        self,
        mocked_approval,
    ):
        request = self.make_request()
        queryset = ImportBatch.objects.filter(
            pk=self.batch.pk,
        )

        self.model_admin.approve_selected_batches(
            request,
            queryset,
        )

        mocked_approval.assert_called_once()

        message_texts = [
            str(message)
            for message in get_messages(request)
        ]

        self.assertTrue(
            any(
                "Approval failed" in message
                for message in message_texts
            )
        )