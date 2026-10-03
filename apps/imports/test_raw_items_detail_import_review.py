from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.imports.models import (
    DistributionBrand,
    ImportBatch,
    ImportBatchStatus,
    ImportSourceSystem,
    ImportSourceUpload,
)
from apps.imports.services.raw_items_detail_import_review import (
    RawItemsDetailImportReviewError,
    create_raw_items_detail_import_review,
)


class RawItemsDetailImportReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="items-detail-import-review",
            password="test",
        )
        cls.source_system = ImportSourceSystem.objects.create(
            code="AIO_WEB",
            name="AIO WEB",
        )
        cls.brand = DistributionBrand.objects.create(
            code="DELISKY",
            name="DELISKY",
        )

    def _source_upload(self, sha):
        return ImportSourceUpload.objects.create(
            source_system=self.source_system,
            original_filename="AIO_Items_DETAIL.xlsx",
            worksheet_name="Classeur",
            file_size_bytes=10,
            file_sha256=sha,
            uploaded_by=self.user,
        )

    def _prepared_review(self):
        return SimpleNamespace(
            adapted=SimpleNamespace(
                filename="AIO_Items_DETAIL.xlsx",
                worksheet_name="Classeur",
                rows=(object(), object()),
            ),
            excluded_source_rows=(
                SimpleNamespace(
                    source_code="RACHID",
                    reason="OUT_OF_SCOPE",
                ),
                SimpleNamespace(
                    source_code="RACHID",
                    reason="OUT_OF_SCOPE",
                ),
                SimpleNamespace(
                    source_code="ADV",
                    reason="OUT_OF_SCOPE",
                ),
            ),
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
            source_truck_scope=SimpleNamespace(
                as_dict=lambda: {
                    "mappings": [],
                    "exclusions": [],
                }
            ),
        )

    def _batch(
        self,
        upload,
        *,
        status=ImportBatchStatus.REVIEWED,
        content_sha="3" * 64,
    ):
        return ImportBatch.objects.create(
            source_upload=upload,
            brand=self.brand,
            report_type="ITEMS",
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
            original_filename=upload.original_filename,
            worksheet_name="Classeur",
            content_sha256=content_sha,
            status=status,
            total_rows=0,
            accepted_rows=0,
            excluded_rows=0,
            stopped_rows=0,
            uploaded_by=self.user,
            reviewed_by=self.user,
            approved_by=(
                self.user
                if status
                == ImportBatchStatus.APPROVED
                else None
            ),
        )

    @patch(
        "apps.imports.services.raw_items_detail_import_review."
        "persist_raw_items_detail_review"
    )
    @patch(
        "apps.imports.services.raw_items_detail_import_review."
        "create_import_source_upload"
    )
    @patch(
        "apps.imports.services.raw_items_detail_import_review."
        "prepare_raw_items_detail_review"
    )
    def test_persists_all_derived_brands_from_one_source(
        self,
        prepare_mock,
        source_store_mock,
        persist_mock,
    ):
        upload = self._source_upload("1" * 64)
        prepare_mock.return_value = self._prepared_review()
        source_store_mock.return_value = SimpleNamespace(
            source_upload=upload,
            created=True,
        )

        first_batch = SimpleNamespace(pk=101)
        second_batch = SimpleNamespace(pk=102)
        persisted = SimpleNamespace(
            source_upload=upload,
            brand_results=(
                SimpleNamespace(batch=first_batch),
                SimpleNamespace(batch=second_batch),
            ),
        )
        persist_mock.return_value = persisted

        result = create_raw_items_detail_import_review(
            SimpleNamespace(name="AIO_Items_DETAIL.xlsx"),
            source_system_code="AIO_WEB",
            uploaded_by=self.user,
            reviewed_by=self.user,
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
            original_filename="AIO_Items_DETAIL.xlsx",
        )

        self.assertEqual(
            result.source_upload.pk,
            upload.pk,
        )
        self.assertEqual(
            result.batches,
            (first_batch, second_batch),
        )
        persist_mock.assert_called_once()
        self.assertEqual(
            persist_mock.call_args.kwargs[
                "source_upload"
            ].pk,
            upload.pk,
        )
        self.assertEqual(
            persist_mock.call_args.kwargs[
                "existing_batches_by_brand"
            ],
            {},
        )

        upload.refresh_from_db()
        audit = upload.audit_metadata[
            "items_detail"
        ]
        self.assertTrue(
            audit["transaction_level"]
        )
        self.assertEqual(
            audit["adapted_row_count"],
            2,
        )
        self.assertEqual(
            audit["excluded_source_row_count"],
            3,
        )
        self.assertEqual(
            audit["excluded_source_groups"],
            [
                {
                    "source_code": "ADV",
                    "reason": "OUT_OF_SCOPE",
                    "count": 1,
                },
                {
                    "source_code": "RACHID",
                    "reason": "OUT_OF_SCOPE",
                    "count": 2,
                },
            ],
        )

    @patch(
        "apps.imports.services.raw_items_detail_import_review."
        "persist_raw_items_detail_review"
    )
    @patch(
        "apps.imports.services.raw_items_detail_import_review."
        "create_import_source_upload"
    )
    @patch(
        "apps.imports.services.raw_items_detail_import_review."
        "prepare_raw_items_detail_review"
    )
    def test_existing_mutable_source_refreshes_in_place(
        self,
        prepare_mock,
        source_store_mock,
        persist_mock,
    ):
        upload = self._source_upload("2" * 64)
        existing = self._batch(upload)

        prepare_mock.return_value = self._prepared_review()
        source_store_mock.return_value = SimpleNamespace(
            source_upload=upload,
            created=False,
        )
        persisted = SimpleNamespace(
            source_upload=upload,
            brand_results=(
                SimpleNamespace(batch=existing),
            ),
        )
        persist_mock.return_value = persisted

        result = create_raw_items_detail_import_review(
            SimpleNamespace(
                name="AIO_Items_DETAIL.xlsx"
            ),
            source_system_code="AIO_WEB",
            uploaded_by=self.user,
            reviewed_by=self.user,
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
            original_filename=(
                "AIO_Items_DETAIL.xlsx"
            ),
        )

        self.assertEqual(
            result.batches,
            (existing,),
        )

        refreshed = (
            persist_mock.call_args.kwargs[
                "existing_batches_by_brand"
            ]
        )
        self.assertEqual(
            set(refreshed),
            {"DELISKY"},
        )
        self.assertEqual(
            refreshed["DELISKY"].pk,
            existing.pk,
        )

    @patch(
        "apps.imports.services.raw_items_detail_import_review."
        "persist_raw_items_detail_review"
    )
    @patch(
        "apps.imports.services.raw_items_detail_import_review."
        "create_import_source_upload"
    )
    @patch(
        "apps.imports.services.raw_items_detail_import_review."
        "prepare_raw_items_detail_review"
    )
    def test_existing_immutable_source_is_not_rewritten(
        self,
        prepare_mock,
        source_store_mock,
        persist_mock,
    ):
        upload = self._source_upload("4" * 64)
        self._batch(
            upload,
            status=ImportBatchStatus.APPROVED,
            content_sha="5" * 64,
        )

        prepare_mock.return_value = self._prepared_review()
        source_store_mock.return_value = SimpleNamespace(
            source_upload=upload,
            created=False,
        )

        with self.assertRaises(
            RawItemsDetailImportReviewError
        ) as captured:
            create_raw_items_detail_import_review(
                SimpleNamespace(
                    name="AIO_Items_DETAIL.xlsx"
                ),
                source_system_code="AIO_WEB",
                uploaded_by=self.user,
                reviewed_by=self.user,
                period_start=date(2026, 4, 4),
                period_end=date(2026, 8, 26),
                original_filename=(
                    "AIO_Items_DETAIL.xlsx"
                ),
            )

        self.assertEqual(
            captured.exception.code,
            "source_upload_already_reviewed",
        )
        self.assertEqual(
            captured.exception.details[
                "source_upload_id"
            ],
            upload.pk,
        )
        persist_mock.assert_not_called()
