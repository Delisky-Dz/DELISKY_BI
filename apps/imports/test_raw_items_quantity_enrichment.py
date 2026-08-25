from decimal import Decimal

from django.test import TestCase

from apps.imports.models import (
    ImportSourceSystem,
    SourceProductPackaging,
)
from apps.imports.services.raw_items_quantity_enrichment import (
    ItemsQuantityStatus,
    enrich_raw_items_quantity,
)


class RawItemsQuantityEnrichmentTests(
    TestCase
):
    @classmethod
    def setUpTestData(cls):
        cls.source = (
            ImportSourceSystem.objects.create(
                code="BIFA_MILA",
                name="BIFA Mila",
                is_active=True,
            )
        )

        cls.product = (
            SourceProductPackaging.objects.create(
                source_system=cls.source,
                source_product_code="100",
                barcode="BAL-001",
                designation="BALBON FRUITE",
                units_per_carton=8,
                needs_review=False,
                is_active=True,
            )
        )

    def test_mixed_carton_piece_is_official_quantity(
        self,
    ):
        result = enrich_raw_items_quantity(
            {
                "Article": "BALBON FRUITE",
                "Barcode": "BAL-001",
                "Qté vendue": 34,
                "Nbre carton": "4:2",
            },
            source_system=self.source,
        )

        self.assertEqual(
            result.status,
            ItemsQuantityStatus.READY,
        )
        self.assertEqual(
            result.total_units,
            34,
        )
        self.assertEqual(
            result.units_per_carton,
            8,
        )
        self.assertEqual(
            result.cartons,
            4,
        )
        self.assertEqual(
            result.pieces,
            2,
        )
        self.assertEqual(
            result.carton_quantity,
            Decimal("4.25"),
        )
        self.assertTrue(
            result.quantity_matches_source
        )

    def test_numeric_carton_quantity(self):
        result = enrich_raw_items_quantity(
            {
                "Article": "BALBON FRUITE",
                "Barcode": "BAL-001",
                "Qté vendue": 16,
                "Nbre carton": 2,
            },
            source_system=self.source,
        )

        self.assertEqual(
            result.status,
            ItemsQuantityStatus.READY,
        )
        self.assertEqual(
            result.total_units,
            16,
        )
        self.assertEqual(
            result.cartons,
            2,
        )
        self.assertEqual(
            result.pieces,
            0,
        )

    def test_nbre_carton_remains_authoritative_on_mismatch(
        self,
    ):
        result = enrich_raw_items_quantity(
            {
                "Article": "BALBON FRUITE",
                "Barcode": "BAL-001",
                "Qté vendue": 33,
                "Nbre carton": "4:2",
            },
            source_system=self.source,
        )

        self.assertEqual(
            result.status,
            (
                ItemsQuantityStatus
                .SOURCE_QUANTITY_MISMATCH
            ),
        )

        # Official business quantity still comes
        # from Nbre carton, not Qté.
        self.assertEqual(
            result.total_units,
            34,
        )
        self.assertEqual(
            result.source_total_units,
            33,
        )
        self.assertFalse(
            result.quantity_matches_source
        )

    def test_unknown_product_is_not_guessed(self):
        result = enrich_raw_items_quantity(
            {
                "Article": "NEW PRODUCT",
                "Qté vendue": 20,
                "Nbre carton": 1,
            },
            source_system=self.source,
        )

        self.assertEqual(
            result.status,
            ItemsQuantityStatus.UNKNOWN_PRODUCT,
        )
        self.assertIsNone(
            result.total_units
        )

    def test_unknown_packaging_is_not_guessed(
        self,
    ):
        SourceProductPackaging.objects.create(
            source_system=self.source,
            source_product_code="200",
            barcode="UNK-001",
            designation="UNKNOWN PACK",
            units_per_carton=None,
            needs_review=True,
            is_active=True,
        )

        result = enrich_raw_items_quantity(
            {
                "Article": "UNKNOWN PACK",
                "Barcode": "UNK-001",
                "Qté vendue": 10,
                "Nbre carton": 1,
            },
            source_system=self.source,
        )

        self.assertEqual(
            result.status,
            ItemsQuantityStatus.UNKNOWN_PACKAGING,
        )
        self.assertIsNone(
            result.total_units
        )

    def test_missing_nbre_carton_is_reported(
        self,
    ):
        result = enrich_raw_items_quantity(
            {
                "Article": "BALBON FRUITE",
                "Barcode": "BAL-001",
                "Qté vendue": 34,
            },
            source_system=self.source,
        )

        self.assertEqual(
            result.status,
            (
                ItemsQuantityStatus
                .MISSING_BUSINESS_QUANTITY
            ),
        )
        self.assertIsNone(
            result.total_units
        )

    def test_invalid_mixed_quantity_is_reported(
        self,
    ):
        result = enrich_raw_items_quantity(
            {
                "Article": "BALBON FRUITE",
                "Barcode": "BAL-001",
                "Qté vendue": 40,
                "Nbre carton": "4:8",
            },
            source_system=self.source,
        )

        self.assertEqual(
            result.status,
            (
                ItemsQuantityStatus
                .INVALID_BUSINESS_QUANTITY
            ),
        )
        self.assertEqual(
            result.error_code,
            "pieces_exceed_carton_size",
        )

    def test_invalid_source_quantity_does_not_replace_business_quantity(
        self,
    ):
        result = enrich_raw_items_quantity(
            {
                "Article": "BALBON FRUITE",
                "Barcode": "BAL-001",
                "Qté vendue": "BAD",
                "Nbre carton": "4:2",
            },
            source_system=self.source,
        )

        self.assertEqual(
            result.status,
            (
                ItemsQuantityStatus
                .INVALID_SOURCE_QUANTITY
            ),
        )
        self.assertEqual(
            result.total_units,
            34,
        )
        self.assertIsNone(
            result.source_total_units
        )

    def test_barcode_resolution_is_used(
        self,
    ):
        result = enrich_raw_items_quantity(
            {
                "Article": "DIFFERENT NAME",
                "Barcode": "BAL-001",
                "Qté vendue": 8,
                "Nbre carton": 1,
            },
            source_system=self.source,
        )

        self.assertEqual(
            result.status,
            ItemsQuantityStatus.READY,
        )
        self.assertEqual(
            result.product,
            self.product,
        )
        self.assertEqual(
            result.match_method,
            "barcode",
        )