from django.test import SimpleTestCase

from apps.imports.services.raw_opening_stock_adapter import (
    RawOpeningStockAdapterError,
    adapt_raw_opening_stock_row,
    adapt_raw_opening_stock_rows,
)
from apps.imports.services.source_truck_mapper import (
    SourceTruckMappingError,
)


class RawOpeningStockAdapterTests(
    SimpleTestCase
):
    def test_adapts_real_opening_stock_shape(
        self,
    ):
        result = (
            adapt_raw_opening_stock_row(
                {
                    "Désignation":
                        "BALBON FRUITE",
                    "Qté": 34,
                    "Colisage": 8,
                    "العلبة": "4:2",
                    "Barcode": "ABC-001",
                },
                source_truck_code="DCV-03",
                truck_mapping={
                    "DCV-03":
                        "BIFA LIV03",
                },
            )
        )

        self.assertEqual(
            result,
            {
                "VAN": "BIFA LIV03",
                "Qté": 34,
                "Article":
                    "BALBON FRUITE",
                "Colisage": 8,
                "العلبة": "4:2",
                "Barcode": "ABC-001",
            },
        )

    def test_blank_barcode_is_preserved(
        self,
    ):
        result = (
            adapt_raw_opening_stock_row(
                {
                    "Désignation":
                        "ARTICLE A",
                    "Qté": 20,
                    "Colisage": 1,
                    "العلبة": 20,
                    "Barcode": None,
                },
                source_truck_code=(
                    "VAN2-DELISKY"
                ),
                truck_mapping={
                    "VAN2-DELISKY":
                        "DELISKY LIV02",
                },
            )
        )

        self.assertIn(
            "Barcode",
            result,
        )
        self.assertIsNone(
            result["Barcode"]
        )

    def test_header_matching_is_normalized(
        self,
    ):
        result = (
            adapt_raw_opening_stock_row(
                {
                    " désignation ":
                        "ARTICLE A",
                    "qté": 10,
                    " COLISAGE ": 5,
                    " العلبة ": 2,
                },
                source_truck_code="DCV-03",
                truck_mapping={
                    "DCV-03":
                        "BIFA LIV03",
                },
            )
        )

        self.assertEqual(
            result["Article"],
            "ARTICLE A",
        )
        self.assertEqual(
            result["Qté"],
            10,
        )
        self.assertEqual(
            result["Colisage"],
            5,
        )
        self.assertEqual(
            result["العلبة"],
            2,
        )

    def test_zero_blank_product_can_be_preserved(
        self,
    ):
        result = (
            adapt_raw_opening_stock_row(
                {
                    "Désignation": None,
                    "Qté": 0,
                    "Colisage": None,
                    "العلبة": None,
                },
                source_truck_code="DCV-03",
                truck_mapping={
                    "DCV-03":
                        "BIFA LIV03",
                },
            )
        )

        self.assertEqual(
            result["Qté"],
            0,
        )
        self.assertIsNone(
            result["Article"]
        )

    def test_missing_required_column_is_rejected(
        self,
    ):
        with self.assertRaises(
            RawOpeningStockAdapterError
        ) as context:
            adapt_raw_opening_stock_row(
                {
                    "Désignation":
                        "ARTICLE A",
                    "Qté": 10,
                    "العلبة": 2,
                },
                source_truck_code="DCV-03",
                truck_mapping={
                    "DCV-03":
                        "BIFA LIV03",
                },
            )

        self.assertEqual(
            context.exception.code,
            "missing_required_column",
        )

    def test_unknown_filename_truck_is_not_guessed(
        self,
    ):
        with self.assertRaises(
            SourceTruckMappingError
        ):
            adapt_raw_opening_stock_row(
                {
                    "Désignation":
                        "ARTICLE A",
                    "Qté": 10,
                    "Colisage": 5,
                    "العلبة": 2,
                },
                source_truck_code=(
                    "UNKNOWN"
                ),
                truck_mapping={
                    "DCV-03":
                        "BIFA LIV03",
                },
            )

    def test_multiple_rows_report_failing_row(
        self,
    ):
        with self.assertRaises(
            RawOpeningStockAdapterError
        ) as context:
            adapt_raw_opening_stock_rows(
                [
                    {
                        "Désignation":
                            "ARTICLE A",
                        "Qté": 10,
                        "Colisage": 5,
                        "العلبة": 2,
                    },
                    {
                        "Désignation":
                            "ARTICLE B",
                        "Qté": 20,
                        # missing Colisage
                        "العلبة": 4,
                    },
                ],
                source_truck_code="DCV-03",
                truck_mapping={
                    "DCV-03":
                        "BIFA LIV03",
                },
            )

        self.assertEqual(
            context.exception.code,
            "row_adaptation_failed",
        )
        self.assertEqual(
            context.exception.details[
                "row_number"
            ],
            2,
        )