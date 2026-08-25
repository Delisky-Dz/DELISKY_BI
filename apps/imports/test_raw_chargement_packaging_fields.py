from unittest.mock import patch

from django.test import SimpleTestCase

from apps.imports.services.raw_chargement_adapter import (
    adapt_raw_chargement_row,
)
from apps.imports.services.raw_chargement_file import (
    AdaptedChargementRow,
    RawChargementFileResult,
    to_report_row_read_result,
)


class RawChargementPackagingFieldTests(
    SimpleTestCase
):
    @patch(
        "apps.imports.services."
        "raw_chargement_adapter."
        "map_source_truck_code",
        return_value="BIFA-LIV03",
    )
    def test_adapter_preserves_barcode(
        self,
        mapper,
    ):
        result = adapt_raw_chargement_row(
            {
                "Vers l'emplacement": "DCV-03",
                "Qt\u00e9": 54,
                "Article": "AVANTAGE",
                "Barcode": "BIS-00010",
            },
            truck_mapping={},
        )

        self.assertEqual(
            result["Barcode"],
            "BIS-00010",
        )

    @patch(
        "apps.imports.services."
        "raw_chargement_adapter."
        "map_source_truck_code",
        return_value="AIO-LIV02",
    )
    def test_adapter_allows_missing_barcode_column(
        self,
        mapper,
    ):
        result = adapt_raw_chargement_row(
            {
                "Vers l'emplacement":
                    "VAN2-DELISKY",
                "Qt\u00e9": 8,
                "Article":
                    "BEST BIS GAUFRETTES",
            },
            truck_mapping={},
        )

        self.assertNotIn(
            "Barcode",
            result,
        )

    def test_report_rows_include_barcode_when_available(
        self,
    ):
        result = RawChargementFileResult(
            filename="chargement.xlsx",
            worksheet_name="Classeur",
            rows=(
                AdaptedChargementRow(
                    excel_row_number=2,
                    values={
                        "VAN": "BIFA-LIV03",
                        "Qt\u00e9": 54,
                        "Article": "AVANTAGE",
                        "Barcode": "BIS-00010",
                    },
                ),
            ),
        )

        row_result = to_report_row_read_result(
            result
        )

        self.assertIn(
            "Barcode",
            row_result.headers,
        )
        self.assertEqual(
            row_result.rows[0]
            .as_dict()["Barcode"],
            "BIS-00010",
        )
