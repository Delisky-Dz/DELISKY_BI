from django.test import TestCase

from apps.imports.models import (
    ImportSourceSystem,
    SourceProductPackaging,
)
from apps.imports.services.raw_items_cleaning_enrichment import (
    enrich_raw_items_cleaning_result,
)
from apps.imports.services.report_row_cleaner import (
    CleanedReportRow,
    ReportCleaningResult,
    STATUS_ACCEPTED,
    STATUS_EXCLUDED,
    STATUS_STOPPED,
)


class RawItemsCleaningEnrichmentTests(
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

    def cleaning_result(
        self,
        *,
        article="BALBON FRUITE",
        barcode="BAL-001",
        quantity=34,
        nbre_carton="4:2",
        status=STATUS_ACCEPTED,
    ):
        return ReportCleaningResult(
            filename="DCV-03 items.xlsx",
            report_type="ITEMS",
            rows=(
                CleanedReportRow(
                    row_number=2,
                    status=status,
                    raw_values=(
                        ("VAN", "BIFA-LIV03"),
                        ("Article", article),
                        ("Qté vendue", quantity),
                        ("Client", "CLIENT A"),
                        (
                            "Nbre carton",
                            nbre_carton,
                        ),
                        ("Barcode", barcode),
                    ),
                    cleaned_values=(
                        ("van", "BIFA-LIV03"),
                        (
                            "van_normalized",
                            "BIFA-LIV03",
                        ),
                        ("article", article),
                        (
                            "article_normalized",
                            article.upper(),
                        ),
                        (
                            "quantity_sold",
                            quantity,
                        ),
                        ("client", "CLIENT A"),
                        (
                            "client_normalized",
                            "CLIENT A",
                        ),
                    ),
                    issues=(),
                ),
            ),
        )

    def test_ready_row_gets_exact_quantity_fields(
        self,
    ):
        result = (
            enrich_raw_items_cleaning_result(
                self.cleaning_result(),
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
            272,
        )
        self.assertEqual(
            cleaned["units_per_carton"],
            8,
        )
        self.assertEqual(
            cleaned["cartons"],
            34,
        )
        self.assertEqual(
            cleaned["pieces"],
            0,
        )
        self.assertEqual(
            cleaned["carton_quantity"],
            "34",
        )
        self.assertEqual(
            cleaned["product_packaging_id"],
            self.product.pk,
        )
        self.assertEqual(
            cleaned["source_quantity"],
            272,
        )
        self.assertTrue(
            cleaned["quantity_matches_source"]
        )

        # Legacy cleaner value remains the source Qte
        # carton count; Analytics uses total_units.
        self.assertEqual(
            cleaned["quantity_sold"],
            34,
        )

    def test_nbre_carton_is_ignored_for_items_quantity(
        self,
    ):
        result = (
            enrich_raw_items_cleaning_result(
                self.cleaning_result(
                    quantity=33,
                    nbre_carton="4:2",
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
            264,
        )
        self.assertEqual(
            cleaned["cartons"],
            33,
        )
        self.assertEqual(
            cleaned["pieces"],
            0,
        )
        self.assertEqual(
            cleaned["source_quantity"],
            264,
        )
        self.assertTrue(
            cleaned["quantity_matches_source"]
        )
        self.assertEqual(
            cleaned["packaging_status"],
            "READY",
        )

    def test_unknown_product_is_blocked(
        self,
    ):
        result = (
            enrich_raw_items_cleaning_result(
                self.cleaning_result(
                    article="NEW PRODUCT",
                    barcode="",
                    quantity=20,
                    nbre_carton=1,
                ),
                source_system=self.source,
            )
        )

        row = result.rows[0]
        cleaned = row.cleaned_dict()

        self.assertEqual(
            row.status,
            STATUS_EXCLUDED,
        )
        self.assertEqual(
            cleaned["packaging_status"],
            "UNKNOWN_PRODUCT",
        )
        self.assertIsNone(
            cleaned["total_units"]
        )
        self.assertEqual(
            row.issues[-1].severity,
            "ERROR",
        )

    def test_missing_nbre_carton_does_not_block_qte(
        self,
    ):
        result = (
            enrich_raw_items_cleaning_result(
                self.cleaning_result(
                    nbre_carton=None,
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
            cleaned["packaging_status"],
            "READY",
        )
        self.assertEqual(
            cleaned["total_units"],
            272,
        )
        self.assertEqual(
            cleaned["cartons"],
            34,
        )
        self.assertEqual(
            cleaned["pieces"],
            0,
        )

    def test_stopped_row_is_left_untouched(
        self,
    ):
        original = self.cleaning_result(
            status=STATUS_STOPPED,
        )

        result = (
            enrich_raw_items_cleaning_result(
                original,
                source_system=self.source,
            )
        )

        self.assertEqual(
            result.rows[0],
            original.rows[0],
        )