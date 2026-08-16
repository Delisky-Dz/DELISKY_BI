from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook

from apps.fleet.models import Truck
from apps.imports.models import DistributionBrand, ImportBatch
from apps.imports.services.raw_chargement_review import (
    RawChargementImportReviewError,
    create_raw_chargement_import_review,
)


class RawChargementImportReviewTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.addCleanup(self.media_directory.cleanup)

        self.media_settings = self.settings(
            MEDIA_ROOT=self.media_directory.name,
        )
        self.media_settings.enable()
        self.addCleanup(self.media_settings.disable)

        self.user = get_user_model().objects.create_user(
            username="raw-chargement-reviewer",
            password="test-password",
        )

        self.delisky = DistributionBrand.objects.create(
            code="DELISKY",
            name="DELISKY",
            is_active=True,
        )
        self.nita = DistributionBrand.objects.create(
            code="NITA",
            name="NITA",
            is_active=True,
        )

        Truck.objects.create(
            internal_code="DELISKY LIV01",
            distribution_brand=self.delisky,
            registration_number="REG-DELISKY-01",
            brand="TEST BRAND",
            model="TEST MODEL",
        )

        Truck.objects.create(
            internal_code="NITA LIV01",
            distribution_brand=self.nita,
            registration_number="REG-NITA-01",
            brand="TEST BRAND",
            model="TEST MODEL",
        )

    def make_mixed_upload(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Transferts"

        worksheet.append(
            [
                "Vers l'emplacement",
                "Qt\u00e9",
                "Article",
            ]
        )

        worksheet.append(
            [
                "SOURCE DELISKY",
                10,
                "ARTICLE A",
            ]
        )

        worksheet.append(
            [
                "SOURCE NITA",
                20,
                "ARTICLE B",
            ]
        )

        output = BytesIO()
        workbook.save(output)
        workbook.close()

        return SimpleUploadedFile(
            "chargement_mixed.xlsx",
            output.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

    def make_delisky_upload(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Transferts"

        worksheet.append(
            [
                "Vers l'emplacement",
                "Qt\u00e9",
                "Article",
            ]
        )

        worksheet.append(
            [
                "SOURCE DELISKY",
                10,
                "ARTICLE A",
            ]
        )

        worksheet.append(
            [
                "SOURCE DELISKY",
                20,
                "ARTICLE B",
            ]
        )

        output = BytesIO()
        workbook.save(output)
        workbook.close()

        return SimpleUploadedFile(
            "chargement_delisky.xlsx",
            output.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

    def test_creates_real_batch_and_import_rows_for_valid_raw_file(self):
        result = create_raw_chargement_import_review(
            self.make_delisky_upload(),
            uploaded_by=self.user,
            brand_code="DELISKY",
            period_start="2026-03-07",
            period_end="2026-03-11",
            truck_mapping={
                "SOURCE DELISKY": "DELISKY LIV01",
            },
        )

        self.assertTrue(result.created)
        self.assertEqual(
            ImportBatch.objects.count(),
            1,
        )

        batch = result.batch
        batch.refresh_from_db()

        self.assertEqual(
            batch.brand,
            self.delisky,
        )
        self.assertEqual(
            batch.report_type,
            "CHARGEMENT",
        )
        self.assertEqual(
            batch.period_start.isoformat(),
            "2026-03-07",
        )
        self.assertEqual(
            batch.period_end.isoformat(),
            "2026-03-11",
        )
        self.assertEqual(
            batch.original_filename,
            "chargement_delisky.xlsx",
        )
        self.assertEqual(
            batch.worksheet_name,
            "Transferts",
        )
        self.assertEqual(
            batch.status,
            "REVIEWED",
        )

        self.assertEqual(batch.total_rows, 2)
        self.assertEqual(batch.accepted_rows, 2)
        self.assertEqual(batch.excluded_rows, 0)
        self.assertEqual(batch.stopped_rows, 0)
        self.assertEqual(batch.warning_count, 0)
        self.assertEqual(batch.error_count, 0)

        self.assertEqual(
            len(batch.file_sha256),
            64,
        )
        self.assertEqual(
            len(batch.content_sha256),
            64,
        )

        self.assertTrue(
            batch.source_file.name
        )
        self.assertTrue(
            batch.source_file.storage.exists(
                batch.source_file.name
            )
        )

        rows = list(batch.rows.all())

        self.assertEqual(
            len(rows),
            2,
        )
        self.assertEqual(
            [
                row.excel_row_number
                for row in rows
            ],
            [2, 3],
        )
        self.assertEqual(
            [
                row.status
                for row in rows
            ],
            [
                "ACCEPTED",
                "ACCEPTED",
            ],
        )

        self.assertEqual(
            rows[0].raw_data,
            {
                "VAN": "DELISKY LIV01",
                "Qt\u00e9": 10,
                "Article": "ARTICLE A",
            },
        )
        self.assertEqual(
            rows[1].raw_data,
            {
                "VAN": "DELISKY LIV01",
                "Qt\u00e9": 20,
                "Article": "ARTICLE B",
            },
        )

        self.assertEqual(
            len(rows[0].row_sha256),
            64,
        )
        self.assertEqual(
            len(rows[1].row_sha256),
            64,
        )

        self.assertEqual(
            batch.review_summary[
                "recommended_status"
            ],
            "REVIEWED",
        )
        self.assertTrue(
            batch.review_summary[
                "can_approve"
            ]
        )

    def test_rejects_unknown_selected_brand_before_creating_batch(self):
        with self.assertRaises(
            RawChargementImportReviewError
        ) as context:
            create_raw_chargement_import_review(
                self.make_delisky_upload(),
                uploaded_by=self.user,
                brand_code="UNKNOWN",
                period_start="2026-03-07",
                period_end="2026-03-11",
                truck_mapping={
                    "SOURCE DELISKY": "DELISKY LIV01",
                },
            )

        self.assertEqual(
            context.exception.code,
            "unknown_brand",
        )

        self.assertEqual(
            ImportBatch.objects.count(),
            0,
        )

    def test_rejects_invalid_period_range_before_creating_batch(self):
        with self.assertRaises(
            RawChargementImportReviewError
        ) as context:
            create_raw_chargement_import_review(
                self.make_delisky_upload(),
                uploaded_by=self.user,
                brand_code="DELISKY",
                period_start="2026-03-11",
                period_end="2026-03-07",
                truck_mapping={
                    "SOURCE DELISKY": "DELISKY LIV01",
                },
            )

        self.assertEqual(
            context.exception.code,
            "invalid_period_range",
        )

        self.assertEqual(
            ImportBatch.objects.count(),
            0,
        )

    def test_rejects_mixed_brand_file_before_creating_batch(self):
        with self.assertRaises(
            RawChargementImportReviewError
        ) as context:
            create_raw_chargement_import_review(
                self.make_mixed_upload(),
                uploaded_by=self.user,
                brand_code="DELISKY",
                period_start="2026-03-07",
                period_end="2026-03-11",
                truck_mapping={
                    "SOURCE DELISKY": "DELISKY LIV01",
                    "SOURCE NITA": "NITA LIV01",
                },
            )

        self.assertEqual(
            context.exception.code,
            "brand_validation_failed",
        )

        issues = context.exception.details["issues"]

        self.assertEqual(len(issues), 1)
        self.assertEqual(
            issues[0]["code"],
            "brand_mismatch",
        )
        self.assertEqual(
            issues[0]["excel_row_number"],
            3,
        )
        self.assertEqual(
            issues[0]["actual_brand_code"],
            "NITA",
        )
        self.assertEqual(
            issues[0]["expected_brand_code"],
            "DELISKY",
        )

        self.assertEqual(
            ImportBatch.objects.count(),
            0,
        )
