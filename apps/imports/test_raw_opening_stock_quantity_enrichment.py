from decimal import Decimal

from django.test import TestCase

from apps.imports.models import (
    ImportSourceSystem,
    SourceProductPackaging,
)
from apps.imports.services.raw_opening_stock_quantity_enrichment import (
    OpeningStockQuantityStatus,
    enrich_raw_opening_stock_quantity,
)


class RawOpeningStockQuantityEnrichmentTests(
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

    def test_mixed_business_quantity_is_authoritative(
        self,
    ):
        result = (
            enrich_raw_opening_stock_quantity(
                {
                    "Article":
                        "BALBON FRUITE",
                    "Barcode": "BAL-001",
                    "Qté": 34,
                    "Colisage": 8,
                    "العلبة": "4:2",
                },
                source_system=self.source,
            )
        )

        self.assertEqual(
            result.status,
            OpeningStockQuantityStatus.READY,
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
        self.assertTrue(
            result.packaging_matches_product
        )

    def test_numeric_business_quantity(
        self,
    ):
        result = (
            enrich_raw_opening_stock_quantity(
                {
                    "Article":
                        "BALBON FRUITE",
                    "Barcode": "BAL-001",
                    "Qté": 16,
                    "Colisage": 8,
                    "العلبة": 2,
                },
                source_system=self.source,
            )
        )

        self.assertEqual(
            result.status,
            OpeningStockQuantityStatus.READY,
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

    def test_business_quantity_wins_on_source_quantity_mismatch(
        self,
    ):
        result = (
            enrich_raw_opening_stock_quantity(
                {
                    "Article":
                        "BALBON FRUITE",
                    "Barcode": "BAL-001",
                    "Qté": 33,
                    "Colisage": 8,
                    "العلبة": "4:2",
                },
                source_system=self.source,
            )
        )

        self.assertEqual(
            result.status,
            (
                OpeningStockQuantityStatus
                .SOURCE_QUANTITY_MISMATCH
            ),
        )
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

    def test_product_master_wins_on_colisage_mismatch(
        self,
    ):
        result = (
            enrich_raw_opening_stock_quantity(
                {
                    "Article":
                        "BALBON FRUITE",
                    "Barcode": "BAL-001",
                    "Qté": 34,
                    "Colisage": 1,
                    "العلبة": "4:2",
                },
                source_system=self.source,
            )
        )

        self.assertEqual(
            result.status,
            (
                OpeningStockQuantityStatus
                .SOURCE_PACKAGING_MISMATCH
            ),
        )
        self.assertEqual(
            result.units_per_carton,
            8,
        )
        self.assertEqual(
            result.source_units_per_carton,
            1,
        )
        self.assertEqual(
            result.total_units,
            34,
        )
        self.assertFalse(
            result.packaging_matches_product
        )

    def test_both_source_values_can_mismatch(
        self,
    ):
        result = (
            enrich_raw_opening_stock_quantity(
                {
                    "Article":
                        "BALBON FRUITE",
                    "Barcode": "BAL-001",
                    "Qté": 33,
                    "Colisage": 1,
                    "العلبة": "4:2",
                },
                source_system=self.source,
            )
        )

        self.assertEqual(
            result.status,
            (
                OpeningStockQuantityStatus
                .SOURCE_QUANTITY_AND_PACKAGING_MISMATCH
            ),
        )
        self.assertEqual(
            result.total_units,
            34,
        )

    def test_unknown_product_is_not_guessed(
        self,
    ):
        result = (
            enrich_raw_opening_stock_quantity(
                {
                    "Article":
                        "NEW PRODUCT",
                    "Qté": 20,
                    "Colisage": 10,
                    "العلبة": 2,
                },
                source_system=self.source,
            )
        )

        self.assertEqual(
            result.status,
            (
                OpeningStockQuantityStatus
                .UNKNOWN_PRODUCT
            ),
        )
        self.assertIsNone(
            result.total_units
        )

    def test_unknown_product_packaging_is_not_guessed(
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

        result = (
            enrich_raw_opening_stock_quantity(
                {
                    "Article":
                        "UNKNOWN PACK",
                    "Barcode": "UNK-001",
                    "Qté": 10,
                    "Colisage": 10,
                    "العلبة": 1,
                },
                source_system=self.source,
            )
        )

        self.assertEqual(
            result.status,
            (
                OpeningStockQuantityStatus
                .UNKNOWN_PACKAGING
            ),
        )
        self.assertIsNone(
            result.total_units
        )

    def test_missing_business_quantity_is_reported(
        self,
    ):
        result = (
            enrich_raw_opening_stock_quantity(
                {
                    "Article":
                        "BALBON FRUITE",
                    "Barcode": "BAL-001",
                    "Qté": 34,
                    "Colisage": 8,
                },
                source_system=self.source,
            )
        )

        self.assertEqual(
            result.status,
            (
                OpeningStockQuantityStatus
                .MISSING_BUSINESS_QUANTITY
            ),
        )

    def test_invalid_business_quantity_is_reported(
        self,
    ):
        result = (
            enrich_raw_opening_stock_quantity(
                {
                    "Article":
                        "BALBON FRUITE",
                    "Barcode": "BAL-001",
                    "Qté": 40,
                    "Colisage": 8,
                    "العلبة": "4:8",
                },
                source_system=self.source,
            )
        )

        self.assertEqual(
            result.status,
            (
                OpeningStockQuantityStatus
                .INVALID_BUSINESS_QUANTITY
            ),
        )
        self.assertEqual(
            result.error_code,
            "pieces_exceed_carton_size",
        )

    def test_invalid_source_quantity_keeps_business_quantity(
        self,
    ):
        result = (
            enrich_raw_opening_stock_quantity(
                {
                    "Article":
                        "BALBON FRUITE",
                    "Barcode": "BAL-001",
                    "Qté": "BAD",
                    "Colisage": 8,
                    "العلبة": "4:2",
                },
                source_system=self.source,
            )
        )

        self.assertEqual(
            result.status,
            (
                OpeningStockQuantityStatus
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

    def test_invalid_source_colisage_keeps_business_quantity(
        self,
    ):
        result = (
            enrich_raw_opening_stock_quantity(
                {
                    "Article":
                        "BALBON FRUITE",
                    "Barcode": "BAL-001",
                    "Qté": 34,
                    "Colisage": 0,
                    "العلبة": "4:2",
                },
                source_system=self.source,
            )
        )

        self.assertEqual(
            result.status,
            (
                OpeningStockQuantityStatus
                .INVALID_SOURCE_PACKAGING
            ),
        )
        self.assertEqual(
            result.total_units,
            34,
        )
        self.assertEqual(
            result.units_per_carton,
            8,
        )

    def test_designation_fallback_supports_blank_barcode(
        self,
    ):
        result = (
            enrich_raw_opening_stock_quantity(
                {
                    "Article":
                        "BALBON FRUITE",
                    "Barcode": None,
                    "Qté": 34,
                    "Colisage": 8,
                    "العلبة": "4:2",
                },
                source_system=self.source,
            )
        )

        self.assertEqual(
            result.status,
            OpeningStockQuantityStatus.READY,
        )
        self.assertEqual(
            result.product,
            self.product,
        )
        self.assertEqual(
            result.match_method,
            "designation",
        )