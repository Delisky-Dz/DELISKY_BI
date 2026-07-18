from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings
from openpyxl import Workbook

from apps.imports.models import (
    DistributionBrand,
    ImportBatchStatus,
)
from apps.imports.services import (
    ImportBatchApprovalError,
    approve_import_batch,
    create_or_update_import_review,
)


class ImportBatchApprovalTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.media_override = override_settings(
            MEDIA_ROOT=self.media_directory.name,
        )
        self.media_override.enable()

        self.user = get_user_model().objects.create_user(
            username="approval-user",
            password="test-password",
            is_active=True,
        )

        self.brand = DistributionBrand.objects.create(
            code="BIFA",
            name="BIFA",
            is_active=True,
        )

    def tearDown(self):
        self.media_override.disable()
        self.media_directory.cleanup()
        super().tearDown()

    def make_upload(
        self,
        *,
        filename=(
            "Sales_BIFA_"
            "2026-03-07_2026-03-11.xlsx"
        ),
        rows=None,
    ):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Sales"

        worksheet.append([
            "VAN",
            "Date&Heure",
            "Nom du client",
            "Total",
            "Region",
        ])

        for row in rows or [
            [
                "BIFA LIV01",
                "07/03/2026 09:00:00",
                "Client Test",
                1000,
                "MILA",
            ],
        ]:
            worksheet.append(row)

        stream = BytesIO()
        workbook.save(stream)
        workbook.close()

        from django.core.files.uploadedfile import (
            SimpleUploadedFile,
        )

        return SimpleUploadedFile(
            filename,
            stream.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            ),
        )

    def review_batch(
        self,
        *,
        filename=(
            "Sales_BIFA_"
            "2026-03-07_2026-03-11.xlsx"
        ),
        rows=None,
    ):
        result = create_or_update_import_review(
            self.make_upload(
                filename=filename,
                rows=rows,
            ),
            uploaded_by=self.user,
        )

        return result.batch

    def test_approves_reviewed_batch_and_deletes_file(self):
        batch = self.review_batch()
        source_name = batch.source_file.name
        storage = batch.source_file.storage

        self.assertEqual(
            batch.status,
            ImportBatchStatus.REVIEWED,
        )
        self.assertTrue(storage.exists(source_name))
        self.assertEqual(batch.rows.count(), 1)

        result = approve_import_batch(
            batch,
            approved_by=self.user,
        )

        batch.refresh_from_db()

        self.assertEqual(
            batch.status,
            ImportBatchStatus.APPROVED,
        )
        self.assertEqual(batch.approved_by, self.user)
        self.assertIsNotNone(batch.approved_at)
        self.assertEqual(batch.source_file.name, "")
        self.assertFalse(storage.exists(source_name))
        self.assertEqual(batch.rows.count(), 1)
        self.assertEqual(
            result.deleted_source_filename,
            source_name,
        )

    def test_rejects_blocked_batch_and_keeps_file(self):
        batch = self.review_batch(
            rows=[
                [
                    "BIFA LIV01",
                    "06/03/2026 09:00:00",
                    "Client Outside",
                    1000,
                    "MILA",
                ],
            ],
        )

        source_name = batch.source_file.name
        storage = batch.source_file.storage

        self.assertEqual(
            batch.status,
            ImportBatchStatus.BLOCKED,
        )

        with self.assertRaises(
            ImportBatchApprovalError,
        ) as context:
            approve_import_batch(
                batch,
                approved_by=self.user,
            )

        self.assertEqual(
            context.exception.code,
            "batch_not_reviewed",
        )

        batch.refresh_from_db()

        self.assertEqual(
            batch.status,
            ImportBatchStatus.BLOCKED,
        )
        self.assertTrue(storage.exists(source_name))

    def test_rejects_duplicate_approved_content(self):
        first_batch = self.review_batch()

        approve_import_batch(
            first_batch,
            approved_by=self.user,
        )

        second_batch = self.review_batch()
        second_source_name = (
            second_batch.source_file.name
        )
        second_storage = (
            second_batch.source_file.storage
        )

        with self.assertRaises(
            ImportBatchApprovalError,
        ) as context:
            approve_import_batch(
                second_batch,
                approved_by=self.user,
            )

        self.assertIn(
            context.exception.code,
            {
                "invalid_approval",
                "approval_conflict",
            },
        )

        first_batch.refresh_from_db()
        second_batch.refresh_from_db()

        self.assertEqual(
            first_batch.status,
            ImportBatchStatus.APPROVED,
        )
        self.assertEqual(
            second_batch.status,
            ImportBatchStatus.REVIEWED,
        )
        self.assertTrue(
            second_storage.exists(
                second_source_name,
            )
        )

    def test_replacement_supersedes_old_batch(self):
        old_batch = self.review_batch()

        approve_import_batch(
            old_batch,
            approved_by=self.user,
        )

        new_batch = self.review_batch(
            rows=[
                [
                    "BIFA LIV02",
                    "08/03/2026 10:00:00",
                    "Replacement Client",
                    2500,
                    "MILA",
                ],
            ],
        )

        new_batch.replaces_batch = old_batch
        new_batch.save(
            update_fields=[
                "replaces_batch",
                "updated_at",
            ]
        )

        result = approve_import_batch(
            new_batch,
            approved_by=self.user,
        )

        old_batch.refresh_from_db()
        new_batch.refresh_from_db()

        self.assertEqual(
            old_batch.status,
            ImportBatchStatus.SUPERSEDED,
        )
        self.assertEqual(
            new_batch.status,
            ImportBatchStatus.APPROVED,
        )
        self.assertEqual(
            result.superseded_batch_id,
            old_batch.pk,
        )

    def test_rejects_replacement_scope_mismatch(self):
        old_batch = self.review_batch()

        approve_import_batch(
            old_batch,
            approved_by=self.user,
        )

        new_batch = self.review_batch(
            filename=(
                "Sales_BIFA_"
                "2026-03-12_2026-03-13.xlsx"
            ),
            rows=[
                [
                    "BIFA LIV02",
                    "12/03/2026 10:00:00",
                    "Different Period",
                    2500,
                    "MILA",
                ],
            ],
        )

        new_batch.replaces_batch = old_batch
        new_batch.save(
            update_fields=[
                "replaces_batch",
                "updated_at",
            ]
        )

        with self.assertRaises(
            ImportBatchApprovalError,
        ) as context:
            approve_import_batch(
                new_batch,
                approved_by=self.user,
            )

        self.assertEqual(
            context.exception.code,
            "replacement_scope_mismatch",
        )

        old_batch.refresh_from_db()
        new_batch.refresh_from_db()

        self.assertEqual(
            old_batch.status,
            ImportBatchStatus.APPROVED,
        )
        self.assertEqual(
            new_batch.status,
            ImportBatchStatus.REVIEWED,
        )

    def test_rejects_staged_row_count_mismatch(self):
        batch = self.review_batch()

        batch.total_rows += 1
        batch.save(
            update_fields=[
                "total_rows",
                "updated_at",
            ]
        )

        with self.assertRaises(
            ImportBatchApprovalError,
        ) as context:
            approve_import_batch(
                batch,
                approved_by=self.user,
            )

        self.assertEqual(
            context.exception.code,
            "row_count_mismatch",
        )

        batch.refresh_from_db()

        self.assertEqual(
            batch.status,
            ImportBatchStatus.REVIEWED,
        )

    def test_rejects_inactive_approver(self):
        batch = self.review_batch()

        inactive_user = (
            get_user_model().objects.create_user(
                username="inactive-approver",
                password="test-password",
                is_active=False,
            )
        )

        with self.assertRaises(
            ImportBatchApprovalError,
        ) as context:
            approve_import_batch(
                batch,
                approved_by=inactive_user,
            )

        self.assertEqual(
            context.exception.code,
            "inactive_approver",
        )

        batch.refresh_from_db()

        self.assertEqual(
            batch.status,
            ImportBatchStatus.REVIEWED,
        )

    def test_rejects_second_approval(self):
        batch = self.review_batch()

        approve_import_batch(
            batch,
            approved_by=self.user,
        )

        with self.assertRaises(
            ImportBatchApprovalError,
        ) as context:
            approve_import_batch(
                batch,
                approved_by=self.user,
            )

        self.assertEqual(
            context.exception.code,
            "already_approved",
        )
