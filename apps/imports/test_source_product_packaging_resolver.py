from django.test import TestCase

from apps.imports.models import (
    ImportSourceSystem,
    SourceProductAlias,
    SourceProductPackaging,
)
from apps.imports.services.source_product_packaging_resolver import (
    PackagingResolutionStatus,
    resolve_source_product_packaging,
)


class SourceProductPackagingResolverTests(
    TestCase
):
    @classmethod
    def setUpTestData(cls):
        cls.source = (
            ImportSourceSystem.objects.create(
                code="AIO_WEB",
                name="AIO Web",
                is_active=True,
            )
        )

    def create_product(
        self,
        *,
        code,
        designation,
        barcode="",
        units=20,
        needs_review=False,
        active=True,
    ):
        return (
            SourceProductPackaging.objects.create(
                source_system=self.source,
                source_product_code=code,
                barcode=barcode,
                designation=designation,
                normalized_designation=(
                    designation.upper()
                ),
                units_per_carton=units,
                needs_review=needs_review,
                is_active=active,
            )
        )

    def test_resolves_unique_barcode(self):
        product = self.create_product(
            code="1",
            designation="PRODUCT ONE",
            barcode="ABC-001",
            units=24,
        )

        result = resolve_source_product_packaging(
            source_system=self.source,
            barcode="abc-001",
            designation="Different text",
        )

        self.assertEqual(
            result.status,
            PackagingResolutionStatus.READY,
        )
        self.assertEqual(
            result.product,
            product,
        )
        self.assertEqual(
            result.match_method,
            "barcode",
        )

    def test_falls_back_to_designation(self):
        product = self.create_product(
            code="2",
            designation="MARUJA",
            units=20,
        )

        result = resolve_source_product_packaging(
            source_system=self.source,
            designation="  maruja ",
        )

        self.assertEqual(
            result.status,
            PackagingResolutionStatus.READY,
        )
        self.assertEqual(
            result.product,
            product,
        )
        self.assertEqual(
            result.match_method,
            "designation",
        )

    def test_unknown_product(self):
        result = resolve_source_product_packaging(
            source_system=self.source,
            designation="NEW PRODUCT",
        )

        self.assertEqual(
            result.status,
            PackagingResolutionStatus.UNKNOWN_PRODUCT,
        )
        self.assertIsNone(
            result.product
        )

    def test_known_product_unknown_packaging(self):
        product = self.create_product(
            code="3",
            designation="UNKNOWN PACK",
            units=None,
            needs_review=True,
        )

        result = resolve_source_product_packaging(
            source_system=self.source,
            designation="UNKNOWN PACK",
        )

        self.assertEqual(
            result.status,
            PackagingResolutionStatus.UNKNOWN_PACKAGING,
        )
        self.assertEqual(
            result.product,
            product,
        )
        self.assertIsNone(
            result.units_per_carton
        )

    def test_duplicate_designation_is_ambiguous(
        self,
    ):
        self.create_product(
            code="10",
            designation="SAME PRODUCT",
            barcode="BAR-10",
        )
        self.create_product(
            code="11",
            designation="SAME PRODUCT",
            barcode="BAR-11",
        )

        result = resolve_source_product_packaging(
            source_system=self.source,
            designation="SAME PRODUCT",
        )

        self.assertEqual(
            result.status,
            PackagingResolutionStatus.AMBIGUOUS_PRODUCT,
        )
        self.assertEqual(
            result.candidates_count,
            2,
        )
        self.assertEqual(
            result.consensus_units_per_carton,
            20,
        )

    def test_duplicate_designation_with_different_packaging_has_no_consensus(
        self,
    ):
        self.create_product(
            code="12",
            designation="MIXED PACK",
            barcode="BAR-12",
            units=6,
        )
        self.create_product(
            code="13",
            designation="MIXED PACK",
            barcode="BAR-13",
            units=8,
        )

        result = resolve_source_product_packaging(
            source_system=self.source,
            designation="MIXED PACK",
        )

        self.assertEqual(
            result.status,
            PackagingResolutionStatus.AMBIGUOUS_PRODUCT,
        )
        self.assertEqual(
            result.candidates_count,
            2,
        )
        self.assertIsNone(
            result.consensus_units_per_carton
        )

    def test_barcode_and_name_disambiguate(
        self,
    ):
        product = self.create_product(
            code="20",
            designation="PRODUCT A",
            barcode="SHARED",
        )

        self.create_product(
            code="21",
            designation="PRODUCT B",
            barcode="SHARED",
        )

        result = resolve_source_product_packaging(
            source_system=self.source,
            barcode="SHARED",
            designation="PRODUCT A",
        )

        self.assertEqual(
            result.status,
            PackagingResolutionStatus.READY,
        )
        self.assertEqual(
            result.product,
            product,
        )
        self.assertEqual(
            result.match_method,
            "barcode+designation",
        )

    def test_resolves_explicit_product_alias(
        self,
    ):
        product = self.create_product(
            code="40",
            designation=(
                "NITA DOPPIO VANILLE FRAISE"
            ),
            barcode="GAU-00049",
            units=1,
        )

        alias = SourceProductAlias.objects.create(
            source_system=self.source,
            product=product,
            alias=(
                "  nita doppio vanilla strawberry  "
            ),
        )

        self.assertEqual(
            alias.normalized_alias,
            "NITA DOPPIO VANILLA STRAWBERRY",
        )

        result = resolve_source_product_packaging(
            source_system=self.source,
            designation=(
                "NITA DOPPIO VANILLA STRAWBERRY"
            ),
        )

        self.assertEqual(
            result.status,
            PackagingResolutionStatus.READY,
        )
        self.assertEqual(
            result.product,
            product,
        )
        self.assertEqual(
            result.match_method,
            "alias",
        )
        self.assertEqual(
            result.units_per_carton,
            1,
        )

    def test_inactive_alias_is_not_resolved(
        self,
    ):
        product = self.create_product(
            code="41",
            designation="CURRENT NAME",
            units=6,
        )

        SourceProductAlias.objects.create(
            source_system=self.source,
            product=product,
            alias="OLD NAME",
            is_active=False,
        )

        result = resolve_source_product_packaging(
            source_system=self.source,
            designation="OLD NAME",
        )

        self.assertEqual(
            result.status,
            PackagingResolutionStatus.UNKNOWN_PRODUCT,
        )

    def test_exact_designation_precedes_alias(
        self,
    ):
        exact_product = self.create_product(
            code="42",
            designation="SHARED NAME",
            units=4,
        )

        alias_product = self.create_product(
            code="43",
            designation="OTHER PRODUCT",
            units=8,
        )

        SourceProductAlias.objects.create(
            source_system=self.source,
            product=alias_product,
            alias="SHARED NAME",
        )

        result = resolve_source_product_packaging(
            source_system=self.source,
            designation="SHARED NAME",
        )

        self.assertEqual(
            result.status,
            PackagingResolutionStatus.READY,
        )
        self.assertEqual(
            result.product,
            exact_product,
        )
        self.assertEqual(
            result.match_method,
            "designation",
        )

    def test_alias_rejects_product_from_other_source(
        self,
    ):
        other_source = (
            ImportSourceSystem.objects.create(
                code="OTHER",
                name="Other",
                is_active=True,
            )
        )

        other_product = (
            SourceProductPackaging.objects.create(
                source_system=other_source,
                source_product_code="44",
                designation="OTHER PRODUCT",
                normalized_designation=(
                    "OTHER PRODUCT"
                ),
                units_per_carton=1,
                needs_review=False,
                is_active=True,
            )
        )

        with self.assertRaisesMessage(
            Exception,
            (
                "Alias and product must belong "
                "to the same source system."
            ),
        ):
            SourceProductAlias.objects.create(
                source_system=self.source,
                product=other_product,
                alias="BAD ALIAS",
            )

    def test_inactive_product_is_not_resolved(
        self,
    ):
        self.create_product(
            code="30",
            designation="OLD PRODUCT",
            barcode="OLD-1",
            active=False,
        )

        result = resolve_source_product_packaging(
            source_system=self.source,
            barcode="OLD-1",
            designation="OLD PRODUCT",
        )

        self.assertEqual(
            result.status,
            PackagingResolutionStatus.UNKNOWN_PRODUCT,
        )