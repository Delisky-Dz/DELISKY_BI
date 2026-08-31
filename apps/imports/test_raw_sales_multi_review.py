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
    ImportBatchStatus,
    ImportSourceSystem,
    ImportSourceUpload,
    SourceTruckMapping,
)
from apps.imports.services.raw_sales_multi_review import (
    RawSalesImportRequest,
    create_raw_sales_multi_import_reviews,
)


CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument."
    "spreadsheetml.sheet"
)


class RawSalesMultiReviewTests(TestCase):
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
            get_user_model().objects.create_user(
                username="raw-sales-multi-reviewer",
                password="test-password",
            )
        )

        self.bifa = (
            DistributionBrand.objects.create(
                code="BIFA",
                name="BIFA",
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

        self.bifa_truck = Truck.objects.create(
            internal_code="BIFA LIV03",
            distribution_brand=self.bifa,
            registration_number="MULTI-BIFA-03",
            brand="TEST",
            model="TEST",
        )

        self.nita_truck = Truck.objects.create(
            internal_code="NITA LIV02",
            distribution_brand=self.nita,
            registration_number="MULTI-NITA-02",
            brand="TEST",
            model="TEST",
        )

        self.bifa_source = (
            ImportSourceSystem.objects.create(
                code="BIFA_MILA",
                name="BIFA MILA",
                is_active=True,
            )
        )

        self.aio_source = (
            ImportSourceSystem.objects.create(
                code="AIO_WEB",
                name="AIO WEB",
                is_active=True,
            )
        )

        SourceTruckMapping.objects.create(
            source_system=self.bifa_source,
            source_code="DCV-03",
            truck=self.bifa_truck,
            is_active=True,
        )

        SourceTruckMapping.objects.create(
            source_system=self.aio_source,
            source_code="VAN2-NITA",
            truck=self.nita_truck,
            is_active=True,
        )

    def make_upload(
        self,
        filename,
        rows,
    ):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Classeur"

        worksheet.append(
            [
                "Cl\u00e9",
                "Date&Heure",
                "Nom du client",
                "Total",
                "Versement",
                "Region",
                "NET",
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
            content_type=CONTENT_TYPE,
        )

    def test_multiple_valid_files_are_reviewed(self):
        bifa = self.make_upload(
            "DCV-03.xlsx",
            [
                [
                    "VDD-1",
                    "18/08/2026 10:00:00",
                    "Client A",
                    100,
                    100,
                    "MILA",
                    100,
                ],
            ],
        )

        nita = self.make_upload(
            "VAN2-NITA.xlsx",
            [
                [
                    "VDD-2",
                    "18/08/2026 11:00:00",
                    "Client B",
                    200,
                    200,
                    "MILA",
                    200,
                ],
            ],
        )

        result = create_raw_sales_multi_import_reviews(
            (
                RawSalesImportRequest(
                    source=bifa,
                    source_system_code="BIFA_MILA",
                    period_start="2026-08-18",
                    period_end="2026-08-18",
                    original_filename="DCV-03.xlsx",
                ),
                RawSalesImportRequest(
                    source=nita,
                    source_system_code="AIO_WEB",
                    period_start="2026-08-01",
                    period_end="2026-08-18",
                    original_filename="VAN2-NITA.xlsx",
                ),
            ),
            uploaded_by=self.user,
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
            ImportBatch.objects.count(),
            2,
        )
        self.assertEqual(
            ImportSourceUpload.objects.count(),
            2,
        )

        statuses = {
            item.batch.status
            for item in result.files
            if item.batch is not None
        }

        self.assertEqual(
            statuses,
            {ImportBatchStatus.REVIEWED},
        )

    def test_invalid_file_does_not_rollback_valid_file(self):
        valid = self.make_upload(
            "DCV-03.xlsx",
            [
                [
                    "VDD-3",
                    "18/08/2026 10:00:00",
                    "Client A",
                    100,
                    100,
                    "MILA",
                    100,
                ],
            ],
        )

        invalid = self.make_upload(
            "VAN2-NITA.xlsx",
            [
                [
                    "VDD-4",
                    "31/07/2026 10:00:00",
                    "Client B",
                    200,
                    200,
                    "MILA",
                    200,
                ],
            ],
        )

        result = create_raw_sales_multi_import_reviews(
            (
                RawSalesImportRequest(
                    source=valid,
                    source_system_code="BIFA_MILA",
                    period_start="2026-08-18",
                    period_end="2026-08-18",
                    original_filename="DCV-03.xlsx",
                ),
                RawSalesImportRequest(
                    source=invalid,
                    source_system_code="AIO_WEB",
                    period_start="2026-08-01",
                    period_end="2026-08-18",
                    original_filename="VAN2-NITA.xlsx",
                ),
            ),
            uploaded_by=self.user,
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
            "sale_outside_period",
        )

        self.assertEqual(
            ImportBatch.objects.count(),
            1,
        )
        self.assertEqual(
            ImportSourceUpload.objects.count(),
            1,
        )

    def test_blocked_review_counts_as_successful_processing(self):
        source = self.make_upload(
            "VAN2-NITA.xlsx",
            [
                [
                    "VDD-5",
                    "16/08/2026 15:34:54",
                    "Client Blocked",
                    "INVALID-TOTAL",
                    1850,
                    None,
                    1850,
                ],
            ],
        )

        result = create_raw_sales_multi_import_reviews(
            (
                RawSalesImportRequest(
                    source=source,
                    source_system_code="AIO_WEB",
                    period_start="2026-08-01",
                    period_end="2026-08-18",
                    original_filename="VAN2-NITA.xlsx",
                ),
            ),
            uploaded_by=self.user,
        )

        self.assertEqual(
            result.succeeded_count,
            1,
        )
        self.assertEqual(
            result.failed_count,
            0,
        )

        batch = result.files[0].batch

        self.assertIsNotNone(batch)
        self.assertEqual(
            batch.status,
            ImportBatchStatus.BLOCKED,
        )
        self.assertEqual(
            batch.total_rows,
            1,
        )
        self.assertEqual(
            batch.excluded_rows,
            1,
        )
        self.assertEqual(
            batch.error_count,
            1,
        )

    def test_all_invalid_files_create_no_records(self):
        first = self.make_upload(
            "DCV-03.xlsx",
            [
                [
                    "VDD-6",
                    "17/08/2026 10:00:00",
                    "Client A",
                    100,
                    100,
                    "MILA",
                    100,
                ],
            ],
        )

        second = self.make_upload(
            "VAN2-NITA.xlsx",
            [
                [
                    "VDD-7",
                    "31/07/2026 10:00:00",
                    "Client B",
                    200,
                    200,
                    "MILA",
                    200,
                ],
            ],
        )

        result = create_raw_sales_multi_import_reviews(
            (
                RawSalesImportRequest(
                    source=first,
                    source_system_code="BIFA_MILA",
                    period_start="2026-08-18",
                    period_end="2026-08-18",
                    original_filename="DCV-03.xlsx",
                ),
                RawSalesImportRequest(
                    source=second,
                    source_system_code="AIO_WEB",
                    period_start="2026-08-01",
                    period_end="2026-08-18",
                    original_filename="VAN2-NITA.xlsx",
                ),
            ),
            uploaded_by=self.user,
        )

        self.assertEqual(
            result.succeeded_count,
            0,
        )
        self.assertEqual(
            result.failed_count,
            2,
        )
        self.assertEqual(
            ImportBatch.objects.count(),
            0,
        )
        self.assertEqual(
            ImportSourceUpload.objects.count(),
            0,
        )
