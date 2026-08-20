from django.test import SimpleTestCase

from apps.imports.services.raw_sales_adapter import (
    RawSalesAdapterError,
    adapt_raw_sales_row,
    adapt_raw_sales_rows,
)


class RawSalesAdapterTests(SimpleTestCase):
    def setUp(self):
        self.mapping = {
            "DCV-03": "BIFA LIV03",
            "DLV-01": "BIFA PLIV01",
            "VAN1-DELISKY": "DELISKY LIV01",
            "VAN1-NITA": "NITA LIV01",
        }

    def test_adapts_bifa_sales_row(self):
        result = adapt_raw_sales_row(
            {
                "Cle": "VDD-18550",
                "Date&Heure": "18/08/2026 12:57:44",
                "Nom du client": "Test Client",
                "Versement": "41889.2",
                "Total": "41889.2",
                "Region": "EX TAJNANET",
                "NET": "41889.2",
            },
            source_truck_code="DCV-03",
            truck_mapping=self.mapping,
        )

        self.assertEqual(
            result,
            {
                "VAN": "BIFA LIV03",
                "Date&Heure": "18/08/2026 12:57:44",
                "Nom du client": "Test Client",
                "Total": "41889.2",
                "Region": "EX TAJNANET",
            },
        )

    def test_adapts_aio_sales_row(self):
        result = adapt_raw_sales_row(
            {
                "Date&Heure": "18/08/2026 12:49:51",
                "Nom du client": "Test Client",
                "Total": 2946,
                "Versement": 2946,
                "Region": "EL MCHIRA",
                "NET": 2946,
            },
            source_truck_code="VAN1-NITA",
            truck_mapping=self.mapping,
        )

        self.assertEqual(
            result["VAN"],
            "NITA LIV01",
        )
        self.assertEqual(
            result["Total"],
            2946,
        )
        self.assertEqual(
            result["Region"],
            "EL MCHIRA",
        )

    def test_region_header_is_required(self):
        with self.assertRaises(
            RawSalesAdapterError
        ) as context:
            adapt_raw_sales_row(
                {
                    "Date&Heure": "18/08/2026 12:00:00",
                    "Nom du client": "Test Client",
                    "Total": 100,
                },
                source_truck_code="DCV-03",
                truck_mapping=self.mapping,
            )

        self.assertEqual(
            context.exception.code,
            "missing_required_column",
        )
        self.assertEqual(
            context.exception.details["column"],
            "Region",
        )

    def test_unmapped_source_truck_is_rejected(self):
        with self.assertRaises(
            Exception
        ) as context:
            adapt_raw_sales_row(
                {
                    "Date&Heure": "18/08/2026 12:00:00",
                    "Nom du client": "Test Client",
                    "Total": 100,
                    "Region": "MILA",
                },
                source_truck_code="UNKNOWN-01",
                truck_mapping=self.mapping,
            )

        self.assertEqual(
            context.exception.code,
            "source_truck_not_mapped",
        )

    def test_multi_row_error_preserves_row_number(self):
        with self.assertRaises(
            RawSalesAdapterError
        ) as context:
            adapt_raw_sales_rows(
                (
                    {
                        "Date&Heure": "18/08/2026 10:00:00",
                        "Nom du client": "Client A",
                        "Total": 100,
                        "Region": "MILA",
                    },
                    {
                        "Date&Heure": "18/08/2026 11:00:00",
                        "Nom du client": "Client B",
                        "Total": 200,
                    },
                ),
                source_truck_code="DLV-01",
                truck_mapping=self.mapping,
            )

        self.assertEqual(
            context.exception.code,
            "row_adaptation_failed",
        )
        self.assertEqual(
            context.exception.details["row_number"],
            2,
        )
        self.assertEqual(
            context.exception.details["cause_code"],
            "missing_required_column",
        )
