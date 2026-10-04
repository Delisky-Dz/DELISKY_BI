from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.imports.services.raw_items_detail_derived_review import (
    _items_detail_metadata,
)
from apps.imports.services.raw_items_detail_replacement import (
    ItemsDetailReplacementPlan,
)
from apps.imports.services.source_truck_scope_snapshot import (
    build_source_truck_scope_snapshot,
)


class RawItemsDetailDerivedReviewMetadataTests(SimpleTestCase):
    def _brand_review(self, covered_trucks):
        return SimpleNamespace(
            covered_trucks=covered_trucks,
            source_truck_scope=build_source_truck_scope_snapshot(
                mappings={"DCV-03": "BIFA LIV03"},
                exclusions={"DPV-01": "PRE_SALE_OUT_OF_SCOPE"},
            ),
        )

    def test_metadata_marks_transaction_level_scope_and_replacements(self):
        brand_review = self._brand_review(
            ("BIFA LIV03", "BIFA LIV07")
        )
        replacement_plan = ItemsDetailReplacementPlan(
            covered_trucks=("BIFA LIV03", "BIFA LIV07"),
            replacement_batches=(
                SimpleNamespace(pk=52),
                SimpleNamespace(pk=53),
            ),
        )

        metadata = _items_detail_metadata(
            brand_review=brand_review,
            replacement_plan=replacement_plan,
        )

        self.assertTrue(metadata["transaction_level"])
        self.assertEqual(
            metadata["covered_trucks"],
            ["BIFA LIV03", "BIFA LIV07"],
        )
        self.assertEqual(metadata["replacement_batch_ids"], [52, 53])
        self.assertEqual(
            metadata["source_truck_scope"]["mappings"],
            {"DCV-03": "BIFA LIV03"},
        )
        self.assertEqual(
            metadata["source_truck_scope"]["exclusions"],
            {"DPV-01": "PRE_SALE_OUT_OF_SCOPE"},
        )
        self.assertEqual(
            len(metadata["source_truck_scope"]["sha256"]),
            64,
        )

    def test_metadata_ignores_unsaved_replacement_objects(self):
        brand_review = self._brand_review(("DELISKY LIV01",))
        replacement_plan = ItemsDetailReplacementPlan(
            covered_trucks=("DELISKY LIV01",),
            replacement_batches=(
                SimpleNamespace(pk=None),
                SimpleNamespace(pk=59),
            ),
        )

        metadata = _items_detail_metadata(
            brand_review=brand_review,
            replacement_plan=replacement_plan,
        )

        self.assertEqual(metadata["replacement_batch_ids"], [59])
        self.assertEqual(
            metadata["covered_trucks"],
            ["DELISKY LIV01"],
        )
        self.assertIn("source_truck_scope", metadata)
