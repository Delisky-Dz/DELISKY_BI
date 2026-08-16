from django.test import SimpleTestCase

from apps.imports.services.raw_chargement_adapter import (
    RawChargementAdapterError,
    adapt_raw_chargement_row,
    adapt_raw_chargement_rows,
)
from apps.imports.services.source_truck_mapper import (
    SourceTruckMappingError,
)


class RawChargementAdapterTests(SimpleTestCase):
    def test_adapts_multiple_rows_with_multiple_vans(self):
        result = adapt_raw_chargement_rows(
            [
                {
                    "Vers l'emplacement": "SOURCE A",
                    "Qt?": 10,
                    "Article": "ARTICLE A",
                },
                {
                    "Vers l'emplacement": "SOURCE B",
                    "Qt?": 20,
                    "Article": "ARTICLE B",
                },
                {
                    "Vers l'emplacement": "SOURCE A",
                    "Qt?": 30,
                    "Article": "ARTICLE C",
                },
            ],
            truck_mapping={
                "SOURCE A": "DELISKY LIV01",
                "SOURCE B": "NITA LIV01",
            },
        )

        self.assertEqual(
            result,
            (
                {
                    "VAN": "DELISKY LIV01",
                    "Qt?": 10,
                    "Article": "ARTICLE A",
                },
                {
                    "VAN": "NITA LIV01",
                    "Qt?": 20,
                    "Article": "ARTICLE B",
                },
                {
                    "VAN": "DELISKY LIV01",
                    "Qt?": 30,
                    "Article": "ARTICLE C",
                },
            ),
        )


    def test_multiple_rows_error_reports_failing_row_number(self):
        with self.assertRaises(
            RawChargementAdapterError
        ) as context:
            adapt_raw_chargement_rows(
                [
                    {
                        "Vers l'emplacement": "SOURCE A",
                        "Qt?": 10,
                        "Article": "ARTICLE A",
                    },
                    {
                        "Vers l'emplacement": "UNKNOWN",
                        "Qt?": 20,
                        "Article": "ARTICLE B",
                    },
                ],
                truck_mapping={
                    "SOURCE A": "DELISKY LIV01",
                },
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
            "source_truck_not_mapped",
        )


    def test_adapts_raw_chargement_row_to_canonical_columns(self):
        result = adapt_raw_chargement_row(
            {
                "Vers l'emplacement": "VAN-EXT-01",
                "Qt?": 12,
                "Article": "BISCUIT A",
            },
            truck_mapping={
                "VAN-EXT-01": "DELISKY LIV01",
            },
        )

        self.assertEqual(
            result,
            {
                "VAN": "DELISKY LIV01",
                "Qt?": 12,
                "Article": "BISCUIT A",
            },
        )

    def test_preserves_values_for_existing_cleaner(self):
        result = adapt_raw_chargement_row(
            {
                "Vers l'emplacement": "VAN-EXT-01",
                "Qt?": 0,
                "Article": None,
            },
            truck_mapping={
                "VAN-EXT-01": "NITA LIV01",
            },
        )

        self.assertEqual(result["Qt?"], 0)
        self.assertIsNone(result["Article"])

    def test_raw_header_matching_is_normalized(self):
        result = adapt_raw_chargement_row(
            {
                "  Vers l'emplacement  ": "SOURCE 01",
                "qt?": 5,
                " article ": "ARTICLE TEST",
            },
            truck_mapping={
                "SOURCE 01": "BIFA PSLIV01",
            },
        )

        self.assertEqual(
            result,
            {
                "VAN": "BIFA PSLIV01",
                "Qt?": 5,
                "Article": "ARTICLE TEST",
            },
        )

    def test_rejects_duplicate_normalized_raw_columns(self):
        with self.assertRaises(
            RawChargementAdapterError
        ) as context:
            adapt_raw_chargement_row(
                {
                    "Vers l'emplacement": "SOURCE 01",
                    "Qt?": 5,
                    " qt? ": 7,
                    "Article": "ARTICLE TEST",
                },
                truck_mapping={
                    "SOURCE 01": "DELISKY LIV01",
                },
            )

        self.assertEqual(
            context.exception.code,
            "duplicate_normalized_column",
        )


    def test_rejects_missing_required_raw_column(self):
        with self.assertRaises(
            RawChargementAdapterError
        ) as context:
            adapt_raw_chargement_row(
                {
                    "Vers l'emplacement": "SOURCE 01",
                    "Article": "ARTICLE TEST",
                },
                truck_mapping={
                    "SOURCE 01": "DELISKY LIV01",
                },
            )

        self.assertEqual(
            context.exception.code,
            "missing_required_column",
        )

    def test_unknown_source_truck_is_not_guessed(self):
        with self.assertRaises(SourceTruckMappingError):
            adapt_raw_chargement_row(
                {
                    "Vers l'emplacement": "UNKNOWN VAN",
                    "Qt?": 5,
                    "Article": "ARTICLE TEST",
                },
                truck_mapping={
                    "KNOWN VAN": "DELISKY LIV01",
                },
            )
