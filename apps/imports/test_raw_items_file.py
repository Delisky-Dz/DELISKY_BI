from io import BytesIO

from django.core.files.uploadedfile import (
    SimpleUploadedFile,
)
from django.test import SimpleTestCase
from openpyxl import Workbook

from apps.imports.services.raw_items_file import (
    CANONICAL_ITEMS_HEADERS,
    RawItemsFileError,
    adapt_raw_items_file,
    to_report_row_read_result,
)


class RawItemsFileTests(SimpleTestCase):
    def setUp(self):
        self.mapping = {
            "DCV-03": "BIFA LIV03",
        }

    def make_file(
        self,
        rows,
        *,
        headers=None,
        filename="DCV-03 items.xlsx",
    ):
        workbook = Workbook()
        worksheet = workbook.active

        worksheet.append(
            headers
            or (
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

    def test_reads_items_and_ignores_matching_footer(self):
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

        result = adapt_raw_items_file(
            source,
            truck_mapping=self.mapping,
        )

        self.assertEqual(
            len(result.rows),
            2,
        )
        self.assertEqual(
            [
                row.excel_row_number
                for row in result.rows
            ],
            [2, 3],
        )
        self.assertEqual(
            result.rows[0].values["VAN"],
            "BIFA LIV03",
        )

    def test_wrong_quantity_footer_is_not_dropped(self):
        source = self.make_file(
            (
                (
                    "ARTICLE A",
                    "A1",
                    10,
                    "CLIENT A",
                ),
                (
                    "2",
                    None,
                    "999",
                    None,
                ),
            )
        )

        result = adapt_raw_items_file(
            source,
            truck_mapping=self.mapping,
        )

        self.assertEqual(
            len(result.rows),
            2,
        )
        self.assertEqual(
            result.rows[-1].values["Article"],
            "2",
        )

    def test_summary_like_middle_row_is_not_dropped(self):
        source = self.make_file(
            (
                (
                    "1",
                    None,
                    10,
                    None,
                ),
                (
                    "ARTICLE B",
                    "B1",
                    20,
                    "CLIENT B",
                ),
            )
        )

        result = adapt_raw_items_file(
            source,
            truck_mapping=self.mapping,
        )

        self.assertEqual(
            len(result.rows),
            2,
        )

    def test_missing_required_column_reports_excel_row(self):
        source = self.make_file(
            (
                (
                    "ARTICLE A",
                    10,
                ),
            ),
            headers=(
                "Article",
                "Qt\u00e9",
            ),
        )

        with self.assertRaises(
            RawItemsFileError
        ) as captured:
            adapt_raw_items_file(
                source,
                    truck_mapping=self.mapping,
            )

        self.assertEqual(
            captured.exception.code,
            "row_adaptation_failed",
        )
        self.assertEqual(
            captured.exception.details[
                "excel_row_number"
            ],
            2,
        )
        self.assertEqual(
            captured.exception.details[
                "cause_code"
            ],
            "missing_required_column",
        )

    def test_derives_source_truck_code_from_filename(self):
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

        result = adapt_raw_items_file(
            source,
            truck_mapping=self.mapping,
            original_filename=(
                "DCV-03 items.xlsx"
            ),
        )

        self.assertEqual(
            result.source_truck_code,
            "DCV-03",
        )
        self.assertEqual(
            result.rows[0].values["VAN"],
            "BIFA LIV03",
        )

    def test_converts_to_items_report_rows(self):
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

        adapted = adapt_raw_items_file(
            source,
            truck_mapping=self.mapping,
        )

        result = to_report_row_read_result(
            adapted
        )

        self.assertEqual(
            result.report_type,
            "ITEMS",
        )
        self.assertEqual(
            result.headers,
            CANONICAL_ITEMS_HEADERS,
        )
        self.assertEqual(
            len(result.rows),
            1,
        )
        self.assertEqual(
            result.rows[0].row_number,
            2,
        )
