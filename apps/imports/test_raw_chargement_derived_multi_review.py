from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook

from apps.fleet.models import Truck
from apps.imports.models import (
    DistributionBrand,
    ImportBatch,
    ImportSourceSystem,
    ImportSourceUpload,
    SourceTruckMapping,
)
from apps.imports.services.raw_chargement_derived_multi_review import (
    RawChargementDerivedImportRequest,
    create_raw_chargement_derived_multi_import_reviews,
)


class RawChargementDerivedMultiReviewTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.addCleanup(self.media_directory.cleanup)

        self.media_settings = self.settings(
            MEDIA_ROOT=self.media_directory.name,
        )
        self.media_settings.enable()
        self.addCleanup(self.media_settings.disable)

        self.user = get_user_model().objects.create_user(
            username="raw-derived-multi-reviewer",
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

        delisky_truck = Truck.objects.create(
            internal_code="DELISKY LIV01",
            distribution_brand=self.delisky,
            registration_number="MULTI-DERIVED-D-01",
            brand="TEST BRAND",
            model="TEST MODEL",
        )

        nita_truck = Truck.objects.create(
            internal_code="NITA LIV01",
            distribution_brand=self.nita,
            registration_number="MULTI-DERIVED-N-01",
            brand="TEST BRAND",
            model="TEST MODEL",
        )

        self.source_system = ImportSourceSystem.objects.create(
            code="AIO_WEB",
            name="AIO-WEB",
            is_active=True,
        )

        SourceTruckMapping.objects.create(
            source_system=self.source_system,
            source_code="VAN1-DELISKY",
            truck=delisky_truck,
            is_active=True,
        )

        SourceTruckMapping.objects.create(
            source_system=self.source_system,
            source_code="VAN1-NITA",
            truck=nita_truck,
            is_active=True,
        )

    def make_upload(self, filename, rows):
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

    def test_failed_file_does_not_rollback_successful_mixed_file(self):
        mixed_upload = self.make_upload(
            "mixed_valid.xlsx",
            [
                [
                    "VAN1-DELISKY",
                    10,
                    "ARTICLE DELISKY",
                ],
                [
                    "VAN1-NITA",
                    20,
                    "ARTICLE NITA",
                ],
            ],
        )

        invalid_upload = self.make_upload(
            "unknown_truck.xlsx",
            [
                [
                    "VAN-UNKNOWN",
                    30,
                    "ARTICLE UNKNOWN",
                ],
            ],
        )

        result = create_raw_chargement_derived_multi_import_reviews(
            (
                RawChargementDerivedImportRequest(
                    source=mixed_upload,
                    source_system_code="AIO_WEB",
                    period_start="2026-08-01",
                    period_end="2026-08-17",
                    original_filename="mixed_valid.xlsx",
                ),
                RawChargementDerivedImportRequest(
                    source=invalid_upload,
                    source_system_code="AIO_WEB",
                    period_start="2026-08-01",
                    period_end="2026-08-17",
                    original_filename="unknown_truck.xlsx",
                ),
            ),
            uploaded_by=self.user,
            reviewed_by=self.user,
        )

        self.assertEqual(
            result.succeeded_count,
            1,
        )
        self.assertEqual(
            result.failed_count,
            1,
        )
        self.assertEqual(
            len(result.files),
            2,
        )

        first = result.files[0]
        second = result.files[1]

        self.assertTrue(first.succeeded)
        self.assertFalse(second.succeeded)

        self.assertEqual(
            first.original_filename,
            "mixed_valid.xlsx",
        )
        self.assertEqual(
            second.original_filename,
            "unknown_truck.xlsx",
        )

        self.assertEqual(
            len(first.batches),
            2,
        )
        self.assertEqual(
            {
                batch.brand.code
                for batch in first.batches
            },
            {"DELISKY", "NITA"},
        )

        self.assertEqual(
            second.batches,
            (),
        )
        self.assertIsNotNone(
            second.error_code,
        )
        self.assertIsNotNone(
            second.error_message,
        )

        self.assertEqual(
            ImportSourceUpload.objects.count(),
            1,
        )
        self.assertEqual(
            ImportBatch.objects.count(),
            2,
        )
