from decimal import Decimal

from django.test import TestCase

from apps.imports.models import (
    ImportSourceSystem,
    SourceProductPackaging,
)
from apps.imports.services.raw_items_quantity_enrichment import (
    ItemsQuantityStatus,
    QTY_SOLD_FIELD,
    enrich_raw_items_quantity,
)


class RawItemsQuantityEnrichmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.source = ImportSourceSystem.objects.create(
            code="BIFA_MILA",
            name="BIFA Mila",
            is_active=True,
        )

        cls.product = SourceProductPackaging.objects.create(
            source_system=cls.source,
            source_product_code="100",
            barcode="BAL-001",
            designation="BALBON FRUITE",
            normalized_designation="BALBON FRUITE",
            units_per_carton=8,
            needs_review=False,
            is_active=True,
        )

    def test_qte_total_units_are_authoritative(self):
        result = enrich_raw_items_quantity(
            {
                "Article": "BALBON FRUITE",
                "Barcode": "BAL-001",
                QTY_SOLD_FIELD: 4,
            },
            source_system=self.source,
        )

        self.assertEqual(
            result.status,
            ItemsQuantityStatus.READY,
        )
        self.assertEqual(result.total_units, 4)
        self.assertEqual(result.units_per_carton, 8)
        self.assertEqual(result.cartons, 0)
        self.assertEqual(result.pieces, 4)
        self.assertEqual(
            result.carton_quantity,
            Decimal("0.5"),
        )
        self.assertTrue(
            result.quantity_matches_source
        )

    def test_fractional_total_units_are_rejected(self):
        result = enrich_raw_items_quantity(
            {
                "Article": "BALBON FRUITE",
                "Barcode": "BAL-001",
                QTY_SOLD_FIELD: "4.25",
            },
            source_system=self.source,
        )

        self.assertEqual(
            result.status,
            ItemsQuantityStatus.INVALID_BUSINESS_QUANTITY,
        )
        self.assertIsNone(result.total_units)
        self.assertEqual(
            result.error_code,
            "fractional_total_units",
        )

    def test_nbre_carton_is_not_authoritative(self):
        result = enrich_raw_items_quantity(
            {
                "Article": "BALBON FRUITE",
                "Barcode": "BAL-001",
                QTY_SOLD_FIELD: 33,
                "Nbre carton": "4:2",
            },
            source_system=self.source,
        )

        self.assertEqual(
            result.status,
            ItemsQuantityStatus.READY,
        )
        self.assertEqual(result.total_units, 33)
        self.assertEqual(result.cartons, 4)
        self.assertEqual(result.pieces, 1)
        self.assertEqual(
            result.source_total_units,
            33,
        )
        self.assertTrue(
            result.quantity_matches_source
        )

    def test_unknown_product_is_not_guessed(self):
        result = enrich_raw_items_quantity(
            {
                "Article": "NEW PRODUCT",
                QTY_SOLD_FIELD: 20,
            },
            source_system=self.source,
        )

        self.assertEqual(
            result.status,
            ItemsQuantityStatus.UNKNOWN_PRODUCT,
        )
        self.assertIsNone(result.total_units)

    def test_unknown_packaging_is_not_guessed(self):
        SourceProductPackaging.objects.create(
            source_system=self.source,
            source_product_code="200",
            barcode="UNK-001",
            designation="UNKNOWN PACK",
            normalized_designation="UNKNOWN PACK",
            units_per_carton=None,
            needs_review=True,
            is_active=True,
        )

        result = enrich_raw_items_quantity(
            {
                "Article": "UNKNOWN PACK",
                "Barcode": "UNK-001",
                QTY_SOLD_FIELD: 10,
            },
            source_system=self.source,
        )

        self.assertEqual(
            result.status,
            ItemsQuantityStatus.UNKNOWN_PACKAGING,
        )
        self.assertIsNone(result.total_units)

    def test_missing_qte_is_reported(self):
        result = enrich_raw_items_quantity(
            {
                "Article": "BALBON FRUITE",
                "Barcode": "BAL-001",
            },
            source_system=self.source,
        )

        self.assertEqual(
            result.status,
            ItemsQuantityStatus.MISSING_BUSINESS_QUANTITY,
        )
        self.assertIsNone(result.total_units)
        self.assertEqual(
            result.error_code,
            "missing_items_total_units",
        )

    def test_invalid_qte_is_reported(self):
        result = enrich_raw_items_quantity(
            {
                "Article": "BALBON FRUITE",
                "Barcode": "BAL-001",
                QTY_SOLD_FIELD: "BAD",
            },
            source_system=self.source,
        )

        self.assertEqual(
            result.status,
            ItemsQuantityStatus.INVALID_BUSINESS_QUANTITY,
        )
        self.assertIsNone(result.total_units)
        self.assertEqual(
            result.error_code,
            "invalid_quantity",
        )

    def test_negative_qte_is_rejected(self):
        result = enrich_raw_items_quantity(
            {
                "Article": "BALBON FRUITE",
                "Barcode": "BAL-001",
                QTY_SOLD_FIELD: -2,
            },
            source_system=self.source,
        )

        self.assertEqual(
            result.status,
            ItemsQuantityStatus.INVALID_BUSINESS_QUANTITY,
        )
        self.assertIsNone(result.total_units)
        self.assertEqual(
            result.error_code,
            "negative_business_quantity",
        )

    def test_barcode_resolution_is_used(self):
        result = enrich_raw_items_quantity(
            {
                "Article": "DIFFERENT NAME",
                "Barcode": "BAL-001",
                QTY_SOLD_FIELD: 1,
            },
            source_system=self.source,
        )

        self.assertEqual(
            result.status,
            ItemsQuantityStatus.READY,
        )
        self.assertEqual(result.product, self.product)
        self.assertEqual(
            result.match_method,
            "barcode",
        )
        self.assertEqual(result.total_units, 1)

    def test_real_items_total_unit_regression_examples(
        self,
    ):
        product_48 = (
            SourceProductPackaging.objects.create(
                source_system=self.source,
                source_product_code="REAL-48",
                barcode="REAL-UPC-48",
                designation="REAL PRODUCT UPC 48",
                units_per_carton=48,
                needs_review=False,
                is_active=True,
            )
        )

        product_18 = (
            SourceProductPackaging.objects.create(
                source_system=self.source,
                source_product_code="REAL-18",
                barcode="REAL-UPC-18",
                designation="REAL PRODUCT UPC 18",
                units_per_carton=18,
                needs_review=False,
                is_active=True,
            )
        )

        quantity_144 = enrich_raw_items_quantity(
            {
                "Article":
                    product_48.designation,
                "Barcode":
                    product_48.barcode,
                QTY_SOLD_FIELD: 144,
            },
            source_system=self.source,
        )

        self.assertEqual(
            quantity_144.status,
            ItemsQuantityStatus.READY,
        )
        self.assertEqual(
            quantity_144.total_units,
            144,
        )
        self.assertEqual(
            quantity_144.cartons,
            3,
        )
        self.assertEqual(
            quantity_144.pieces,
            0,
        )

        quantity_54 = enrich_raw_items_quantity(
            {
                "Article":
                    product_18.designation,
                "Barcode":
                    product_18.barcode,
                QTY_SOLD_FIELD: 54,
            },
            source_system=self.source,
        )

        self.assertEqual(
            quantity_54.status,
            ItemsQuantityStatus.READY,
        )
        self.assertEqual(
            quantity_54.total_units,
            54,
        )
        self.assertEqual(
            quantity_54.cartons,
            3,
        )
        self.assertEqual(
            quantity_54.pieces,
            0,
        )
