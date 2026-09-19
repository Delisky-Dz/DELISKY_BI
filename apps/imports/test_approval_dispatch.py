from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.imports.models import (
    DistributionBrand,
    ImportBatch,
    ImportBatchStatus,
    ImportSourceSystem,
    ImportSourceUpload,
)
from apps.imports.services.approval_dispatch import (
    approve_reviewed_batch,
    is_items_detail_batch,
)


class ApprovalDispatchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="approval-dispatch-user",
            password="test",
        )
        cls.brand = DistributionBrand.objects.create(
            code="BIFA",
            name="BIFA",
        )
        cls.source_system = ImportSourceSystem.objects.create(
            code="BIFA_MILA",
            name="BIFA Mila",
        )
        cls.source_upload = ImportSourceUpload.objects.create(
            source_system=cls.source_system,
            original_filename="detail.xlsx",
            file_size_bytes=1,
            file_sha256="a" * 64,
            uploaded_by=cls.user,
        )

    def _batch(
        self,
        *,
        detail=False,
        source_upload=None,
        filename="batch.xlsx",
    ):
        return ImportBatch.objects.create(
            source_upload=source_upload,
            brand=self.brand,
            report_type="ITEMS",
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
            original_filename=filename,
            file_sha256=(
                ""
                if source_upload is not None
                else "b" * 64
            ),
            content_sha256="c" * 64,
            status=ImportBatchStatus.REVIEWED,
            total_rows=0,
            accepted_rows=0,
            excluded_rows=0,
            stopped_rows=0,
            uploaded_by=self.user,
            reviewed_by=self.user,
            review_summary=(
                {
                    "items_detail": {
                        "transaction_level": True,
                        "covered_trucks": [
                            "BIFA LIV03",
                        ],
                        "replacement_batch_ids": [],
                    }
                }
                if detail
                else {}
            ),
        )

    @patch(
        "apps.imports.services.approval_dispatch."
        "approve_items_detail_batch"
    )
    @patch(
        "apps.imports.services.approval_dispatch."
        "approve_import_batch"
    )
    def test_detail_batch_uses_detail_approval(
        self,
        legacy_approval,
        detail_approval,
    ):
        batch = self._batch(
            detail=True,
            source_upload=self.source_upload,
        )
        expected = SimpleNamespace(batch=batch)
        detail_approval.return_value = expected

        result = approve_reviewed_batch(
            batch.pk,
            approved_by=self.user,
        )

        self.assertIs(result, expected)
        detail_approval.assert_called_once_with(
            batch.pk,
            approved_by=self.user,
        )
        legacy_approval.assert_not_called()
        self.assertTrue(
            is_items_detail_batch(batch)
        )

    @patch(
        "apps.imports.services.approval_dispatch."
        "approve_items_detail_batch"
    )
    @patch(
        "apps.imports.services.approval_dispatch."
        "approve_import_batch"
    )
    def test_legacy_batch_keeps_legacy_approval(
        self,
        legacy_approval,
        detail_approval,
    ):
        batch = self._batch(
            detail=False,
            source_upload=self.source_upload,
            filename="legacy-source-backed.xlsx",
        )
        expected = SimpleNamespace(batch=batch)
        legacy_approval.return_value = expected

        result = approve_reviewed_batch(
            batch,
            approved_by=self.user,
        )

        self.assertIs(result, expected)
        legacy_approval.assert_called_once_with(
            batch.pk,
            approved_by=self.user,
        )
        detail_approval.assert_not_called()
        self.assertFalse(
            is_items_detail_batch(batch)
        )
