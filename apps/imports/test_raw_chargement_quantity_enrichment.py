from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.imports.services.raw_chargement_quantity_enrichment import (
    ChargementQuantityStatus,
    enrich_raw_chargement_quantity,
)
from apps.imports.services.source_product_packaging_resolver import (
    PackagingResolution,
    PackagingResolutionStatus,
)


class RawChargementQuantityEnrichmentTests(
    SimpleTestCase
):
    def _product(
        self,
        *,
        units_per_carton=18,
    ):
        return SimpleNamespace(
            pk=101,
            units_per_carton=units_per_carton,
        )

    def _ready_resolution(
        self,
        *,
        units_per_carton=18,
        match_method="barcode",
    ):
        return PackagingResolution(
            status=PackagingResolutionStatus.READY,
            product=self._product(
                units_per_carton=units_per_carton
            ),
            match_method=match_method,
            candidates_count=1,
        )

    @patch(
        "apps.imports.services."
        "raw_chargement_quantity_enrichment."
        "resolve_source_product_packaging"
    )
    def test_ready_quantity_uses_qte_as_total_units(
        self,
        resolver,
    ):
        resolver.return_value = (
            self._ready_resolution(
                units_per_carton=18
            )
        )

        source_system = object()

        result = enrich_raw_chargement_quantity(
            {
                "Article": "AVANTAGE",
                "Barcode": "BIS-00010",
                "Qt\u00e9": 54,
            },
            source_system=source_system,
        )

        self.assertEqual(
            result.status,
            ChargementQuantityStatus.READY,
        )
        self.assertEqual(result.total_units, 54)
        self.assertEqual(result.units_per_carton, 18)
        self.assertEqual(result.cartons, 3)
        self.assertEqual(result.pieces, 0)

        resolver.assert_called_once_with(
            source_system=source_system,
            barcode="BIS-00010",
            designation="AVANTAGE",
        )

    @patch(
        "apps.imports.services."
        "raw_chargement_quantity_enrichment."
        "resolve_source_product_packaging"
    )
    def test_ready_quantity_preserves_piece_remainder(
        self,
        resolver,
    ):
        resolver.return_value = (
            self._ready_resolution(
                units_per_carton=8
            )
        )

        result = enrich_raw_chargement_quantity(
            {
                "Article": "BALBON FRUITE",
                "Barcode": "COF-00002",
                "Qt\u00e9": 34,
            },
            source_system=object(),
        )

        self.assertEqual(result.total_units, 34)
        self.assertEqual(result.cartons, 4)
        self.assertEqual(result.pieces, 2)

    @patch(
        "apps.imports.services."
        "raw_chargement_quantity_enrichment."
        "resolve_source_product_packaging"
    )
    def test_negative_chargement_quantity_is_preserved(
        self,
        resolver,
    ):
        resolver.return_value = (
            self._ready_resolution(
                units_per_carton=8
            )
        )

        result = enrich_raw_chargement_quantity(
            {
                "Article": "PRODUCT",
                "Qt\u00e9": -34,
            },
            source_system=object(),
        )

        self.assertEqual(
            result.status,
            ChargementQuantityStatus.READY,
        )
        self.assertEqual(result.total_units, -34)
        self.assertEqual(result.cartons, -4)
        self.assertEqual(result.pieces, -2)

    @patch(
        "apps.imports.services."
        "raw_chargement_quantity_enrichment."
        "resolve_source_product_packaging"
    )
    def test_fractional_quantity_is_invalid(
        self,
        resolver,
    ):
        result = enrich_raw_chargement_quantity(
            {
                "Article": "PRODUCT",
                "Qt\u00e9": "1,5",
            },
            source_system=object(),
        )

        self.assertEqual(
            result.status,
            ChargementQuantityStatus.INVALID_QUANTITY,
        )
        self.assertIsNone(result.total_units)
        resolver.assert_not_called()

    @patch(
        "apps.imports.services."
        "raw_chargement_quantity_enrichment."
        "resolve_source_product_packaging"
    )
    def test_unknown_product_keeps_known_total_units(
        self,
        resolver,
    ):
        resolver.return_value = PackagingResolution(
            status=(
                PackagingResolutionStatus
                .UNKNOWN_PRODUCT
            ),
            product=None,
            match_method=None,
            candidates_count=0,
        )

        result = enrich_raw_chargement_quantity(
            {
                "Article": "UNKNOWN",
                "Qt\u00e9": 12,
            },
            source_system=object(),
        )

        self.assertEqual(
            result.status,
            ChargementQuantityStatus.UNKNOWN_PRODUCT,
        )
        self.assertEqual(result.total_units, 12)
        self.assertIsNone(result.units_per_carton)

    @patch(
        "apps.imports.services."
        "raw_chargement_quantity_enrichment."
        "resolve_source_product_packaging"
    )
    def test_unknown_packaging_keeps_total_units(
        self,
        resolver,
    ):
        product = self._product(
            units_per_carton=None
        )

        resolver.return_value = PackagingResolution(
            status=(
                PackagingResolutionStatus
                .UNKNOWN_PACKAGING
            ),
            product=product,
            match_method="designation",
            candidates_count=1,
        )

        result = enrich_raw_chargement_quantity(
            {
                "Article": "PRODUCT",
                "Qt\u00e9": 20,
            },
            source_system=object(),
        )

        self.assertEqual(
            result.status,
            ChargementQuantityStatus.UNKNOWN_PACKAGING,
        )
        self.assertEqual(result.total_units, 20)
        self.assertIsNone(result.units_per_carton)

    @patch(
        "apps.imports.services."
        "raw_chargement_quantity_enrichment."
        "resolve_source_product_packaging"
    )
    def test_ambiguous_product_blocks_packaging(
        self,
        resolver,
    ):
        resolver.return_value = PackagingResolution(
            status=(
                PackagingResolutionStatus
                .AMBIGUOUS_PRODUCT
            ),
            product=None,
            match_method="designation",
            candidates_count=2,
        )

        result = enrich_raw_chargement_quantity(
            {
                "Article": "PRODUCT",
                "Qt\u00e9": 20,
            },
            source_system=object(),
        )

        self.assertEqual(
            result.status,
            ChargementQuantityStatus.AMBIGUOUS_PRODUCT,
        )
        self.assertEqual(result.total_units, 20)
        self.assertIsNone(result.cartons)

    @patch(
        "apps.imports.services."
        "raw_chargement_quantity_enrichment."
        "resolve_source_product_packaging"
    )
    def test_non_numeric_quantity_is_invalid(
        self,
        resolver,
    ):
        result = enrich_raw_chargement_quantity(
            {
                "Article": "PRODUCT",
                "Qt\u00e9": "abc",
            },
            source_system=object(),
        )

        self.assertEqual(
            result.status,
            ChargementQuantityStatus.INVALID_QUANTITY,
        )
        resolver.assert_not_called()
