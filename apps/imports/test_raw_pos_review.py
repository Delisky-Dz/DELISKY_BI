from io import BytesIO
from datetime import datetime

from django.test import SimpleTestCase
from openpyxl import Workbook

from apps.imports.services.raw_pos_adapter import (
    adapt_raw_pos_row,
)
from apps.imports.services.raw_pos_file import (
    adapt_raw_pos_file,
    source_truck_code_from_filename,
)
from apps.imports.services.raw_pos_review import (
    prepare_raw_pos_review,
)


class RawPosReviewTests(SimpleTestCase):
    def _workbook(
        self,
        headers,
        rows,
    ):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Classeur"

        worksheet.append(headers)

        for row in rows:
            worksheet.append(row)

        buffer = BytesIO()
        workbook.save(buffer)
        workbook.close()
        buffer.seek(0)

        return buffer

    def test_historical_filename_extracts_source_truck(self):
        self.assertEqual(
            source_truck_code_from_filename(
                "DCV-03 pos_2026-04-04_to_2026-08-26.xlsx"
            ),
            "DCV-03",
        )

        self.assertEqual(
            source_truck_code_from_filename(
                "VAN2-NITA pos_2026-04-04_to_2026-08-26.xlsx"
            ),
            "VAN2-NITA",
        )

    def test_adapter_is_independent_of_column_order(self):
        adapted = adapt_raw_pos_row(
            {
                "Date": datetime(2026, 4, 4),
                "Cause d'ignoration": "FERME",
                "Nom du client": "Client A",
                "Message d'ignoration": None,
            },
            source_truck_code="VAN2-NITA",
            truck_mapping={
                "VAN2-NITA": "NITA LIV02",
            },
        )

        self.assertEqual(
            adapted["VAN"],
            "NITA LIV02",
        )
        self.assertEqual(
            adapted["Nom du client"],
            "Client A",
        )

    def test_file_skips_real_export_summary_footer(self):
        source = self._workbook(
            [
                "Nom du client",
                "Cause d'ignoration",
                "Latitude",
                "Longitude",
                "Message d'ignoration",
                "Date",
            ],
            [
                [
                    "Client A",
                    None,
                    36.0,
                    6.0,
                    None,
                    datetime(2026, 4, 4),
                ],
                [
                    "1",
                    None,
                    None,
                    None,
                    None,
                    None,
                ],
            ],
        )

        result = adapt_raw_pos_file(
            source,
            truck_mapping={
                "VAN2-NITA": "NITA LIV02",
            },
            original_filename=(
                "VAN2-NITA "
                "pos_2026-04-04_to_2026-08-26.xlsx"
            ),
        )

        self.assertEqual(
            len(result.rows),
            1,
        )
        self.assertEqual(
            result.rows[0].excel_row_number,
            2,
        )
        self.assertEqual(
            result.source_truck_code,
            "VAN2-NITA",
        )

    def test_prepare_review_uses_selected_period(self):
        source = self._workbook(
            [
                "Nom du client",
                "Latitude",
                "Longitude",
                "Message d'ignoration",
                "Date",
                "Cause d'ignoration",
            ],
            [
                [
                    "Client A",
                    36.0,
                    6.0,
                    None,
                    datetime(2026, 4, 4),
                    None,
                ],
                [
                    "1",
                    None,
                    None,
                    None,
                    None,
                    None,
                ],
            ],
        )

        result = prepare_raw_pos_review(
            source,
            truck_mapping={
                "DCV-03": "BIFA LIV03",
            },
            period_start="2026-04-04",
            period_end="2026-08-26",
            original_filename=(
                "DCV-03 "
                "pos_2026-04-04_to_2026-08-26.xlsx"
            ),
        )

        self.assertEqual(
            result.row_result.row_count,
            1,
        )
        self.assertEqual(
            str(result.period_start),
            "2026-04-04",
        )
        self.assertEqual(
            str(result.period_end),
            "2026-08-26",
        )


    def test_blank_client_zero_coordinates_is_excluded_source_artifact(self):
        source = self._workbook(
            [
                "Nom du client",
                "Cause d'ignoration",
                "Latitude",
                "Longitude",
                "Message d'ignoration",
                "Date",
            ],
            [
                [
                    None,
                    None,
                    0,
                    0,
                    None,
                    datetime(2026, 8, 22),
                ],
            ],
        )

        result = prepare_raw_pos_review(
            source,
            truck_mapping={
                "VAN3-DELISKY": "DELISKY LIV03",
            },
            period_start="2026-04-04",
            period_end="2026-08-26",
            original_filename=(
                "VAN3-DELISKY "
                "pos_2026-04-04_to_2026-08-26.xlsx"
            ),
        )

        cleaned_row = (
            result.cleaning_result.rows[0]
        )

        self.assertEqual(
            cleaned_row.status,
            "EXCLUDED",
        )

        self.assertEqual(
            [
                issue.code
                for issue in cleaned_row.issues
            ],
            [
                "pos_blank_client_source_artifact",
            ],
        )

    def test_missing_client_with_real_coordinates_remains_error(self):
        source = self._workbook(
            [
                "Nom du client",
                "Cause d'ignoration",
                "Latitude",
                "Longitude",
                "Message d'ignoration",
                "Date",
            ],
            [
                [
                    None,
                    None,
                    36.35,
                    6.30,
                    None,
                    datetime(2026, 8, 22),
                ],
            ],
        )

        result = prepare_raw_pos_review(
            source,
            truck_mapping={
                "VAN3-DELISKY": "DELISKY LIV03",
            },
            period_start="2026-04-04",
            period_end="2026-08-26",
            original_filename=(
                "VAN3-DELISKY "
                "pos_2026-04-04_to_2026-08-26.xlsx"
            ),
        )

        cleaned_row = (
            result.cleaning_result.rows[0]
        )

        issue_codes = [
            issue.code
            for issue in cleaned_row.issues
        ]

        self.assertEqual(
            cleaned_row.status,
            "EXCLUDED",
        )

        self.assertIn(
            "missing_client",
            issue_codes,
        )

        self.assertNotIn(
            "pos_blank_client_source_artifact",
            issue_codes,
        )
