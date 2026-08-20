from io import BytesIO

from django.test import SimpleTestCase
from openpyxl import Workbook

from apps.imports.services.raw_sales_review import (
    RawSalesImportReviewError,
    prepare_raw_sales_review,
)


def build_sales_excel(
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


class RawSalesReviewTests(SimpleTestCase):
    def setUp(self):
        self.mapping = {
            "DCV-03": "BIFA LIV03",
            "VAN1-DELISKY": "DELISKY LIV01",
            "VAN2-DELISKY": "DELISKY LIV02",
        }

    def test_bifa_single_day_sales_pass(self):
        source = build_sales_excel(
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
                    "1",
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

        result = prepare_raw_sales_review(
            source,
            truck_mapping=self.mapping,
            period_start="2026-08-18",
            period_end="2026-08-18",
        )

        self.assertEqual(
            result.row_result.row_count,
            1,
        )
        self.assertEqual(
            len(result.cleaning_result.rows),
            1,
        )
        self.assertEqual(
            result.cleaning_result.rows[0].status,
            "ACCEPTED",
        )

    def test_august_sales_range_passes(self):
        source = build_sales_excel(
            [
                [
                    "VDD-1",
                    "01/08/2026 08:00:00",
                    "Client A",
                    100,
                    100,
                    "MILA",
                    100,
                ],
                [
                    "VDD-2",
                    "18/08/2026 13:00:00",
                    "Client B",
                    200,
                    200,
                    "MILA",
                    200,
                ],
            ],
            filename="VAN2-DELISKY.xlsx",
        )

        result = prepare_raw_sales_review(
            source,
            truck_mapping=self.mapping,
            period_start="2026-08-01",
            period_end="2026-08-18",
        )

        self.assertEqual(
            result.row_result.row_count,
            2,
        )

    def test_file_with_july_sale_is_rejected_for_august(self):
        source = build_sales_excel(
            [
                [
                    "VDD-1",
                    "01/07/2026 08:00:00",
                    "Client A",
                    100,
                    100,
                    "MILA",
                    100,
                ],
                [
                    "VDD-2",
                    "03/08/2026 13:00:00",
                    "Client B",
                    200,
                    200,
                    "MILA",
                    200,
                ],
            ],
            filename="VAN1-DELISKY.xlsx",
        )

        with self.assertRaises(
            RawSalesImportReviewError
        ) as context:
            prepare_raw_sales_review(
                source,
                truck_mapping=self.mapping,
                period_start="2026-08-01",
                period_end="2026-08-18",
            )

        self.assertEqual(
            context.exception.code,
            "sale_outside_period",
        )
        self.assertEqual(
            context.exception.details[
                "sale_date"
            ],
            "2026-07-01",
        )

    def test_july_to_august_period_passes(self):
        source = build_sales_excel(
            [
                [
                    "VDD-1",
                    "01/07/2026 08:00:00",
                    "Client A",
                    100,
                    100,
                    "MILA",
                    100,
                ],
                [
                    "VDD-2",
                    "03/08/2026 13:00:00",
                    "Client B",
                    200,
                    200,
                    "MILA",
                    200,
                ],
            ],
            filename="VAN1-DELISKY.xlsx",
        )

        result = prepare_raw_sales_review(
            source,
            truck_mapping=self.mapping,
            period_start="2026-07-01",
            period_end="2026-08-03",
        )

        self.assertEqual(
            result.row_result.row_count,
            2,
        )

    def test_invalid_period_range_is_rejected(self):
        source = build_sales_excel(
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
            filename="DCV-03.xlsx",
        )

        with self.assertRaises(
            RawSalesImportReviewError
        ) as context:
            prepare_raw_sales_review(
                source,
                truck_mapping=self.mapping,
                period_start="2026-08-18",
                period_end="2026-08-01",
            )

        self.assertEqual(
            context.exception.code,
            "invalid_period_range",
        )

    def test_missing_datetime_is_rejected(self):
        source = build_sales_excel(
            [
                [
                    "VDD-1",
                    None,
                    "Client A",
                    100,
                    100,
                    "MILA",
                    100,
                ],
            ],
            filename="DCV-03.xlsx",
        )

        with self.assertRaises(
            RawSalesImportReviewError
        ) as context:
            prepare_raw_sales_review(
                source,
                truck_mapping=self.mapping,
                period_start="2026-08-18",
                period_end="2026-08-18",
            )

        self.assertEqual(
            context.exception.code,
            "missing_datetime",
        )
