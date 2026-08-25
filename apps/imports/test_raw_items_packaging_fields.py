from django.test import SimpleTestCase

from apps.imports.services.raw_items_adapter import (
    adapt_raw_items_row,
)
from apps.imports.services.raw_items_file import (
    AdaptedItemsRow,
    RawItemsFileResult,
    to_report_row_read_result,
)


class RawItemsPackagingFieldsTests(
    SimpleTestCase
):
    def test_preserves_nbre_carton_and_barcode(
        self,
    ):
        result = adapt_raw_items_row(
            {
                "Article": "BALBON FRUITE",
                "Qté": 34,
                "Client": "CLIENT A",
                "Nbre carton": "4:2",
                "Barcode": "ABC-001",
            },
            source_truck_code="DCV-03",
            truck_mapping={
                "DCV-03": "BIFA-LIV03",
            },
        )

        self.assertEqual(
            result["Qté vendue"],
            34,
        )
        self.assertEqual(
            result["Nbre carton"],
            "4:2",
        )
        self.assertEqual(
            result["Barcode"],
            "ABC-001",
        )

    def test_old_shape_remains_supported(
        self,
    ):
        result = adapt_raw_items_row(
            {
                "Article": "PRODUCT A",
                "Qté": 12,
                "Client": "CLIENT A",
            },
            source_truck_code="DCV-03",
            truck_mapping={
                "DCV-03": "BIFA-LIV03",
            },
        )

        self.assertEqual(
            result["Qté vendue"],
            12,
        )
        self.assertNotIn(
            "Nbre carton",
            result,
        )
        self.assertNotIn(
            "Barcode",
            result,
        )

    def test_report_rows_include_optional_fields(
        self,
    ):
        result = RawItemsFileResult(
            filename="DCV-03 items.xlsx",
            worksheet_name="Classeur",
            source_truck_code="DCV-03",
            rows=(
                AdaptedItemsRow(
                    excel_row_number=2,
                    values={
                        "VAN": "BIFA-LIV03",
                        "Article":
                            "BALBON FRUITE",
                        "Qté vendue": 34,
                        "Client": "CLIENT A",
                        "Nbre carton": "4:2",
                        "Barcode": "ABC-001",
                    },
                ),
            ),
        )

        row_result = (
            to_report_row_read_result(
                result
            )
        )

        self.assertEqual(
            row_result.headers,
            (
                "VAN",
                "Article",
                "Qté vendue",
                "Client",
                "Nbre carton",
                "Barcode",
            ),
        )

        values = row_result.rows[0].as_dict()

        self.assertEqual(
            values["Nbre carton"],
            "4:2",
        )
        self.assertEqual(
            values["Barcode"],
            "ABC-001",
        )

    def test_optional_headers_are_not_added_for_old_rows(
        self,
    ):
        result = RawItemsFileResult(
            filename="DCV-03 items.xlsx",
            worksheet_name="Classeur",
            source_truck_code="DCV-03",
            rows=(
                AdaptedItemsRow(
                    excel_row_number=2,
                    values={
                        "VAN": "BIFA-LIV03",
                        "Article": "PRODUCT A",
                        "Qté vendue": 12,
                        "Client": "CLIENT A",
                    },
                ),
            ),
        )

        row_result = (
            to_report_row_read_result(
                result
            )
        )

        self.assertEqual(
            row_result.headers,
            (
                "VAN",
                "Article",
                "Qté vendue",
                "Client",
            ),
        )