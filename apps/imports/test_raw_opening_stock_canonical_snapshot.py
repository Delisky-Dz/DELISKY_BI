from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from openpyxl import Workbook

from apps.imports.services.raw_opening_stock_adapter import (
    adapt_raw_opening_stock_row,
)
from apps.imports.services.raw_opening_stock_cleaning_enrichment import (
    enrich_raw_opening_stock_cleaning_result,
)
from apps.imports.services.raw_opening_stock_file import (
    adapt_raw_opening_stock_file,
)
from apps.imports.services.raw_opening_stock_quantity_enrichment import (
    OpeningStockQuantityStatus,
    enrich_raw_opening_stock_quantity,
)
from apps.imports.services.report_row_cleaner import (
    CleanedReportRow,
    ReportCleaningResult,
    STATUS_ACCEPTED,
)
from apps.imports.services.source_product_packaging_resolver import (
    PackagingResolution,
    PackagingResolutionStatus,
)


class CanonicalOpeningStockSnapshotTests(
    SimpleTestCase
):
    def ready_resolution(
        self,
        *,
        units_per_carton=8,
    ):
        product = SimpleNamespace(
            units_per_carton=units_per_carton,
            pk=101,
        )

        return PackagingResolution(
            status=PackagingResolutionStatus.READY,
            product=product,
            match_method="designation",
            candidates_count=1,
        )

    def test_canonical_row_preserves_van(self):
        result = adapt_raw_opening_stock_row(
            {
                "VAN": "BIFA LIV03",
                "Qt\u00e9": 34,
                "Article": "ARTICLE A",
            },
            source_truck_code="NOT-MAPPED",
            truck_mapping={},
        )

        self.assertEqual(
            result,
            {
                "VAN": "BIFA LIV03",
                "Qt\u00e9": 34,
                "Article": "ARTICLE A",
            },
        )

    def test_canonical_file_supports_multiple_vans(
        self,
    ):
        workbook = Workbook()
        worksheet = workbook.active

        worksheet.append(
            [
                "VAN",
                "Qt\u00e9",
                "Article",
            ]
        )
        worksheet.append(
            [
                "BIFA LIV01",
                34,
                "ARTICLE A",
            ]
        )
        worksheet.append(
            [
                "BIFA LIV03",
                17,
                "ARTICLE B",
            ]
        )

        output = BytesIO()
        workbook.save(output)
        workbook.close()
        output.seek(0)

        result = adapt_raw_opening_stock_file(
            output,
            truck_mapping={},
            original_filename=(
                "OpeningStock_BIFA_2026-04-03.xlsx"
            ),
        )

        self.assertEqual(
            len(result.rows),
            2,
        )
        self.assertEqual(
            result.rows[0].values["VAN"],
            "BIFA LIV01",
        )
        self.assertEqual(
            result.rows[1].values["VAN"],
            "BIFA LIV03",
        )

    @patch(
        "apps.imports.services."
        "raw_opening_stock_quantity_enrichment."
        "resolve_source_product_packaging"
    )
    def test_canonical_quantity_uses_total_units(
        self,
        resolver,
    ):
        resolver.return_value = (
            self.ready_resolution(
                units_per_carton=8,
            )
        )

        result = enrich_raw_opening_stock_quantity(
            {
                "Article": "ARTICLE A",
                "Qt\u00e9": 34,
            },
            source_system=SimpleNamespace(),
            source_quantity_is_authoritative=True,
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
        self.assertTrue(
            result.source_quantity_authoritative
        )

    @patch(
        "apps.imports.services."
        "raw_opening_stock_quantity_enrichment."
        "resolve_source_product_packaging"
    )
    def test_cleaning_enrichment_detects_canonical_mode(
        self,
        resolver,
    ):
        resolver.return_value = (
            self.ready_resolution(
                units_per_carton=8,
            )
        )

        original = ReportCleaningResult(
            filename=(
                "OpeningStock_BIFA_2026-04-03.xlsx"
            ),
            report_type="OPENING_STOCK",
            rows=(
                CleanedReportRow(
                    row_number=2,
                    status=STATUS_ACCEPTED,
                    raw_values=(
                        ("VAN", "BIFA LIV03"),
                        ("Qt\u00e9", 34),
                        ("Article", "ARTICLE A"),
                    ),
                    cleaned_values=(
                        ("van", "BIFA LIV03"),
                        (
                            "van_normalized",
                            "bifa liv03",
                        ),
                        ("article", "ARTICLE A"),
                        (
                            "article_normalized",
                            "article a",
                        ),
                        ("quantity", 34),
                    ),
                    issues=(),
                ),
            ),
        )

        result = (
            enrich_raw_opening_stock_cleaning_result(
                original,
                source_system=SimpleNamespace(),
            )
        )

        row = result.rows[0]
        cleaned = row.cleaned_dict()

        self.assertEqual(
            row.status,
            STATUS_ACCEPTED,
        )
        self.assertEqual(
            cleaned["total_units"],
            34,
        )
        self.assertEqual(
            cleaned["cartons"],
            4,
        )
        self.assertEqual(
            cleaned["pieces"],
            2,
        )
        self.assertIsNone(
            cleaned["business_quantity_raw"]
        )
        self.assertIsNone(
            cleaned["source_packaging"]
        )

    @patch(
        "apps.imports.services."
        "raw_opening_stock_quantity_enrichment."
        "resolve_source_product_packaging"
    )
    def test_canonical_ambiguous_product_uses_packaging_consensus(
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
            consensus_units_per_carton=8,
        )

        original = ReportCleaningResult(
            filename=(
                "OpeningStock_NITA_2026-04-03.xlsx"
            ),
            report_type="OPENING_STOCK",
            rows=(
                CleanedReportRow(
                    row_number=2,
                    status=STATUS_ACCEPTED,
                    raw_values=(
                        ("VAN", "NITA LIV01"),
                        ("Qt\u00e9", 19),
                        (
                            "Article",
                            "AMBIGUOUS ARTICLE",
                        ),
                    ),
                    cleaned_values=(
                        ("van", "NITA LIV01"),
                        (
                            "van_normalized",
                            "nita liv01",
                        ),
                        (
                            "article",
                            "AMBIGUOUS ARTICLE",
                        ),
                        (
                            "article_normalized",
                            "ambiguous article",
                        ),
                        ("quantity", 19),
                    ),
                    issues=(),
                ),
            ),
        )

        result = (
            enrich_raw_opening_stock_cleaning_result(
                original,
                source_system=SimpleNamespace(),
            )
        )

        row = result.rows[0]
        cleaned = row.cleaned_dict()

        self.assertEqual(
            row.status,
            STATUS_ACCEPTED,
        )
        self.assertEqual(
            cleaned["total_units"],
            19,
        )
        self.assertEqual(
            cleaned["units_per_carton"],
            8,
        )
        self.assertEqual(
            cleaned["cartons"],
            2,
        )
        self.assertEqual(
            cleaned["pieces"],
            3,
        )
        self.assertIsNone(
            cleaned["product_packaging_id"]
        )
        self.assertTrue(
            cleaned["packaging_consensus_used"]
        )
        self.assertEqual(
            len(row.issues),
            1,
        )
        self.assertEqual(
            row.issues[0].code,
            (
                "opening_stock_ambiguous_product_"
                "packaging_consensus"
            ),
        )
        self.assertEqual(
            row.issues[0].severity,
            "WARNING",
        )

    def test_old_mode_still_requires_business_quantity(
        self,
    ):
        result = enrich_raw_opening_stock_quantity(
            {
                "Article": "ARTICLE A",
                "Qt\u00e9": 34,
                "Colisage": 8,
            },
            source_system=SimpleNamespace(),
        )

        self.assertEqual(
            result.status,
            (
                OpeningStockQuantityStatus
                .MISSING_BUSINESS_QUANTITY
            ),
        )
