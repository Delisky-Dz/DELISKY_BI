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
    SourceProductPackaging,
    SourceTruckMapping,
)
from apps.imports.services.raw_opening_stock_multi_review import (
    RawOpeningStockImportRequest,
    create_raw_opening_stock_multi_import_reviews,
)


CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument."
    "spreadsheetml.sheet"
)


class RawOpeningStockMultiReviewTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.addCleanup(
            self.media_directory.cleanup
        )

        self.media_settings = self.settings(
            MEDIA_ROOT=self.media_directory.name,
        )
        self.media_settings.enable()
        self.addCleanup(
            self.media_settings.disable
        )

        self.user = (
            get_user_model()
            .objects
            .create_user(
                username="raw-opening-multi",
                password="test-password",
            )
        )

        self.delisky = (
            DistributionBrand.objects.create(
                code="DELISKY",
                name="DELISKY",
                is_active=True,
            )
        )

        self.nita = (
            DistributionBrand.objects.create(
                code="NITA",
                name="NITA",
                is_active=True,
            )
        )

        self.delisky_truck = Truck.objects.create(
            internal_code="DELISKY LIV01",
            distribution_brand=self.delisky,
            registration_number="MULTI-DELISKY",
            brand="TEST",
            model="TEST",
        )

        self.nita_truck = Truck.objects.create(
            internal_code="NITA LIV01",
            distribution_brand=self.nita,
            registration_number="MULTI-NITA",
            brand="TEST",
            model="TEST",
        )

        self.source_system = (
            ImportSourceSystem.objects.create(
                code="AIO_WEB",
                name="AIO WEB",
                is_active=True,
            )
        )

        SourceTruckMapping.objects.create(
            source_system=self.source_system,
            source_code="VAN1-DELISKY",
            truck=self.delisky_truck,
            is_active=True,
        )

        SourceTruckMapping.objects.create(
            source_system=self.source_system,
            source_code="VAN1-NITA",
            truck=self.nita_truck,
            is_active=True,
        )

        SourceProductPackaging.objects.create(
            source_system=self.source_system,
            source_product_code="TEST-D",
            barcode="DEL-001",
            designation="ARTICLE D",
            units_per_carton=1,
            needs_review=False,
            is_active=True,
        )

        SourceProductPackaging.objects.create(
            source_system=self.source_system,
            source_product_code="TEST-N",
            barcode="NITA-001",
            designation="ARTICLE N",
            units_per_carton=1,
            needs_review=False,
            is_active=True,
        )

    def make_upload(
        self,
        *,
        quantity,
        article,
        barcode,
        filename,
    ):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Classeur"

        worksheet.append(
            [
                "Barcode",
                "Qté",
                "Colisage",
                "العلبة",
                "Désignation",
            ]
        )

        worksheet.append(
            [
                barcode,
                quantity,
                1,
                quantity,
                article,
            ]
        )

        output = BytesIO()
        workbook.save(output)
        workbook.close()

        return SimpleUploadedFile(
            filename,
            output.getvalue(),
            content_type=CONTENT_TYPE,
        )

    def test_processes_multiple_valid_files(
        self,
    ):
        delisky_filename = (
            "VAN1-DELISKY opning stock.xlsx"
        )
        nita_filename = (
            "VAN1-NITA opning stock.xlsx"
        )

        result = (
            create_raw_opening_stock_multi_import_reviews(
                (
                    RawOpeningStockImportRequest(
                        source=self.make_upload(
                            quantity=10,
                            article="ARTICLE D",
                            barcode="DEL-001",
                            filename=delisky_filename,
                        ),
                        source_system_code="AIO_WEB",
                        stock_date="2026-08-01",
                        original_filename=delisky_filename,
                    ),
                    RawOpeningStockImportRequest(
                        source=self.make_upload(
                            quantity=20,
                            article="ARTICLE N",
                            barcode="NITA-001",
                            filename=nita_filename,
                        ),
                        source_system_code="AIO_WEB",
                        stock_date="2026-08-01",
                        original_filename=nita_filename,
                    ),
                ),
                uploaded_by=self.user,
                reviewed_by=self.user,
            )
        )

        self.assertEqual(
            result.succeeded_count,
            2,
        )
        self.assertEqual(
            result.failed_count,
            0,
        )
        self.assertEqual(
            ImportSourceUpload.objects.count(),
            2,
        )
        self.assertEqual(
            ImportBatch.objects.count(),
            2,
        )

        brands = {
            batch.brand.code
            for item in result.files
            for batch in item.batches
        }

        self.assertEqual(
            brands,
            {"DELISKY", "NITA"},
        )

        total_units = {
            batch.brand.code:
                batch.rows.get()
                .cleaned_data["total_units"]
            for item in result.files
            for batch in item.batches
        }

        self.assertEqual(
            total_units["DELISKY"],
            10,
        )
        self.assertEqual(
            total_units["NITA"],
            20,
        )

    def test_bad_file_does_not_block_good_file(
        self,
    ):
        good_filename = (
            "VAN1-DELISKY opning stock.xlsx"
        )
        bad_filename = (
            "UNKNOWN opning stock.xlsx"
        )

        result = (
            create_raw_opening_stock_multi_import_reviews(
                (
                    RawOpeningStockImportRequest(
                        source=self.make_upload(
                            quantity=10,
                            article="ARTICLE D",
                            barcode="DEL-001",
                            filename=good_filename,
                        ),
                        source_system_code="AIO_WEB",
                        stock_date="2026-08-01",
                    ),
                    RawOpeningStockImportRequest(
                        source=self.make_upload(
                            quantity=20,
                            article="ARTICLE N",
                            barcode="NITA-001",
                            filename=bad_filename,
                        ),
                        source_system_code="AIO_WEB",
                        stock_date="2026-08-01",
                    ),
                ),
                uploaded_by=self.user,
            )
        )

        self.assertEqual(
            result.succeeded_count,
            1,
        )
        self.assertEqual(
            result.failed_count,
            1,
        )

        self.assertTrue(
            result.files[0].succeeded
        )
        self.assertFalse(
            result.files[1].succeeded
        )

        self.assertEqual(
            result.files[1].error_code,
            "row_adaptation_failed",
        )

        self.assertEqual(
            ImportSourceUpload.objects.count(),
            1,
        )
        self.assertEqual(
            ImportBatch.objects.count(),
            1,
        )

    def test_invalid_stock_date_is_file_failure(
        self,
    ):
        filename = (
            "VAN1-DELISKY opning stock.xlsx"
        )

        result = (
            create_raw_opening_stock_multi_import_reviews(
                (
                    RawOpeningStockImportRequest(
                        source=self.make_upload(
                            quantity=10,
                            article="ARTICLE D",
                            barcode="DEL-001",
                            filename=filename,
                        ),
                        source_system_code="AIO_WEB",
                        stock_date="2026-02-30",
                    ),
                ),
                uploaded_by=self.user,
            )
        )

        self.assertEqual(
            result.succeeded_count,
            0,
        )
        self.assertEqual(
            result.failed_count,
            1,
        )
        self.assertEqual(
            result.files[0].error_code,
            "invalid_stock_date",
        )
        self.assertEqual(
            ImportSourceUpload.objects.count(),
            0,
        )
        self.assertEqual(
            ImportBatch.objects.count(),
            0,
        )