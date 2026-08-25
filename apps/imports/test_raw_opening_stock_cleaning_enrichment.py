from django.test import TestCase

from apps.imports.models import (
    ImportSourceSystem,
    SourceProductPackaging,
)
from apps.imports.services.raw_opening_stock_cleaning_enrichment import (
    enrich_raw_opening_stock_cleaning_result,
)
from apps.imports.services.report_row_cleaner import (
    CleanedReportRow,
    ReportCleaningResult,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    STATUS_ACCEPTED,
    STATUS_EXCLUDED,
    STATUS_STOPPED,
)


class RawOpeningStockCleaningEnrichmentTests(
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

    def make_result(
        self,
        *,
        article="BALBON FRUITE",
        barcode="BAL-001",
        quantity=34,
        colisage=8,
        business_quantity="4:2",
        status=STATUS_ACCEPTED,
    ):
        return ReportCleaningResult(
            filename="DCV-03 opning stock.xlsx",
            report_type="OPENING_STOCK",
            rows=(
                CleanedReportRow(
                    row_number=2,
                    status=status,
                    raw_values=(
                        ("VAN", "BIFA LIV03"),
                        ("Qté", quantity),
                        ("Article", article),
                        ("Colisage", colisage),
                        ("العلبة", business_quantity),
                        ("Barcode", barcode),
                    ),
                    cleaned_values=(
                        ("van", "BIFA LIV03"),
                        ("article", article),
                        ("quantity", quantity),
                    ),
                    issues=(),
                ),
            ),
        )

    def test_ready_row_gets_exact_quantity_fields(
        self,
    ):
        result = (
            enrich_raw_opening_stock_cleaning_result(
                self.make_result(),
                source_system=self.source,
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
            cleaned["units_per_carton"],
            8,
        )
        self.assertEqual(
            cleaned["cartons"],
            4,
        )
        self.assertEqual(
            cleaned["pieces"],
            2,
        )
        self.assertEqual(
            cleaned["carton_quantity"],
            "4.25",
        )
        self.assertEqual(
            cleaned["source_quantity"],
            34,
        )
        self.assertEqual(
            cleaned["source_packaging"],
            8,
        )
        self.assertTrue(
            cleaned["quantity_matches_source"]
        )
        self.assertTrue(
            cleaned["packaging_matches_product"]
        )
        self.assertEqual(
            cleaned["product_packaging_id"],
            self.product.pk,
        )
        self.assertEqual(
            cleaned["product_match_method"],
            "barcode",
        )

    def test_quantity_mismatch_is_warning_not_block(
        self,
    ):
        result = (
            enrich_raw_opening_stock_cleaning_result(
                self.make_result(
                    quantity=33,
                ),
                source_system=self.source,
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

        issue = row.issues[-1]

        self.assertEqual(
            issue.severity,
            SEVERITY_WARNING,
        )
        self.assertEqual(
            issue.code,
            "opening_stock_source_quantity_mismatch",
        )

    def test_colisage_mismatch_is_warning_not_block(
        self,
    ):
        result = (
            enrich_raw_opening_stock_cleaning_result(
                self.make_result(
                    colisage=1,
                ),
                source_system=self.source,
            )
        )

        row = result.rows[0]
        cleaned = row.cleaned_dict()

        self.assertEqual(
            row.status,
            STATUS_ACCEPTED,
        )
        self.assertEqual(
            cleaned["units_per_carton"],
            8,
        )
        self.assertEqual(
            cleaned["source_packaging"],
            1,
        )

        issue = row.issues[-1]

        self.assertEqual(
            issue.severity,
            SEVERITY_WARNING,
        )
        self.assertEqual(
            issue.code,
            "opening_stock_source_packaging_mismatch",
        )

    def test_unknown_product_is_excluded(
        self,
    ):
        result = (
            enrich_raw_opening_stock_cleaning_result(
                self.make_result(
                    article="NEW PRODUCT",
                    barcode=None,
                ),
                source_system=self.source,
            )
        )

        row = result.rows[0]

        self.assertEqual(
            row.status,
            STATUS_EXCLUDED,
        )
        self.assertEqual(
            row.issues[-1].severity,
            SEVERITY_ERROR,
        )
        self.assertEqual(
            row.issues[-1].code,
            "opening_stock_unknown_product",
        )

    def test_missing_business_quantity_is_excluded(
        self,
    ):
        result = (
            enrich_raw_opening_stock_cleaning_result(
                self.make_result(
                    business_quantity=None,
                ),
                source_system=self.source,
            )
        )

        row = result.rows[0]

        self.assertEqual(
            row.status,
            STATUS_EXCLUDED,
        )
        self.assertEqual(
            row.issues[-1].severity,
            SEVERITY_ERROR,
        )
        self.assertEqual(
            row.issues[-1].code,
            (
                "opening_stock_"
                "missing_business_quantity"
            ),
        )

    def test_stopped_row_is_untouched(
        self,
    ):
        original = self.make_result(
            article=None,
            barcode=None,
            quantity=0,
            colisage=None,
            business_quantity=None,
            status=STATUS_STOPPED,
        )

        result = (
            enrich_raw_opening_stock_cleaning_result(
                original,
                source_system=self.source,
            )
        )

        self.assertEqual(
            result.rows[0],
            original.rows[0],
        )