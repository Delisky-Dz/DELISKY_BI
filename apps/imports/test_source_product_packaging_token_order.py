from django.test import TestCase

from apps.imports.models import (
    ImportSourceSystem,
    SourceProductPackaging,
)
from apps.imports.services.source_product_packaging_resolver import (
    PackagingResolutionStatus,
    normalize_product_text,
    resolve_source_product_packaging,
)


class SourceProductPackagingTokenOrderTests(
    TestCase
):
    def setUp(self):
        self.source = (
            ImportSourceSystem.objects.create(
                code="TOKEN_TEST",
                name="Token Test",
                is_active=True,
            )
        )

    def create_product(
        self,
        *,
        code,
        designation,
        units_per_carton=8,
        needs_review=False,
    ):
        return SourceProductPackaging.objects.create(
            source_system=self.source,
            source_product_code=code,
            barcode="",
            designation=designation,
            normalized_designation=(
                normalize_product_text(
                    designation
                )
            ),
            units_per_carton=units_per_carton,
            needs_review=needs_review,
            is_active=True,
        )

    def test_unique_reordered_designation_resolves(
        self,
    ):
        product = self.create_product(
            code="1480",
            designation=(
                "SWAREEN SCUSA 600G CHOCOLAT"
            ),
            units_per_carton=8,
        )

        result = resolve_source_product_packaging(
            source_system=self.source,
            designation=(
                "SWAREEN SCUSA CHOCOLAT 600G"
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
            "designation_tokens",
        )
        self.assertEqual(
            result.candidates_count,
            1,
        )

    def test_exact_designation_keeps_priority(
        self,
    ):
        exact = self.create_product(
            code="EXACT",
            designation=(
                "SWAREEN SCUSA CHOCOLAT 600G"
            ),
        )

        self.create_product(
            code="REORDERED",
            designation=(
                "SWAREEN SCUSA 600G CHOCOLAT"
            ),
        )

        result = resolve_source_product_packaging(
            source_system=self.source,
            designation=(
                "SWAREEN SCUSA CHOCOLAT 600G"
            ),
        )

        self.assertEqual(
            result.status,
            PackagingResolutionStatus.READY,
        )
        self.assertEqual(
            result.product,
            exact,
        )
        self.assertEqual(
            result.match_method,
            "designation",
        )

    def test_token_collision_is_ambiguous(
        self,
    ):
        self.create_product(
            code="A",
            designation="ALPHA BETA 600G",
        )

        self.create_product(
            code="B",
            designation="BETA 600G ALPHA",
        )

        result = resolve_source_product_packaging(
            source_system=self.source,
            designation="600G ALPHA BETA",
        )

        self.assertEqual(
            result.status,
            (
                PackagingResolutionStatus
                .AMBIGUOUS_PRODUCT
            ),
        )
        self.assertIsNone(
            result.product
        )
        self.assertEqual(
            result.match_method,
            "designation_tokens",
        )
        self.assertEqual(
            result.candidates_count,
            2,
        )

    def test_reordered_unknown_packaging_stays_blocked(
        self,
    ):
        product = self.create_product(
            code="NO-PACK",
            designation=(
                "SWAREEN SCUSA 750G CHOCOLAT"
            ),
            units_per_carton=None,
            needs_review=True,
        )

        result = resolve_source_product_packaging(
            source_system=self.source,
            designation=(
                "SWAREEN SCUSA CHOCOLAT 750G"
            ),
        )

        self.assertEqual(
            result.status,
            (
                PackagingResolutionStatus
                .UNKNOWN_PACKAGING
            ),
        )
        self.assertEqual(
            result.product,
            product,
        )
        self.assertEqual(
            result.match_method,
            "designation_tokens",
        )

    def test_unrelated_product_remains_unknown(
        self,
    ):
        self.create_product(
            code="KNOWN",
            designation="KNOWN PRODUCT 600G",
        )

        result = resolve_source_product_packaging(
            source_system=self.source,
            designation="OTHER PRODUCT 600G",
        )

        self.assertEqual(
            result.status,
            (
                PackagingResolutionStatus
                .UNKNOWN_PRODUCT
            ),
        )
        self.assertIsNone(
            result.product
        )
