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
            cleaned["product_packaging_id"],
            self.product.pk,
        )
        self.assertEqual(
            cleaned["source_quantity"],
            34,
        )
        self.assertTrue(
            cleaned["quantity_matches_source"]
        )

        # Legacy cleaner value remains the source Qte.
        # Qte and total_units represent the same units.
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
            33,
        )
        self.assertEqual(
            cleaned["cartons"],
            4,
        )
        self.assertEqual(
            cleaned["pieces"],
            1,
        )
        self.assertEqual(
            cleaned["source_quantity"],
            33,
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

    def test_negative_qte_is_excluded_without_blocking_error(
        self,
    ):
        original = self.cleaning_result(
            quantity=-2,
            status=STATUS_EXCLUDED,
        )

        original_row = original.rows[0]

        original = ReportCleaningResult(
            filename=original.filename,
            report_type=original.report_type,
            rows=(
                CleanedReportRow(
                    row_number=original_row.row_number,
                    status=STATUS_EXCLUDED,
                    raw_values=original_row.raw_values,
                    cleaned_values=(
                        original_row.cleaned_values
                    ),
                    issues=(),
                ),
            ),
        )

        result = (
            enrich_raw_items_cleaning_result(
                original,
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
            "INVALID_BUSINESS_QUANTITY",
        )

        self.assertIsNone(
            cleaned["total_units"],
        )

        self.assertFalse(
            any(
                issue.code
                == "items_invalid_business_quantity"
                for issue in row.issues
            )
        )

    def test_ambiguous_product_consensus_is_accepted_with_warning(
        self,
    ):
        SourceProductPackaging.objects.create(
            source_system=self.source,
            source_product_code="CONS-001",
            barcode="CONS-A",
            designation="CONSENSUS PRODUCT",
            units_per_carton=8,
            needs_review=False,
            is_active=True,
        )

        SourceProductPackaging.objects.create(
            source_system=self.source,
            source_product_code="CONS-002",
            barcode="CONS-B",
            designation="CONSENSUS PRODUCT",
            units_per_carton=8,
            needs_review=False,
            is_active=True,
        )

        result = (
            enrich_raw_items_cleaning_result(
                self.cleaning_result(
                    article="CONSENSUS PRODUCT",
                    barcode="",
                    quantity=18,
                    nbre_carton="2:2",
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
            "AMBIGUOUS_PRODUCT",
        )
        self.assertEqual(
            cleaned["total_units"],
            18,
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
            2,
        )
        self.assertIsNone(
            cleaned["product_packaging_id"],
        )
        self.assertEqual(
            cleaned["product_match_method"],
            "designation",
        )

        self.assertTrue(
            any(
                issue.code
                == "items_ambiguous_product"
                and issue.severity
                == "WARNING"
                for issue in row.issues
            )
        )

    def test_ambiguous_product_without_consensus_remains_excluded(
        self,
    ):
        SourceProductPackaging.objects.create(
            source_system=self.source,
            source_product_code="NO-CONS-001",
            barcode="NO-CONS-A",
            designation="NO CONSENSUS PRODUCT",
            units_per_carton=8,
            needs_review=False,
            is_active=True,
        )

        SourceProductPackaging.objects.create(
            source_system=self.source,
            source_product_code="NO-CONS-002",
            barcode="NO-CONS-B",
            designation="NO CONSENSUS PRODUCT",
            units_per_carton=10,
            needs_review=False,
            is_active=True,
        )

        result = (
            enrich_raw_items_cleaning_result(
                self.cleaning_result(
                    article="NO CONSENSUS PRODUCT",
                    barcode="",
                    quantity=20,
                ),
                source_system=self.source,
            )
        )

        row = result.rows[0]

        self.assertEqual(
            row.status,
            STATUS_EXCLUDED,
        )

        self.assertTrue(
            any(
                issue.code
                == "items_ambiguous_product"
                and issue.severity
                == "ERROR"
                for issue in row.issues
            )
        )
