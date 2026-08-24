from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.imports.services.raw_items_multi_review import (
    RawItemsImportRequest,
    create_raw_items_multi_import_reviews,
)
from apps.imports.services.raw_items_review import (
    RawItemsImportReviewError,
)


class RawItemsMultiReviewTests(SimpleTestCase):
    @patch(
        "apps.imports.services.raw_items_multi_review."
        "create_raw_items_derived_import_review"
    )
    def test_collects_successful_files(
        self,
        mocked_create,
    ):
        mocked_create.return_value = (
            SimpleNamespace(batch="BATCH")
        )

        result = create_raw_items_multi_import_reviews(
            [
                RawItemsImportRequest(
                    source=object(),
                    source_system_code="BIFA_MILA",
                    period_start="2026-08-01",
                    period_end="2026-08-18",
                    original_filename=(
                        "DCV-03 items.xlsx"
                    ),
                ),
                RawItemsImportRequest(
                    source=object(),
                    source_system_code="AIO_WEB",
                    period_start="2026-08-01",
                    period_end="2026-08-18",
                    original_filename=(
                        "VAN2-DELISKY items.xlsx"
                    ),
                ),
            ],
            uploaded_by=object(),
        )

        self.assertEqual(
            result.succeeded_count,
            2,
        )
        self.assertEqual(
            result.failed_count,
            0,
        )
        self.assertTrue(
            all(
                item.succeeded
                for item in result.files
            )
        )

    @patch(
        "apps.imports.services.raw_items_multi_review."
        "create_raw_items_derived_import_review"
    )
    def test_failure_does_not_hide_other_file(
        self,
        mocked_create,
    ):
        mocked_create.side_effect = [
            SimpleNamespace(batch="BATCH"),
            RawItemsImportReviewError(
                "bad_items_file",
                "Bad Items file.",
            ),
        ]

        result = create_raw_items_multi_import_reviews(
            [
                RawItemsImportRequest(
                    source=object(),
                    source_system_code="BIFA_MILA",
                    period_start="2026-08-01",
                    period_end="2026-08-18",
                    original_filename=(
                        "DCV-03 items.xlsx"
                    ),
                ),
                RawItemsImportRequest(
                    source=object(),
                    source_system_code="AIO_WEB",
                    period_start="2026-08-01",
                    period_end="2026-08-18",
                    original_filename=(
                        "BAD items.xlsx"
                    ),
                ),
            ],
            uploaded_by=object(),
        )

        self.assertEqual(
            result.succeeded_count,
            1,
        )
        self.assertEqual(
            result.failed_count,
            1,
        )
        self.assertTrue(
            result.files[0].succeeded
        )
        self.assertFalse(
            result.files[1].succeeded
        )
        self.assertEqual(
            result.files[1].error_code,
            "bad_items_file",
        )
