from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.imports.models import (
    ImportSourceSystem,
    SourceProductPackaging,
)


class SourceProductPackagingModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bifa = ImportSourceSystem.objects.create(
            code="BIFA_MILA",
            name="BIFA Mila",
            is_active=True,
        )

        cls.aio = ImportSourceSystem.objects.create(
            code="AIO_WEB",
            name="AIO Web",
            is_active=True,
        )

    def test_normalizes_source_identity_and_designation(
        self,
    ):
        product = SourceProductPackaging(
            source_system=self.bifa,
            source_product_code="  1168  ",
            barcode=" bis-00117 ",
            reference=" ref-01 ",
            designation="  BESTO   NOIRCO 4PCS ",
            units_per_carton=24,
            needs_review=False,
        )

        product.full_clean()
        product.save()

        self.assertEqual(
            product.source_product_code,
            "1168",
        )
        self.assertEqual(
            product.barcode,
            "BIS-00117",
        )
        self.assertEqual(
            product.reference,
            "REF-01",
        )
        self.assertEqual(
            product.designation,
            "BESTO NOIRCO 4PCS",
        )
        self.assertEqual(
            product.normalized_designation,
            "BESTO NOIRCO 4PCS",
        )
        self.assertEqual(
            product.units_per_carton,
            24,
        )
        self.assertFalse(
            product.needs_review
        )

    def test_unknown_packaging_requires_review(
        self,
    ):
        product = SourceProductPackaging(
            source_system=self.aio,
            source_product_code="2001",
            designation="NEW PRODUCT",
            units_per_carton=None,
            needs_review=False,
        )

        product.full_clean()

        self.assertTrue(
            product.needs_review
        )
        self.assertIsNone(
            product.units_per_carton
        )

    def test_zero_units_per_carton_is_invalid(
        self,
    ):
        product = SourceProductPackaging(
            source_system=self.bifa,
            source_product_code="3001",
            designation="BAD PACKAGING",
            units_per_carton=0,
        )

        with self.assertRaises(
            ValidationError
        ):
            product.full_clean()

    def test_same_source_product_code_is_unique_per_source(
        self,
    ):
        SourceProductPackaging.objects.create(
            source_system=self.bifa,
            source_product_code="ABC-1",
            designation="PRODUCT ONE",
            units_per_carton=12,
            needs_review=False,
        )

        duplicate = SourceProductPackaging(
            source_system=self.bifa,
            source_product_code=" abc-1 ",
            designation="PRODUCT TWO",
            units_per_carton=24,
            needs_review=False,
        )

        with self.assertRaises(
            ValidationError
        ):
            duplicate.full_clean()

    def test_same_source_code_is_allowed_in_another_system(
        self,
    ):
        SourceProductPackaging.objects.create(
            source_system=self.bifa,
            source_product_code="ABC-1",
            designation="BIFA PRODUCT",
            units_per_carton=20,
            needs_review=False,
        )

        product = SourceProductPackaging(
            source_system=self.aio,
            source_product_code="ABC-1",
            designation="AIO PRODUCT",
            units_per_carton=1,
            needs_review=False,
        )

        product.full_clean()
        product.save()

        self.assertIsNotNone(
            product.pk
        )

    def test_duplicate_barcode_and_designation_are_allowed(
        self,
    ):
        SourceProductPackaging.objects.create(
            source_system=self.aio,
            source_product_code="5001",
            barcode="SAME-BARCODE",
            designation="SAME PRODUCT",
            units_per_carton=20,
            needs_review=False,
        )

        second = SourceProductPackaging(
            source_system=self.aio,
            source_product_code="5002",
            barcode="SAME-BARCODE",
            designation="SAME PRODUCT",
            units_per_carton=20,
            needs_review=False,
        )

        second.full_clean()
        second.save()

        self.assertEqual(
            SourceProductPackaging.objects.filter(
                source_system=self.aio,
                barcode="SAME-BARCODE",
            ).count(),
            2,
        )