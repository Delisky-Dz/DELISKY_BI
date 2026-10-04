from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.imports.services.raw_items_detail_import_review import (
    RawItemsDetailImportReviewError,
)
from apps.imports.services.raw_items_detail_multi_review import (
    RawItemsDetailImportRequest,
    create_raw_items_detail_multi_import_reviews,
)


class RawItemsDetailMultiReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="items-detail-multi-review",
            password="test",
        )

    def _request(self, filename, source_system_code):
        return RawItemsDetailImportRequest(
            source=SimpleNamespace(name=filename),
            source_system_code=source_system_code,
            period_start="2026-04-04",
            period_end="2026-08-26",
            original_filename=filename,
        )

    @patch(
        "apps.imports.services.raw_items_detail_multi_review."
        "create_raw_items_detail_import_review"
    )
    def test_returns_success_for_each_reviewed_source(
        self,
        review_mock,
    ):
        first_batch = SimpleNamespace(pk=11)
        second_batch = SimpleNamespace(pk=12)
        third_batch = SimpleNamespace(pk=13)

        review_mock.side_effect = [
            SimpleNamespace(
                batches=(first_batch,)
            ),
            SimpleNamespace(
                batches=(
                    second_batch,
                    third_batch,
                )
            ),
        ]

        result = (
            create_raw_items_detail_multi_import_reviews(
                (
                    self._request(
                        "BIFA_Items_DETAIL.xlsx",
                        "BIFA_MILA",
                    ),
                    self._request(
                        "AIO_Items_DETAIL.xlsx",
                        "AIO_WEB",
                    ),
                ),
                uploaded_by=self.user,
                reviewed_by=self.user,
            )
        )

        self.assertEqual(result.succeeded_count, 2)
        self.assertEqual(result.failed_count, 0)
        self.assertEqual(
            result.files[0].batches,
            (first_batch,),
        )
        self.assertEqual(
            result.files[1].batches,
            (
                second_batch,
                third_batch,
            ),
        )

    @patch(
        "apps.imports.services.raw_items_detail_multi_review."
        "create_raw_items_detail_import_review"
    )
    def test_one_failed_source_does_not_hide_other_result(
        self,
        review_mock,
    ):
        good_batch = SimpleNamespace(pk=21)

        review_mock.side_effect = [
            RawItemsDetailImportReviewError(
                "source_upload_already_reviewed",
                "Already reviewed.",
                details={"source_upload_id": 9},
            ),
            SimpleNamespace(
                batches=(good_batch,)
            ),
        ]

        result = (
            create_raw_items_detail_multi_import_reviews(
                (
                    self._request(
                        "duplicate.xlsx",
                        "BIFA_MILA",
                    ),
                    self._request(
                        "good.xlsx",
                        "AIO_WEB",
                    ),
                ),
                uploaded_by=self.user,
                reviewed_by=self.user,
            )
        )

        self.assertEqual(result.succeeded_count, 1)
        self.assertEqual(result.failed_count, 1)
        self.assertFalse(
            result.files[0].succeeded
        )
        self.assertEqual(
            result.files[0].error_code,
            "source_upload_already_reviewed",
        )
        self.assertEqual(
            result.files[0].error_details,
            {"source_upload_id": 9},
        )
        self.assertTrue(
            result.files[1].succeeded
        )
        self.assertEqual(
            result.files[1].batches,
            (good_batch,),
        )
