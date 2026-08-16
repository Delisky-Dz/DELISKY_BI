from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook

from apps.fleet.models import Truck
from apps.imports.models import DistributionBrand, ImportBatch
from apps.imports.services.raw_chargement_multi_review import (
    RawChargementImportRequest,
    create_raw_chargement_multi_import_reviews,
)


class RawChargementMultiReviewTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.addCleanup(self.media_directory.cleanup)

        self.media_settings = self.settings(
            MEDIA_ROOT=self.media_directory.name,
        )
        self.media_settings.enable()
        self.addCleanup(self.media_settings.disable)

        self.user = get_user_model().objects.create_user(
            username="raw-multi-reviewer",
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
            registration_number="MULTI-DELISKY-01",
            brand="TEST BRAND",
            model="TEST MODEL",
        )

        Truck.objects.create(
            internal_code="NITA LIV01",
            distribution_brand=self.nita,
            registration_number="MULTI-NITA-01",
            brand="TEST BRAND",
            model="TEST MODEL",
        )

    def make_upload(
        self,
        *,
        filename,
        rows,
    ):
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

        for row in rows:
            worksheet.append(row)

        output = BytesIO()
        workbook.save(output)
        workbook.close()

        return SimpleUploadedFile(
            filename,
            output.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

    def test_one_failed_file_does_not_rollback_successful_file(self):
        valid_upload = self.make_upload(
            filename="valid_delisky.xlsx",
            rows=[
                [
                    "SOURCE DELISKY",
                    10,
                    "ARTICLE A",
                ],
            ],
        )

        mixed_upload = self.make_upload(
            filename="mixed_file.xlsx",
            rows=[
                [
                    "SOURCE DELISKY",
                    20,
                    "ARTICLE B",
                ],
                [
                    "SOURCE NITA",
                    30,
                    "ARTICLE C",
                ],
            ],
        )

        result = create_raw_chargement_multi_import_reviews(
            (
                RawChargementImportRequest(
                    source=valid_upload,
                    brand_code="DELISKY",
                    period_start="2026-03-07",
                    period_end="2026-03-11",
                    truck_mapping={
                        "SOURCE DELISKY": "DELISKY LIV01",
                    },
                ),
                RawChargementImportRequest(
                    source=mixed_upload,
                    brand_code="DELISKY",
                    period_start="2026-03-07",
                    period_end="2026-03-11",
                    truck_mapping={
                        "SOURCE DELISKY": "DELISKY LIV01",
                        "SOURCE NITA": "NITA LIV01",
                    },
                ),
            ),
            uploaded_by=self.user,
        )

        self.assertEqual(
            len(result.files),
            2,
        )

        self.assertTrue(
            result.files[0].succeeded
        )
        self.assertFalse(
            result.files[1].succeeded
        )

        self.assertIsNotNone(
            result.files[0].batch
        )
        self.assertIsNone(
            result.files[1].batch
        )

        self.assertEqual(
            result.files[1].error_code,
            "brand_validation_failed",
        )

        self.assertEqual(
            ImportBatch.objects.count(),
            1,
        )

        batch = ImportBatch.objects.get()

        self.assertEqual(
            batch.original_filename,
            "valid_delisky.xlsx",
        )
        self.assertEqual(
            batch.brand.code,
            "DELISKY",
        )
