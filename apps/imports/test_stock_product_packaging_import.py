from io import BytesIO

from django.test import TestCase
from openpyxl import Workbook

from apps.imports.models import (
    ImportSourceSystem,
    SourceProductPackaging,
)
from apps.imports.services.stock_product_packaging_import import (
    StockProductPackagingImportError,
    import_stock_product_packaging_file,
)


class StockProductPackagingImportTests(TestCase):
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

    def make_file(
        self,
        rows,
        *,
        headers=None,
    ):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Classeur"

        worksheet.append(
            headers
            or [
                "Num",
                "Réf",
                "Barcode",
                "Désignation",
                "Colisage",
                "Activé",
            ]
        )

        for row in rows:
            worksheet.append(row)

        output = BytesIO()
        workbook.save(output)
        workbook.close()
        output.seek(0)

        return output

    def test_imports_valid_products(
        self,
    ):
        result = (
            import_stock_product_packaging_file(
                self.make_file(
                    [
                        [
                            1168,
                            "00720",
                            "BIS-00117",
                            "BESTO NOIRCO 4PCS",
                            24,
                            "True",
                        ],
                        [
                            619,
                            "03721",
                            "TCH-00052",
                            "STORY CHOCOLAT SPECULOOS",
                            4,
                            "True",
                        ],
                    ]
                ),
                source_system_code="BIFA_MILA",
            )
        )

        self.assertEqual(
            result.total_rows,
            2,
        )
        self.assertEqual(
            result.created_count,
            2,
        )
        self.assertEqual(
            result.review_required_count,
            0,
        )

        product = (
            SourceProductPackaging.objects.get(
                source_system=self.bifa,
                source_product_code="1168",
            )
        )

        self.assertEqual(
            product.units_per_carton,
            24,
        )
        self.assertEqual(
            product.barcode,
            "BIS-00117",
        )
        self.assertFalse(
            product.needs_review
        )

    def test_zero_colisage_requires_review(
        self,
    ):
        result = (
            import_stock_product_packaging_file(
                self.make_file(
                    [
                        [
                            1168,
                            "",
                            "BIS-00117",
                            "BESTO NOIRCO 4PCS",
                            0,
                            "True",
                        ],
                    ]
                ),
                source_system_code="AIO_WEB",
            )
        )

        product = (
            SourceProductPackaging.objects.get(
                source_system=self.aio,
                source_product_code="1168",
            )
        )

        self.assertIsNone(
            product.units_per_carton
        )
        self.assertTrue(
            product.needs_review
        )
        self.assertEqual(
            result.review_required_count,
            1,
        )
        self.assertEqual(
            result.review_items[0].reason,
            "unknown_units_per_carton",
        )

    def test_same_file_is_idempotent(
        self,
    ):
        rows = [
            [
                100,
                "REF-1",
                "BAR-1",
                "PRODUCT ONE",
                12,
                "True",
            ],
        ]

        import_stock_product_packaging_file(
            self.make_file(rows),
            source_system_code="BIFA_MILA",
        )

        second = (
            import_stock_product_packaging_file(
                self.make_file(rows),
                source_system_code="BIFA_MILA",
            )
        )

        self.assertEqual(
            SourceProductPackaging.objects.count(),
            1,
        )
        self.assertEqual(
            second.created_count,
            0,
        )
        self.assertEqual(
            second.updated_count,
            0,
        )
        self.assertEqual(
            second.unchanged_count,
            1,
        )

    def test_existing_product_is_updated(
        self,
    ):
        SourceProductPackaging.objects.create(
            source_system=self.bifa,
            source_product_code="100",
            barcode="OLD",
            designation="OLD PRODUCT",
            units_per_carton=10,
            needs_review=False,
        )

        result = (
            import_stock_product_packaging_file(
                self.make_file(
                    [
                        [
                            100,
                            "NEW-REF",
                            "NEW-BAR",
                            "NEW PRODUCT",
                            20,
                            "True",
                        ],
                    ]
                ),
                source_system_code="BIFA_MILA",
            )
        )

        product = (
            SourceProductPackaging.objects.get(
                source_system=self.bifa,
                source_product_code="100",
            )
        )

        self.assertEqual(
            result.updated_count,
            1,
        )
        self.assertEqual(
            product.units_per_carton,
            20,
        )
        self.assertEqual(
            product.designation,
            "NEW PRODUCT",
        )
        self.assertEqual(
            product.barcode,
            "NEW-BAR",
        )

    def test_normalizes_non_breaking_spaces(
        self,
    ):
        import_stock_product_packaging_file(
            self.make_file(
                [
                    [
                        773,
                        "",
                        "",
                        (
                            "CAPRICE\u00a0LIQUIDE"
                            "\u00a0CHOCO"
                        ),
                        12,
                        "True",
                    ],
                ]
            ),
            source_system_code="AIO_WEB",
        )

        product = (
            SourceProductPackaging.objects.get(
                source_system=self.aio,
                source_product_code="773",
            )
        )

        self.assertEqual(
            product.designation,
            "CAPRICE LIQUIDE CHOCO",
        )

    def test_rejects_missing_required_header(
        self,
    ):
        with self.assertRaises(
            StockProductPackagingImportError
        ) as context:
            import_stock_product_packaging_file(
                self.make_file(
                    [],
                    headers=[
                        "Num",
                        "Désignation",
                        "Activé",
                    ],
                ),
                source_system_code="BIFA_MILA",
            )

        self.assertEqual(
            context.exception.code,
            "missing_required_headers",
        )

    def test_rejects_duplicate_num_in_same_file(
        self,
    ):
        with self.assertRaises(
            StockProductPackagingImportError
        ) as context:
            import_stock_product_packaging_file(
                self.make_file(
                    [
                        [
                            100,
                            "",
                            "",
                            "PRODUCT A",
                            12,
                            "True",
                        ],
                        [
                            100,
                            "",
                            "",
                            "PRODUCT B",
                            24,
                            "True",
                        ],
                    ]
                ),
                source_system_code="BIFA_MILA",
            )

        self.assertEqual(
            context.exception.code,
            "duplicate_source_product_code",
        )

        self.assertEqual(
            SourceProductPackaging.objects.count(),
            0,
        )