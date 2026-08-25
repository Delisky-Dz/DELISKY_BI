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
)
from apps.imports.services.raw_opening_stock_review import (
    RawOpeningStockImportReviewError,
    create_raw_opening_stock_import_review,
)


CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument."
    "spreadsheetml.sheet"
)


class RawOpeningStockImportReviewTests(TestCase):
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
                username="raw-opening-stock-reviewer",
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

    def make_upload(
        self,
        rows,
        *,
        filename="SOURCE DELISKY opning stock.xlsx",
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

    def test_creates_opening_stock_batch_with_single_date(
        self,
    ):
        result = (
            create_raw_opening_stock_import_review(
                self.make_upload(
                    [
                        [
                            "DEL-001",
                            10,
                            1,
                            10,
                            "ARTICLE A",
                        ],
                        [
                            "DEL-002",
                            20,
                            1,
                            20,
                            "ARTICLE B",
                        ],
                    ]
                ),
                uploaded_by=self.user,
                brand_code="DELISKY",
                stock_date="2026-03-07",
                truck_mapping={
                    "SOURCE DELISKY":
                        "DELISKY LIV01",
                },
            )
        )

        self.assertTrue(
            result.created
        )
        self.assertEqual(
            ImportBatch.objects.count(),
            1,
        )

        batch = result.batch
        batch.refresh_from_db()

        self.assertEqual(
            batch.report_type,
            "OPENING_STOCK",
        )
        self.assertEqual(
            batch.brand,
            self.delisky,
        )
        self.assertEqual(
            batch.period_start.isoformat(),
            "2026-03-07",
        )
        self.assertEqual(
            batch.period_end.isoformat(),
            "2026-03-07",
        )
        self.assertEqual(
            batch.status,
            "REVIEWED",
        )
        self.assertEqual(
            batch.total_rows,
            2,
        )
        self.assertEqual(
            batch.accepted_rows,
            2,
        )
        self.assertEqual(
            batch.excluded_rows,
            0,
        )
        self.assertEqual(
            batch.error_count,
            0,
        )

        rows = list(
            batch.rows.all()
        )

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
            rows[0].raw_data["Barcode"],
            "DEL-001",
        )
        self.assertEqual(
            rows[0].raw_data["Colisage"],
            1,
        )
        self.assertEqual(
            rows[0].raw_data["العلبة"],
            10,
        )
        self.assertEqual(
            rows[0].raw_data["Article"],
            "ARTICLE A",
        )

    def test_rejects_unknown_brand(
        self,
    ):
        with self.assertRaises(
            RawOpeningStockImportReviewError
        ) as context:
            create_raw_opening_stock_import_review(
                self.make_upload(
                    [
                        [
                            "DEL-001",
                            10,
                            1,
                            10,
                            "ARTICLE A",
                        ],
                    ]
                ),
                uploaded_by=self.user,
                brand_code="UNKNOWN",
                stock_date="2026-03-07",
                truck_mapping={
                    "SOURCE DELISKY":
                        "DELISKY LIV01",
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

    def test_rejects_invalid_stock_date(
        self,
    ):
        with self.assertRaises(
            RawOpeningStockImportReviewError
        ) as context:
            create_raw_opening_stock_import_review(
                self.make_upload(
                    [
                        [
                            "DEL-001",
                            10,
                            1,
                            10,
                            "ARTICLE A",
                        ],
                    ]
                ),
                uploaded_by=self.user,
                brand_code="DELISKY",
                stock_date="2026-02-30",
                truck_mapping={
                    "SOURCE DELISKY":
                        "DELISKY LIV01",
                },
            )

        self.assertEqual(
            context.exception.code,
            "invalid_stock_date",
        )
        self.assertEqual(
            ImportBatch.objects.count(),
            0,
        )

    def test_rejects_filename_truck_from_other_brand(
        self,
    ):
        with self.assertRaises(
            RawOpeningStockImportReviewError
        ) as context:
            create_raw_opening_stock_import_review(
                self.make_upload(
                    [
                        [
                            "NITA-001",
                            20,
                            1,
                            20,
                            "ARTICLE NITA",
                        ],
                    ],
                    filename=(
                        "SOURCE NITA opning stock.xlsx"
                    ),
                ),
                uploaded_by=self.user,
                brand_code="DELISKY",
                stock_date="2026-03-07",
                truck_mapping={
                    "SOURCE NITA":
                        "NITA LIV01",
                },
            )

        self.assertEqual(
            context.exception.code,
            "brand_validation_failed",
        )

        issues = (
            context.exception.details[
                "issues"
            ]
        )

        self.assertEqual(
            len(issues),
            1,
        )
        self.assertEqual(
            issues[0]["code"],
            "brand_mismatch",
        )
        self.assertEqual(
            issues[0][
                "actual_brand_code"
            ],
            "NITA",
        )
        self.assertEqual(
            issues[0][
                "expected_brand_code"
            ],
            "DELISKY",
        )

        self.assertEqual(
            ImportBatch.objects.count(),
            0,
        )