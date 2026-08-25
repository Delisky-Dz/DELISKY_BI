from django.test import SimpleTestCase

from apps.imports.services.raw_items_adapter import (
    RawItemsAdapterError,
    adapt_raw_items_row,
    adapt_raw_items_rows,
)


class RawItemsAdapterTests(SimpleTestCase):
    def setUp(self):
        self.mapping = {
            "DCV-03": "BIFA LIV03",
            "DLV-02": "BIFA PLIV02",
            "VAN1-DELISKY": "DELISKY LIV01",
        }

    def test_adapts_raw_items_row(self):
        result = adapt_raw_items_row(
            {
                "Article": "SNOWBALL",
                "Code": "1297",
                "Qt\u00e9": 128,
                "Total": 4480,
                "Client": "CLIENT TEST",
            },
            source_truck_code="DCV-03",
            truck_mapping=self.mapping,
        )

        self.assertEqual(
            result,
            {
                "VAN": "BIFA LIV03",
                "Article": "SNOWBALL",
                "Qt\u00e9 vendue": 128,
                "Client": "CLIENT TEST",
            },
        )

    def test_extra_raw_columns_are_ignored(self):
        result = adapt_raw_items_row(
            {
                "Article": "ARTICLE A",
                "Qté": 24,
                "Client": "CLIENT A",
                "Total": 1200,
                "Barcode": "ABC",
                "Catégorie": "BIFA",
            },
            source_truck_code="DCV-03",
            truck_mapping=self.mapping,
        )

        self.assertEqual(
            set(result),
            {
                "VAN",
                "Article",
                "Qté vendue",
                "Client",
                "Barcode",
            },
        )

        self.assertEqual(
            result["Barcode"],
            "ABC",
        )

        self.assertNotIn(
            "Total",
            result,
        )

        self.assertNotIn(
            "Catégorie",
            result,
        )
    def test_missing_client_column_is_rejected(self):
        with self.assertRaises(
            RawItemsAdapterError
        ) as captured:
            adapt_raw_items_row(
                {
                    "Article": "ARTICLE A",
                    "Qt\u00e9": 24,
                },
                source_truck_code="DCV-03",
                truck_mapping=self.mapping,
            )

        self.assertEqual(
            captured.exception.code,
            "missing_required_column",
        )
        self.assertEqual(
            captured.exception.details[
                "column"
            ],
            "Client",
        )

    def test_unmapped_truck_is_rejected(self):
        with self.assertRaises(
            Exception
        ) as captured:
            adapt_raw_items_row(
                {
                    "Article": "ARTICLE A",
                    "Qt\u00e9": 24,
                    "Client": "CLIENT A",
                },
                source_truck_code="UNKNOWN",
                truck_mapping=self.mapping,
            )

        self.assertEqual(
            captured.exception.code,
            "source_truck_not_mapped",
        )

    def test_multi_row_error_keeps_row_number(self):
        with self.assertRaises(
            RawItemsAdapterError
        ) as captured:
            adapt_raw_items_rows(
                (
                    {
                        "Article": "ARTICLE A",
                        "Qt\u00e9": 10,
                        "Client": "CLIENT A",
                    },
                    {
                        "Article": "ARTICLE B",
                        "Qt\u00e9": 20,
                    },
                ),
                source_truck_code="DCV-03",
                truck_mapping=self.mapping,
            )

        self.assertEqual(
            captured.exception.code,
            "row_adaptation_failed",
        )
        self.assertEqual(
            captured.exception.details[
                "row_number"
            ],
            2,
        )
        self.assertEqual(
            captured.exception.details[
                "cause_code"
            ],
            "missing_required_column",
        )
