from io import BytesIO

from django.test import SimpleTestCase
from openpyxl import Workbook

from apps.imports.services.raw_sales_file import (
    RawSalesFileError,
    adapt_raw_sales_file,
    source_truck_code_from_filename,
    to_report_row_read_result,
)


def build_excel(
    rows,
    *,
    filename,
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

    content = BytesIO()
    workbook.save(content)
    workbook.close()
    content.seek(0)
    content.name = filename

    return content


class RawSalesFileTests(SimpleTestCase):
    def setUp(self):
        self.mapping = {
            "DCV-03": "BIFA LIV03",
            "DLV-01": "BIFA PLIV01",
            "VAN1-DELISKY": "DELISKY LIV01",
            "VAN1-NITA": "NITA LIV01",
        }

    def test_extracts_source_truck_from_filename(self):
        self.assertEqual(
            source_truck_code_from_filename(
                "DCV-03.xlsx"
            ),
            "DCV-03",
        )

        self.assertEqual(
            source_truck_code_from_filename(
                "van1-nita.xlsx"
            ),
            "VAN1-NITA",
        )

    def test_rejects_dpv_filename(self):
        with self.assertRaises(
            RawSalesFileError
        ) as context:
            source_truck_code_from_filename(
                "DPV-01.xlsx"
            )

        self.assertEqual(
            context.exception.code,
            "unsupported_dpv_sales_source",
        )

    def test_ignores_matching_last_summary_footer(self):
        source = build_excel(
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
                [
                    "VDD-2",
                    "18/08/2026 11:00:00",
                    "Client B",
                    200,
                    200,
                    "MILA",
                    200,
                ],
                [
                    "2",
                    None,
                    None,
                    "300,00",
                    "300,00",
                    None,
                    "300,00",
                ],
            ],
            filename="DCV-03.xlsx",
        )

        result = adapt_raw_sales_file(
            source,
            truck_mapping=self.mapping,
        )

        self.assertEqual(
            len(result.rows),
            2,
        )
        self.assertEqual(
            result.source_truck_code,
            "DCV-03",
        )
        self.assertEqual(
            result.rows[0].excel_row_number,
            2,
        )
        self.assertEqual(
            result.rows[1].excel_row_number,
            3,
        )

    def test_does_not_ignore_wrong_summary_count(self):
        source = build_excel(
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
                [
                    "99",
                    None,
                    None,
                    "100,00",
                    "100,00",
                    None,
                    "100,00",
                ],
            ],
            filename="DCV-03.xlsx",
        )

        result = adapt_raw_sales_file(
            source,
            truck_mapping=self.mapping,
        )

        self.assertEqual(
            len(result.rows),
            2,
        )
        self.assertEqual(
            result.rows[1].excel_row_number,
            3,
        )
        self.assertIsNone(
            result.rows[1].values["Date&Heure"],
        )
        self.assertIsNone(
            result.rows[1].values["Nom du client"],
        )


    def test_converts_to_canonical_sales_result(self):
        source = build_excel(
            [
                [
                    "VDD-1",
                    "18/08/2026 10:00:00",
                    "Client A",
                    125,
                    125,
                    "MILA",
                    125,
                ],
            ],
            filename="DLV-01.xlsx",
        )

        adapted = adapt_raw_sales_file(
            source,
            truck_mapping=self.mapping,
        )

        result = to_report_row_read_result(
            adapted
        )

        self.assertEqual(
            result.report_type,
            "SALES",
        )
        self.assertEqual(
            result.headers,
            (
                "VAN",
                "Date&Heure",
                "Nom du client",
                "Total",
                "Region",
            ),
        )
        self.assertEqual(
            result.row_count,
            1,
        )

        row = result.rows[0].as_dict()

        self.assertEqual(
            row["VAN"],
            "BIFA PLIV01",
        )
        self.assertEqual(
            row["Total"],
            125,
        )
        self.assertEqual(
            row["Region"],
            "MILA",
        )
