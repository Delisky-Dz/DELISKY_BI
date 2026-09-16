from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.imports.services.raw_items_detail_derived_review import (
    _items_detail_metadata,
)
from apps.imports.services.raw_items_detail_replacement import (
    ItemsDetailReplacementPlan,
)


class RawItemsDetailDerivedReviewMetadataTests(SimpleTestCase):
    def test_metadata_marks_transaction_level_scope_and_replacements(self):
        brand_review = SimpleNamespace(
            covered_trucks=("BIFA LIV03", "BIFA LIV07"),
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

        self.assertEqual(
            metadata,
            {
                "transaction_level": True,
                "covered_trucks": ["BIFA LIV03", "BIFA LIV07"],
                "replacement_batch_ids": [52, 53],
            },
        )

    def test_metadata_ignores_unsaved_replacement_objects(self):
        brand_review = SimpleNamespace(
            covered_trucks=("DELISKY LIV01",),
        )
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
