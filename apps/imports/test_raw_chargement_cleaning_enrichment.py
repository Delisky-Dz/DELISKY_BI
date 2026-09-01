from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.imports.services.raw_chargement_cleaning_enrichment import (
    enrich_raw_chargement_cleaning_result,
)
from apps.imports.services.raw_chargement_quantity_enrichment import (
    ChargementQuantityEnrichment,
    ChargementQuantityStatus,
)
from apps.imports.services.report_row_cleaner import (
    CleanedReportRow,
    ReportCleaningResult,
    STATUS_ACCEPTED,
    STATUS_EXCLUDED,
    STATUS_STOPPED,
)


class RawChargementCleaningEnrichmentTests(
    SimpleTestCase
):
    def _row(
        self,
        *,
        status=STATUS_ACCEPTED,
        quantity=34,
        article="BALBON FRUITE",
        barcode="COF-00002",
    ):
        return CleanedReportRow(
            row_number=2,
            status=status,
            raw_values=(
                ("VAN", "BIFA-LIV03"),
                ("Qt\u00e9", quantity),
                ("Article", article),
                ("Barcode", barcode),
            ),
            cleaned_values=(
                ("van", "BIFA-LIV03"),
                ("van_normalized", "BIFA-LIV03"),
                ("article", article),
                (
                    "article_normalized",
                    article,
                ),
                (
                    "quantity",
                    Decimal(str(quantity)),
                ),
            ),
            issues=(),
        )

    def _result(
        self,
        row,
    ):
        return ReportCleaningResult(
            filename="chargement.xlsx",
            report_type="CHARGEMENT",
            rows=(row,),
        )

    def _enrichment(
        self,
        *,
        status=ChargementQuantityStatus.READY,
        total_units=34,
        units_per_carton=8,
        cartons=4,
        pieces=2,
        product=True,
        error_code=None,
    ):
        product_obj = None

        if product:
            product_obj = SimpleNamespace(
                pk=101,
                units_per_carton=units_per_carton,
            )

        return ChargementQuantityEnrichment(
            status=status,
            product=product_obj,
            match_method=(
                "barcode"
                if product_obj is not None
                else None
            ),
            quantity_raw=total_units,
            units_per_carton=units_per_carton,
            total_units=total_units,
            carton_quantity=(
                Decimal(total_units)
                / Decimal(units_per_carton)
                if (
                    total_units is not None
                    and units_per_carton
                )
                else None
            ),
            cartons=cartons,
            pieces=pieces,
            error_code=error_code,
        )

    @patch(
        "apps.imports.services."
        "raw_chargement_cleaning_enrichment."
        "enrich_raw_chargement_quantity"
    )
    def test_ready_row_adds_exact_quantity_fields(
        self,
        enrich_quantity,
    ):
        enrich_quantity.return_value = (
            self._enrichment()
        )

        source_system = object()

        result = (
            enrich_raw_chargement_cleaning_result(
                self._result(
                    self._row()
                ),
                source_system=source_system,
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
            cleaned["packaging_status"],
            "READY",
        )
        self.assertEqual(
            cleaned["product_packaging_id"],
            101,
        )

        enrich_quantity.assert_called_once_with(
            {
                "Article": "BALBON FRUITE",
                "Barcode": "COF-00002",
                "Qt\u00e9": 34,
            },
            source_system=source_system,
        )

    @patch(
        "apps.imports.services."
        "raw_chargement_cleaning_enrichment."
        "enrich_raw_chargement_quantity"
    )
    def test_unknown_product_excludes_row(
        self,
        enrich_quantity,
    ):
        enrich_quantity.return_value = (
            self._enrichment(
                status=(
                    ChargementQuantityStatus
                    .UNKNOWN_PRODUCT
                ),
                product=False,
                units_per_carton=None,
                cartons=None,
                pieces=None,
                error_code="UNKNOWN_PRODUCT",
            )
        )

        result = (
            enrich_raw_chargement_cleaning_result(
                self._result(
                    self._row()
                ),
                source_system=object(),
            )
        )

        row = result.rows[0]

        self.assertEqual(
            row.status,
            STATUS_EXCLUDED,
        )
        self.assertEqual(
            row.issues[-1].code,
            "chargement_unknown_product",
        )

    @patch(
        "apps.imports.services."
        "raw_chargement_cleaning_enrichment."
        "enrich_raw_chargement_quantity"
    )
    def test_unknown_packaging_excludes_row(
        self,
        enrich_quantity,
    ):
        enrich_quantity.return_value = (
            self._enrichment(
                status=(
                    ChargementQuantityStatus
                    .UNKNOWN_PACKAGING
                ),
                units_per_carton=None,
                cartons=None,
                pieces=None,
                error_code="UNKNOWN_PACKAGING",
            )
        )

        result = (
            enrich_raw_chargement_cleaning_result(
                self._result(
                    self._row()
                ),
                source_system=object(),
            )
        )

        self.assertEqual(
            result.rows[0].status,
            STATUS_EXCLUDED,
        )
        self.assertEqual(
            result.rows[0].issues[-1].code,
            "chargement_unknown_packaging",
        )

    @patch(
        "apps.imports.services."
        "raw_chargement_cleaning_enrichment."
        "enrich_raw_chargement_quantity"
    )
    def test_ambiguous_product_excludes_row(
        self,
        enrich_quantity,
    ):
        enrich_quantity.return_value = (
            self._enrichment(
                status=(
                    ChargementQuantityStatus
                    .AMBIGUOUS_PRODUCT
                ),
                product=False,
                units_per_carton=None,
                cartons=None,
                pieces=None,
                error_code="AMBIGUOUS_PRODUCT",
            )
        )

        result = (
            enrich_raw_chargement_cleaning_result(
                self._result(
                    self._row()
                ),
                source_system=object(),
            )
        )

        self.assertEqual(
            result.rows[0].status,
            STATUS_EXCLUDED,
        )

    @patch(
        "apps.imports.services."
        "raw_chargement_cleaning_enrichment."
        "enrich_raw_chargement_quantity"
    )
    def test_ambiguous_product_consensus_is_accepted_with_warning(
        self,
        enrich_quantity,
    ):
        from decimal import Decimal
        from types import SimpleNamespace

        enrich_quantity.return_value = SimpleNamespace(
            status=(
                ChargementQuantityStatus
                .AMBIGUOUS_PRODUCT
            ),
            product=None,
            match_method="designation",
            quantity_raw=-18,
            units_per_carton=8,
            total_units=-18,
            carton_quantity=Decimal("-2.25"),
            cartons=-2,
            pieces=-2,
            error_code=None,
        )

        result = (
            enrich_raw_chargement_cleaning_result(
                self._result(
                    self._row()
                ),
                source_system=object(),
            )
        )

        row = result.rows[0]
        cleaned = row.cleaned_dict()

        self.assertEqual(
            row.status,
            "ACCEPTED",
        )
        self.assertEqual(
            cleaned["packaging_status"],
            "AMBIGUOUS_PRODUCT",
        )
        self.assertEqual(
            cleaned["total_units"],
            -18,
        )
        self.assertEqual(
            cleaned["units_per_carton"],
            8,
        )
        self.assertEqual(
            cleaned["cartons"],
            -2,
        )
        self.assertEqual(
            cleaned["pieces"],
            -2,
        )
        self.assertEqual(
            cleaned["carton_quantity"],
            "-2.25",
        )
        self.assertIsNone(
            cleaned["product_packaging_id"],
        )
        self.assertEqual(
            cleaned["product_match_method"],
            "designation",
        )

        issue = row.issues[-1]

        self.assertEqual(
            issue.code,
            "chargement_ambiguous_product",
        )
        self.assertEqual(
            issue.severity,
            "WARNING",
        )
        self.assertEqual(
            issue.details[
                "consensus_units_per_carton"
            ],
            8,
        )
        self.assertEqual(
            issue.details["total_units"],
            -18,
        )

    @patch(
        "apps.imports.services."
        "raw_chargement_cleaning_enrichment."
        "enrich_raw_chargement_quantity"
    )
    def test_invalid_quantity_excludes_row(
        self,
        enrich_quantity,
    ):
        enrich_quantity.return_value = (
            self._enrichment(
                status=(
                    ChargementQuantityStatus
                    .INVALID_QUANTITY
                ),
                total_units=None,
                units_per_carton=None,
                cartons=None,
                pieces=None,
                product=False,
                error_code=(
                    "invalid_chargement_quantity"
                ),
            )
        )

        result = (
            enrich_raw_chargement_cleaning_result(
                self._result(
                    self._row()
                ),
                source_system=object(),
            )
        )

        row = result.rows[0]

        self.assertEqual(
            row.status,
            STATUS_EXCLUDED,
        )
        self.assertEqual(
            row.issues[-1].code,
            "chargement_invalid_quantity",
        )

    @patch(
        "apps.imports.services."
        "raw_chargement_cleaning_enrichment."
        "enrich_raw_chargement_quantity"
    )
    def test_stopped_row_is_not_product_resolved(
        self,
        enrich_quantity,
    ):
        stopped = self._row(
            status=STATUS_STOPPED,
            quantity=0,
            article=None,
            barcode=None,
        )

        result = (
            enrich_raw_chargement_cleaning_result(
                self._result(stopped),
                source_system=object(),
            )
        )

        self.assertEqual(
            result.rows[0].status,
            STATUS_STOPPED,
        )
        enrich_quantity.assert_not_called()

    def test_rejects_non_chargement_result(
        self,
    ):
        cleaning_result = ReportCleaningResult(
            filename="items.xlsx",
            report_type="ITEMS",
            rows=(),
        )

        with self.assertRaises(ValueError):
            enrich_raw_chargement_cleaning_result(
                cleaning_result,
                source_system=object(),
            )
