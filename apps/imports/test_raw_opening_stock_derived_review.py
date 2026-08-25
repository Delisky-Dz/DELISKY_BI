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
from apps.imports.services.raw_opening_stock_derived_review import (
    create_raw_opening_stock_derived_import_reviews,
)
from apps.imports.services.raw_opening_stock_review import (
    RawOpeningStockImportReviewError,
)


CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument."
    "spreadsheetml.sheet"
)


class RawOpeningStockDerivedReviewTests(TestCase):
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
                username="raw-opening-derived",
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

        self.delisky_truck = Truck.objects.create(
            internal_code="DELISKY LIV01",
            distribution_brand=self.delisky,
            registration_number="OPEN-DELISKY-01",
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

        self.product = (
            SourceProductPackaging.objects.create(
                source_system=self.source_system,
                source_product_code="TEST-DELISKY",
                barcode="DEL-001",
                designation="ARTICLE DELISKY",
                units_per_carton=1,
                needs_review=False,
                is_active=True,
            )
        )

    def make_upload(
        self,
        *,
        quantity=10,
        filename="VAN1-DELISKY opning stock.xlsx",
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
                "DEL-001",
                quantity,
                1,
                quantity,
                "ARTICLE DELISKY",
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

    def test_single_file_creates_one_upload_and_one_brand_batch(
        self,
    ):
        result = (
            create_raw_opening_stock_derived_import_reviews(
                self.make_upload(),
                source_system_code="AIO_WEB",
                uploaded_by=self.user,
                stock_date="2026-08-01",
            )
        )

        self.assertEqual(
            ImportSourceUpload.objects.count(),
            1,
        )
        self.assertEqual(
            ImportBatch.objects.count(),
            1,
        )
        self.assertEqual(
            len(result.batches),
            1,
        )

        batch = result.batches[0]

        self.assertEqual(
            batch.brand.code,
            "DELISKY",
        )
        self.assertEqual(
            batch.report_type,
            "OPENING_STOCK",
        )
        self.assertEqual(
            batch.period_start.isoformat(),
            "2026-08-01",
        )
        self.assertEqual(
            batch.period_end.isoformat(),
            "2026-08-01",
        )
        self.assertEqual(
            batch.opening_month.isoformat(),
            "2026-08-01",
        )
        self.assertEqual(
            batch.source_upload_id,
            result.source_upload.pk,
        )
        self.assertEqual(
            batch.rows.count(),
            1,
        )

        row = batch.rows.get()

        self.assertEqual(
            row.raw_data["Qté"],
            10,
        )
        self.assertEqual(
            row.raw_data["العلبة"],
            10,
        )
        self.assertEqual(
            row.cleaned_data["total_units"],
            10,
        )
        self.assertEqual(
            row.cleaned_data["units_per_carton"],
            1,
        )
        self.assertEqual(
            row.cleaned_data["packaging_status"],
            "READY",
        )

    def test_same_raw_file_reuses_existing_batch(
        self,
    ):
        first_upload = self.make_upload()
        file_bytes = first_upload.read()
        first_upload.seek(0)

        first = (
            create_raw_opening_stock_derived_import_reviews(
                first_upload,
                source_system_code="AIO_WEB",
                uploaded_by=self.user,
                stock_date="2026-08-01",
            )
        )

        first_batch_id = (
            first.batches[0].pk
        )

        second_upload = SimpleUploadedFile(
            "VAN1-DELISKY opning stock.xlsx",
            file_bytes,
            content_type=CONTENT_TYPE,
        )

        second = (
            create_raw_opening_stock_derived_import_reviews(
                second_upload,
                source_system_code="AIO_WEB",
                uploaded_by=self.user,
                stock_date="2026-08-01",
            )
        )

        self.assertEqual(
            second.batches[0].pk,
            first_batch_id,
        )
        self.assertEqual(
            ImportSourceUpload.objects.count(),
            1,
        )
        self.assertEqual(
            ImportBatch.objects.count(),
            1,
        )

    def test_corrected_file_updates_mutable_batch(
        self,
    ):
        first = (
            create_raw_opening_stock_derived_import_reviews(
                self.make_upload(
                    quantity=10,
                ),
                source_system_code="AIO_WEB",
                uploaded_by=self.user,
                stock_date="2026-08-01",
            )
        )

        first_batch_id = (
            first.batches[0].pk
        )

        second = (
            create_raw_opening_stock_derived_import_reviews(
                self.make_upload(
                    quantity=99,
                ),
                source_system_code="AIO_WEB",
                uploaded_by=self.user,
                stock_date="2026-08-01",
            )
        )

        self.assertEqual(
            second.batches[0].pk,
            first_batch_id,
        )

        self.assertEqual(
            ImportSourceUpload.objects.count(),
            2,
        )
        self.assertEqual(
            ImportBatch.objects.count(),
            1,
        )

        row = second.batches[0].rows.get()

        self.assertEqual(
            row.raw_data["Qté"],
            99,
        )
        self.assertEqual(
            row.raw_data["العلبة"],
            99,
        )
        self.assertEqual(
            row.cleaned_data["total_units"],
            99,
        )

    def test_invalid_stock_date_creates_nothing(
        self,
    ):
        with self.assertRaises(
            RawOpeningStockImportReviewError
        ):
            create_raw_opening_stock_derived_import_reviews(
                self.make_upload(),
                source_system_code="AIO_WEB",
                uploaded_by=self.user,
                stock_date="2026-02-30",
            )

        self.assertEqual(
            ImportSourceUpload.objects.count(),
            0,
        )
        self.assertEqual(
            ImportBatch.objects.count(),
            0,
        )