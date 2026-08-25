from io import BytesIO

from django.core.files.uploadedfile import (
    SimpleUploadedFile,
)
from django.test import SimpleTestCase
from openpyxl import Workbook

from apps.imports.services.raw_opening_stock_file import (
    RawOpeningStockFileError,
    adapt_raw_opening_stock_file,
    source_truck_code_from_filename,
    to_report_row_read_result,
)


CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument."
    "spreadsheetml.sheet"
)


class RawOpeningStockFileTests(
    SimpleTestCase
):
    def make_upload(
        self,
        *,
        filename=(
            "DCV-03 opning stock.xlsx"
        ),
        rows=None,
        include_footer=False,
    ):
        if rows is None:
            rows = [
                [
                    "ABC-001",
                    34,
                    8,
                    "4:2",
                    "BALBON FRUITE",
                ],
                [
                    "ABC-002",
                    16,
                    8,
                    2,
                    "ARTICLE B",
                ],
            ]

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

        total_quantity = 0

        for row in rows:
            worksheet.append(
                row
            )

            if (
                row[1] is not None
                and isinstance(
                    row[1],
                    (int, float),
                )
            ):
                total_quantity += (
                    row[1]
                )

        if include_footer:
            worksheet.append(
                [
                    len(rows),
                    f"{total_quantity},000",
                    None,
                    None,
                    len(rows),
                ]
            )

        buffer = BytesIO()
        workbook.save(buffer)
        workbook.close()

        return SimpleUploadedFile(
            filename,
            buffer.getvalue(),
            content_type=CONTENT_TYPE,
        )

    def test_extracts_source_truck_from_real_filename(
        self,
    ):
        self.assertEqual(
            source_truck_code_from_filename(
                "DCV-03 opning stock.xlsx"
            ),
            "DCV-03",
        )

        self.assertEqual(
            source_truck_code_from_filename(
                "VAN2-DELISKY opening stock.xlsx"
            ),
            "VAN2-DELISKY",
        )

    def test_adapts_real_bifa_layout(
        self,
    ):
        result = (
            adapt_raw_opening_stock_file(
                self.make_upload(),
                truck_mapping={
                    "DCV-03":
                        "BIFA LIV03",
                },
            )
        )

        self.assertEqual(
            result.worksheet_name,
            "Classeur",
        )
        self.assertEqual(
            len(result.rows),
            2,
        )

        self.assertEqual(
            result.rows[0].values,
            {
                "VAN":
                    "BIFA LIV03",
                "Qté": 34,
                "Article":
                    "BALBON FRUITE",
                "Colisage": 8,
                "العلبة": "4:2",
                "Barcode":
                    "ABC-001",
            },
        )

    def test_aio_blank_barcode_is_supported(
        self,
    ):
        result = (
            adapt_raw_opening_stock_file(
                self.make_upload(
                    filename=(
                        "VAN2-DELISKY "
                        "opning stock.xlsx"
                    ),
                    rows=[
                        [
                            None,
                            20,
                            1,
                            20,
                            "ARTICLE A",
                        ],
                    ],
                ),
                truck_mapping={
                    "VAN2-DELISKY":
                        "DELISKY LIV02",
                },
            )
        )

        self.assertIsNone(
            result.rows[0].values[
                "Barcode"
            ]
        )

    def test_ignores_real_export_footer(
        self,
    ):
        result = (
            adapt_raw_opening_stock_file(
                self.make_upload(
                    include_footer=True,
                ),
                truck_mapping={
                    "DCV-03":
                        "BIFA LIV03",
                },
            )
        )

        self.assertEqual(
            len(result.rows),
            2,
        )

    def test_wrong_footer_count_is_not_silently_ignored(
        self,
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
                "ABC",
                10,
                5,
                2,
                "ARTICLE A",
            ]
        )

        worksheet.append(
            [
                99,
                "10,000",
                None,
                None,
                99,
            ]
        )

        buffer = BytesIO()
        workbook.save(buffer)
        workbook.close()

        uploaded = SimpleUploadedFile(
            "DCV-03 opning stock.xlsx",
            buffer.getvalue(),
            content_type=CONTENT_TYPE,
        )

        with self.assertRaises(
            RawOpeningStockFileError
        ) as context:
            adapt_raw_opening_stock_file(
                uploaded,
                truck_mapping={
                    "DCV-03":
                        "BIFA LIV03",
                },
            )

        self.assertEqual(
            context.exception.code,
            "invalid_export_summary_footer",
        )

    def test_report_result_preserves_quantity_metadata(
        self,
    ):
        adapted = (
            adapt_raw_opening_stock_file(
                self.make_upload(),
                truck_mapping={
                    "DCV-03":
                        "BIFA LIV03",
                },
            )
        )

        result = (
            to_report_row_read_result(
                adapted
            )
        )

        self.assertEqual(
            result.headers,
            (
                "VAN",
                "Qté",
                "Article",
                "Colisage",
                "العلبة",
                "Barcode",
            ),
        )

        row = (
            result.rows[0].as_dict()
        )

        self.assertEqual(
            row["Colisage"],
            8,
        )
        self.assertEqual(
            row["العلبة"],
            "4:2",
        )
        self.assertEqual(
            row["Barcode"],
            "ABC-001",
        )

    def test_unknown_filename_truck_fails(
        self,
    ):
        with self.assertRaises(
            RawOpeningStockFileError
        ) as context:
            adapt_raw_opening_stock_file(
                self.make_upload(
                    filename=(
                        "UNKNOWN opning stock.xlsx"
                    ),
                ),
                truck_mapping={
                    "DCV-03":
                        "BIFA LIV03",
                },
            )

        self.assertEqual(
            context.exception.details[
                "cause_code"
            ],
            "source_truck_not_mapped",
        )