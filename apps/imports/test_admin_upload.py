from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from apps.imports.models import (
    DistributionBrand,
    ImportBatch,
    ImportBatchStatus,
    ImportRowStatus,
)


class ImportBatchAdminUploadTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.addCleanup(self.media_directory.cleanup)

        self.media_settings = self.settings(
            MEDIA_ROOT=self.media_directory.name,
        )
        self.media_settings.enable()
        self.addCleanup(self.media_settings.disable)

        self.user = get_user_model().objects.create_superuser(
            username="import-admin-test",
            email="import-admin@example.com",
            password="test-password",
        )
        self.client.force_login(self.user)

        DistributionBrand.objects.create(
            code="BIFA",
            name="BIFA",
            is_active=True,
        )

        self.add_url = reverse(
            "admin:imports_importbatch_add",
        )

    def make_excel_upload(self, *, filename, rows):
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

        for row in rows:
            worksheet.append(row)

        stream = BytesIO()
        workbook.save(stream)
        workbook.close()

        return SimpleUploadedFile(
            filename,
            stream.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            ),
        )

    def test_admin_upload_creates_reviewed_batch(self):
        uploaded = self.make_excel_upload(
            filename=(
                "Sales_BIFA_"
                "2026-03-07_2026-03-11.xlsx"
            ),
            rows=[
                [
                    "BIFA LIV01",
                    "07/03/2026 09:00:00",
                    "Client Test",
                    1250,
                    "MILA",
                ],
            ],
        )

        response = self.client.post(
            self.add_url,
            {
                "source_file": uploaded,
                "replaces_batch": "",
                "notes": "Uploaded from admin test.",
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ImportBatch.objects.count(), 1)

        batch = ImportBatch.objects.get()

        self.assertEqual(
            batch.status,
            ImportBatchStatus.REVIEWED,
        )
        self.assertEqual(batch.uploaded_by, self.user)
        self.assertEqual(batch.reviewed_by, self.user)
        self.assertEqual(
            batch.notes,
            "Uploaded from admin test.",
        )
        self.assertEqual(batch.total_rows, 1)
        self.assertEqual(batch.accepted_rows, 1)
        self.assertEqual(batch.rows.count(), 1)
        self.assertEqual(
            batch.rows.get().status,
            ImportRowStatus.ACCEPTED,
        )

    def test_admin_upload_creates_blocked_batch(self):
        uploaded = self.make_excel_upload(
            filename=(
                "Sales_BIFA_"
                "2026-03-07_2026-03-11.xlsx"
            ),
            rows=[
                [
                    "BIFA LIV01",
                    "06/03/2026 09:00:00",
                    "Client Outside Period",
                    1000,
                    "MILA",
                ],
            ],
        )

        response = self.client.post(
            self.add_url,
            {
                "source_file": uploaded,
                "replaces_batch": "",
                "notes": "",
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ImportBatch.objects.count(), 1)

        batch = ImportBatch.objects.get()

        self.assertEqual(
            batch.status,
            ImportBatchStatus.BLOCKED,
        )
        self.assertGreater(batch.error_count, 0)
        self.assertEqual(batch.rows.count(), 1)
        self.assertEqual(
            batch.rows.get().status,
            ImportRowStatus.EXCLUDED,
        )

    def test_admin_rejects_non_excel_extension(self):
        uploaded = SimpleUploadedFile(
            "Sales_BIFA_2026-03-07_2026-03-11.txt",
            b"not an excel file",
            content_type="text/plain",
        )

        response = self.client.post(
            self.add_url,
            {
                "source_file": uploaded,
                "replaces_batch": "",
                "notes": "",
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ImportBatch.objects.count(), 0)
        self.assertContains(response, "XLSX")
        self.assertContains(response, "XLSM")