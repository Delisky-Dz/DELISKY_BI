from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.imports.models import (
    ImportBatchStatus,
)
from apps.imports.services.raw_pos_derived_review import (
    RawPosDerivedReviewError,
)
from apps.imports.services.raw_pos_multi_review import (
    RawPosImportRequest,
    create_raw_pos_multi_import_reviews,
)


MODULE = (
    "apps.imports.services."
    "raw_pos_multi_review"
)


class RawPosMultiReviewTests(
    SimpleTestCase
):
    def _request(self):
        return RawPosImportRequest(
            source=object(),
            source_system_code="AIO_WEB",
            period_start="2026-04-04",
            period_end="2026-08-26",
            original_filename=(
                "VAN2-NITA "
                "pos_2026-04-04_to_2026-08-26.xlsx"
            ),
        )

    def test_successful_review_counts_as_success(self):
        batch = SimpleNamespace(
            pk=70,
            status=(
                ImportBatchStatus.REVIEWED
            ),
        )

        with patch(
            f"{MODULE}."
            "create_raw_pos_derived_import_review",
            return_value=(
                SimpleNamespace(
                    batch=batch
                )
            ),
        ):
            result = (
                create_raw_pos_multi_import_reviews(
                    (self._request(),),
                    uploaded_by=object(),
                )
            )

        self.assertEqual(
            result.succeeded_count,
            1,
        )

        self.assertEqual(
            result.failed_count,
            0,
        )

        self.assertIs(
            result.files[0].batch,
            batch,
        )

    def test_blocked_batch_still_counts_as_processed(self):
        batch = SimpleNamespace(
            pk=71,
            status=(
                ImportBatchStatus.BLOCKED
            ),
        )

        with patch(
            f"{MODULE}."
            "create_raw_pos_derived_import_review",
            return_value=(
                SimpleNamespace(
                    batch=batch
                )
            ),
        ):
            result = (
                create_raw_pos_multi_import_reviews(
                    (self._request(),),
                    uploaded_by=object(),
                )
            )

        self.assertEqual(
            result.succeeded_count,
            1,
        )

        self.assertEqual(
            result.failed_count,
            0,
        )

        self.assertEqual(
            result.files[0].batch.status,
            ImportBatchStatus.BLOCKED,
        )

    def test_derived_error_counts_as_failed_file(self):
        error = RawPosDerivedReviewError(
            "pos_period_overlap_conflict",
            "POS period conflict.",
            details={
                "batch_ids": [10],
            },
        )

        with patch(
            f"{MODULE}."
            "create_raw_pos_derived_import_review",
            side_effect=error,
        ):
            result = (
                create_raw_pos_multi_import_reviews(
                    (self._request(),),
                    uploaded_by=object(),
                )
            )

        self.assertEqual(
            result.succeeded_count,
            0,
        )

        self.assertEqual(
            result.failed_count,
            1,
        )

        self.assertEqual(
            result.files[0].error_code,
            "pos_period_overlap_conflict",
        )

        self.assertEqual(
            result.files[0].error_details,
            {
                "batch_ids": [10],
            },
        )
