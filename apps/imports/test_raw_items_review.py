from io import BytesIO

from django.core.files.uploadedfile import (
    SimpleUploadedFile,
)
from django.test import SimpleTestCase
from openpyxl import Workbook

from apps.imports.services.raw_items_review import (
    RawItemsImportReviewError,
    prepare_raw_items_review,
)


class RawItemsReviewTests(SimpleTestCase):
    def setUp(self):
        self.mapping = {
            "DCV-03": "BIFA LIV03",
        }

    def make_file(
        self,
        rows,
        *,
        filename="DCV-03 items.xlsx",
    ):
        workbook = Workbook()
        worksheet = workbook.active

        worksheet.append(
            (
                "Article",
                "Code",
                "Qt\u00e9",
                "Client",
            )
        )

        for row in rows:
            worksheet.append(row)

        payload = BytesIO()

        workbook.save(payload)
        workbook.close()

        return SimpleUploadedFile(
            filename,
            payload.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            ),
        )

    def test_prepares_valid_items_review(self):
        source = self.make_file(
            (
                (
                    "ARTICLE A",
                    "A1",
                    10,
                    "CLIENT A",
                ),
                (
                    "ARTICLE B",
                    "B1",
                    20,
                    "CLIENT B",
                ),
                (
                    "2",
                    None,
                    "30",
                    None,
                ),
            )
        )

        result = prepare_raw_items_review(
            source,
            truck_mapping=self.mapping,
            period_start="2026-08-01",
            period_end="2026-08-18",
        )

        self.assertEqual(
            result.period_start.isoformat(),
            "2026-08-01",
        )
        self.assertEqual(
            result.period_end.isoformat(),
            "2026-08-18",
        )
        self.assertEqual(
            len(result.adapted.rows),
            2,
        )
        self.assertEqual(
            len(result.cleaning_result.rows),
            2,
        )
        self.assertTrue(
            all(
                row.status == "ACCEPTED"
                for row
                in result.cleaning_result.rows
            )
        )

    def test_blank_client_is_excluded(self):
        source = self.make_file(
            (
                (
                    "ARTICLE A",
                    "A1",
                    10,
                    None,
                ),
            )
        )

        result = prepare_raw_items_review(
            source,
            truck_mapping=self.mapping,
            period_start="2026-08-01",
            period_end="2026-08-18",
        )

        row = result.cleaning_result.rows[0]

        self.assertEqual(
            row.status,
            "EXCLUDED",
        )
        self.assertTrue(
            any(
                issue.code == "missing_client"
                for issue in row.issues
            )
        )

    def test_negative_quantity_is_excluded(self):
        source = self.make_file(
            (
                (
                    "ARTICLE A",
                    "A1",
                    -5,
                    "CLIENT A",
                ),
            )
        )

        result = prepare_raw_items_review(
            source,
            truck_mapping=self.mapping,
            period_start="2026-08-01",
            period_end="2026-08-18",
        )

        row = result.cleaning_result.rows[0]

        self.assertEqual(
            row.status,
            "EXCLUDED",
        )
        self.assertTrue(
            any(
                issue.code
                == "negative_quantity"
                for issue in row.issues
            )
        )

    def test_invalid_period_range_is_rejected(self):
        source = self.make_file(
            (
                (
                    "ARTICLE A",
                    "A1",
                    10,
                    "CLIENT A",
                ),
            )
        )

        with self.assertRaises(
            RawItemsImportReviewError
        ) as captured:
            prepare_raw_items_review(
                source,
                    truck_mapping=self.mapping,
                period_start="2026-08-18",
                period_end="2026-08-01",
            )

        self.assertEqual(
            captured.exception.code,
            "invalid_period_range",
        )

    def test_invalid_period_date_is_rejected(self):
        source = self.make_file(
            (
                (
                    "ARTICLE A",
                    "A1",
                    10,
                    "CLIENT A",
                ),
            )
        )

        with self.assertRaises(
            RawItemsImportReviewError
        ) as captured:
            prepare_raw_items_review(
                source,
                    truck_mapping=self.mapping,
                period_start="not-a-date",
                period_end="2026-08-18",
            )

        self.assertEqual(
            captured.exception.code,
            "invalid_period_date",
        )

    def test_unmapped_truck_is_wrapped(self):
        self.mapping = {}

        source = self.make_file(
            (
                (
                    "ARTICLE A",
                    "A1",
                    10,
                    "CLIENT A",
                ),
            )
        )

        with self.assertRaises(
            RawItemsImportReviewError
        ) as captured:
            prepare_raw_items_review(
                source,
                truck_mapping=self.mapping,
                period_start="2026-08-01",
                period_end="2026-08-18",
            )

        self.assertEqual(
            captured.exception.code,
            "raw_items_file_failed",
        )
        self.assertEqual(
            captured.exception.details[
                "cause_code"
            ],
            "row_adaptation_failed",
        )
