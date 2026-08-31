from contextlib import ExitStack, nullcontext
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.imports.models import (
    ImportBatchStatus,
)
from apps.imports.services.raw_pos_derived_review import (
    RawPosDerivedReviewError,
    create_raw_pos_derived_import_review,
)


MODULE = (
    "apps.imports.services."
    "raw_pos_derived_review"
)


class RawPosDerivedReviewTests(
    SimpleTestCase
):
    def _run(
        self,
        *,
        scope_batches=(),
        content_sha="new-content",
    ):
        period_start = date(
            2026,
            4,
            4,
        )

        period_end = date(
            2026,
            8,
            26,
        )

        review = SimpleNamespace(
            adapted=SimpleNamespace(
                worksheet_name="Classeur",
                filename=(
                    "VAN2-NITA "
                    "pos_2026-04-04_to_2026-08-26.xlsx"
                ),
                source_truck_code="VAN2-NITA",
            ),
            row_result=object(),
            cleaning_result=object(),
            period_start=period_start,
            period_end=period_end,
        )

        prepared_rows = SimpleNamespace(
            content_sha256=content_sha,
        )

        source_upload = SimpleNamespace(
            pk=100,
            source_system_id=10,
            source_file=SimpleNamespace(
                name="",
                storage=Mock(),
            ),
        )

        source_upload_result = (
            SimpleNamespace(
                source_upload=source_upload,
                created=False,
            )
        )

        fake_source_system_manager = (
            Mock()
        )

        (
            fake_source_system_manager
            .select_for_update
            .return_value
            .get
            .return_value
        ) = SimpleNamespace(
            pk=10
        )

        persisted_batch = (
            SimpleNamespace(
                pk=500,
                status=(
                    ImportBatchStatus.REVIEWED
                ),
            )
        )

        persist_result = (
            SimpleNamespace(
                batch=persisted_batch
            )
        )

        stack = ExitStack()

        stack.enter_context(
            patch(
                f"{MODULE}._validate_user"
            )
        )

        stack.enter_context(
            patch(
                f"{MODULE}."
                "build_source_truck_mapping",
                return_value={
                    "VAN2-NITA":
                        "NITA LIV02",
                },
            )
        )

        stack.enter_context(
            patch(
                f"{MODULE}."
                "prepare_raw_pos_review",
                return_value=review,
            )
        )

        stack.enter_context(
            patch(
                f"{MODULE}."
                "_resolve_pos_brand_code",
                return_value="NITA",
            )
        )

        stack.enter_context(
            patch(
                f"{MODULE}."
                "build_import_review_summary_from_metadata",
                return_value=object(),
            )
        )

        stack.enter_context(
            patch(
                f"{MODULE}."
                "prepare_import_rows",
                return_value=prepared_rows,
            )
        )

        stack.enter_context(
            patch(
                f"{MODULE}."
                "create_import_source_upload",
                return_value=(
                    source_upload_result
                ),
            )
        )

        stack.enter_context(
            patch(
                f"{MODULE}."
                "_logical_pos_scope_batches",
                return_value=tuple(
                    scope_batches
                ),
            )
        )

        persist_mock = (
            stack.enter_context(
                patch(
                    f"{MODULE}."
                    "_persist_derived_import_review",
                    return_value=(
                        persist_result
                    ),
                )
            )
        )

        stack.enter_context(
            patch(
                f"{MODULE}."
                "ImportSourceSystem",
                SimpleNamespace(
                    objects=(
                        fake_source_system_manager
                    )
                ),
            )
        )

        stack.enter_context(
            patch(
                f"{MODULE}."
                "transaction.atomic",
                side_effect=lambda: (
                    nullcontext()
                ),
            )
        )

        return (
            stack,
            persist_mock,
            source_upload,
            persisted_batch,
            period_start,
            period_end,
        )

    def test_exact_mutable_batch_is_updated(self):
        period_start = date(
            2026,
            4,
            4,
        )
        period_end = date(
            2026,
            8,
            26,
        )

        mutable = SimpleNamespace(
            pk=40,
            status=(
                ImportBatchStatus.REVIEWED
            ),
            period_start=period_start,
            period_end=period_end,
            content_sha256="old-content",
        )

        (
            stack,
            persist_mock,
            source_upload,
            persisted_batch,
            _start,
            _end,
        ) = self._run(
            scope_batches=(mutable,),
        )

        with stack:
            result = (
                create_raw_pos_derived_import_review(
                    object(),
                    source_system_code="AIO_WEB",
                    uploaded_by=object(),
                    period_start=period_start,
                    period_end=period_end,
                    original_filename=(
                        "VAN2-NITA "
                        "pos_2026-04-04_to_2026-08-26.xlsx"
                    ),
                )
            )

        self.assertIs(
            result.source_upload,
            source_upload,
        )

        self.assertIs(
            result.batch,
            persisted_batch,
        )

        self.assertEqual(
            persist_mock.call_args.kwargs[
                "batch"
            ],
            mutable,
        )

    def test_identical_approved_batch_is_reused(self):
        period_start = date(
            2026,
            4,
            4,
        )
        period_end = date(
            2026,
            8,
            26,
        )

        approved = SimpleNamespace(
            pk=41,
            status=(
                ImportBatchStatus.APPROVED
            ),
            period_start=period_start,
            period_end=period_end,
            content_sha256="new-content",
        )

        (
            stack,
            persist_mock,
            _source_upload,
            _persisted_batch,
            _start,
            _end,
        ) = self._run(
            scope_batches=(approved,),
        )

        with stack:
            result = (
                create_raw_pos_derived_import_review(
                    object(),
                    source_system_code="AIO_WEB",
                    uploaded_by=object(),
                    period_start=period_start,
                    period_end=period_end,
                )
            )

        self.assertIs(
            result.batch,
            approved,
        )

        persist_mock.assert_not_called()

    def test_different_approved_content_is_blocked(self):
        period_start = date(
            2026,
            4,
            4,
        )
        period_end = date(
            2026,
            8,
            26,
        )

        approved = SimpleNamespace(
            pk=42,
            status=(
                ImportBatchStatus.APPROVED
            ),
            period_start=period_start,
            period_end=period_end,
            content_sha256="different-content",
        )

        (
            stack,
            _persist_mock,
            _source_upload,
            _persisted_batch,
            _start,
            _end,
        ) = self._run(
            scope_batches=(approved,),
        )

        with stack:
            with self.assertRaises(
                RawPosDerivedReviewError
            ) as caught:
                (
                    create_raw_pos_derived_import_review(
                        object(),
                        source_system_code=(
                            "AIO_WEB"
                        ),
                        uploaded_by=object(),
                        period_start=period_start,
                        period_end=period_end,
                    )
                )

        self.assertEqual(
            caught.exception.code,
            "pos_approved_content_conflict",
        )

    def test_different_overlapping_period_is_blocked(self):
        requested_start = date(
            2026,
            4,
            4,
        )
        requested_end = date(
            2026,
            8,
            26,
        )

        overlapping = SimpleNamespace(
            pk=43,
            status=(
                ImportBatchStatus.REVIEWED
            ),
            period_start=date(
                2026,
                8,
                1,
            ),
            period_end=date(
                2026,
                8,
                31,
            ),
            content_sha256="old-content",
        )

        (
            stack,
            _persist_mock,
            _source_upload,
            _persisted_batch,
            _start,
            _end,
        ) = self._run(
            scope_batches=(overlapping,),
        )

        with stack:
            with self.assertRaises(
                RawPosDerivedReviewError
            ) as caught:
                (
                    create_raw_pos_derived_import_review(
                        object(),
                        source_system_code=(
                            "AIO_WEB"
                        ),
                        uploaded_by=object(),
                        period_start=(
                            requested_start
                        ),
                        period_end=(
                            requested_end
                        ),
                    )
                )

        self.assertEqual(
            caught.exception.code,
            "pos_period_overlap_conflict",
        )
