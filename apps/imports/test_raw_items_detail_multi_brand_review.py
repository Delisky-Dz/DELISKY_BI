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
from apps.imports.services.raw_items_detail_multi_brand_review import (
    persist_raw_items_detail_review,
)


class RawItemsDetailMultiBrandReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="items-detail-multi-brand",
            password="test-only-password",
        )
        cls.source_system = ImportSourceSystem.objects.create(
            code="DETAIL_MULTI",
            name="Detail Multi",
        )
        cls.source_upload = ImportSourceUpload.objects.create(
            source_system=cls.source_system,
            original_filename="items-detail.xlsx",
            worksheet_name="Sheet1",
            file_size_bytes=10,
            file_sha256="a" * 64,
            uploaded_by=cls.user,
        )
        cls.delisky = DistributionBrand.objects.create(
            code="DELISKY",
            name="DELISKY",
        )

    def _review(self, brand_reviews):
        return SimpleNamespace(
            brand_reviews=tuple(brand_reviews),
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
        )

    def _existing_batch(
        self,
        *,
        status=ImportBatchStatus.REVIEWED,
    ):
        return ImportBatch.objects.create(
            source_upload=self.source_upload,
            brand=self.delisky,
            report_type="ITEMS",
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
            original_filename=(
                self.source_upload.original_filename
            ),
            worksheet_name="Sheet1",
            status=status,
            total_rows=0,
            accepted_rows=0,
            excluded_rows=0,
            stopped_rows=0,
            content_sha256="b" * 64,
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
        "apps.imports.services.raw_items_detail_multi_brand_review."
        "persist_raw_items_detail_brand_review"
    )
    def test_persists_every_brand_partition_in_review_order(
        self,
        persist_brand,
    ):
        bifa = SimpleNamespace(brand_code="BIFA")
        delisky = SimpleNamespace(
            brand_code="DELISKY"
        )
        first_result = SimpleNamespace(
            batch=SimpleNamespace(pk=101)
        )
        second_result = SimpleNamespace(
            batch=SimpleNamespace(pk=102)
        )
        persist_brand.side_effect = [
            first_result,
            second_result,
        ]

        result = persist_raw_items_detail_review(
            source_upload=self.source_upload,
            review=self._review([bifa, delisky]),
            uploaded_by=self.user,
            reviewer=self.user,
        )

        self.assertEqual(
            result.brand_results,
            (first_result, second_result),
        )
        self.assertEqual(
            tuple(
                batch.pk
                for batch in result.batches
            ),
            (101, 102),
        )
        self.assertEqual(
            persist_brand.call_count,
            2,
        )
        self.assertIs(
            persist_brand.call_args_list[
                0
            ].kwargs["brand_review"],
            bifa,
        )
        self.assertIs(
            persist_brand.call_args_list[
                1
            ].kwargs["brand_review"],
            delisky,
        )
        for call in (
            persist_brand.call_args_list
        ):
            self.assertEqual(
                call.kwargs["period_start"],
                date(2026, 4, 4),
            )
            self.assertEqual(
                call.kwargs["period_end"],
                date(2026, 8, 26),
            )
            self.assertEqual(
                call.kwargs["source_upload"].pk,
                self.source_upload.pk,
            )
            self.assertIsNone(
                call.kwargs["batch"]
            )

    @patch(
        "apps.imports.services.raw_items_detail_multi_brand_review."
        "persist_raw_items_detail_brand_review"
    )
    def test_refresh_passes_matching_mutable_batch(
        self,
        persist_brand,
    ):
        existing = self._existing_batch()
        brand_review = SimpleNamespace(
            brand_code="DELISKY"
        )
        refreshed = SimpleNamespace(
            batch=existing
        )
        persist_brand.return_value = refreshed

        result = persist_raw_items_detail_review(
            source_upload=self.source_upload,
            review=self._review([brand_review]),
            uploaded_by=self.user,
            reviewer=self.user,
            existing_batches_by_brand={
                "DELISKY": existing,
            },
        )

        self.assertEqual(
            result.batches,
            (existing,),
        )
        self.assertEqual(
            persist_brand.call_args.kwargs[
                "batch"
            ].pk,
            existing.pk,
        )

    @patch(
        "apps.imports.services.raw_items_detail_multi_brand_review."
        "persist_raw_items_detail_brand_review"
    )
    def test_refresh_deletes_stale_mutable_brand_batch(
        self,
        persist_brand,
    ):
        stale = self._existing_batch()
        bifa = SimpleNamespace(
            brand_code="BIFA"
        )
        persist_brand.return_value = (
            SimpleNamespace(
                batch=SimpleNamespace(pk=303)
            )
        )

        persist_raw_items_detail_review(
            source_upload=self.source_upload,
            review=self._review([bifa]),
            uploaded_by=self.user,
            reviewer=self.user,
            existing_batches_by_brand={
                "DELISKY": stale,
            },
        )

        self.assertFalse(
            ImportBatch.objects.filter(
                pk=stale.pk
            ).exists()
        )

    def test_refresh_rejects_immutable_existing_batch(
        self,
    ):
        existing = self._existing_batch(
            status=ImportBatchStatus.APPROVED
        )

        with self.assertRaisesMessage(
            ValueError,
            "Only mutable",
        ):
            persist_raw_items_detail_review(
                source_upload=self.source_upload,
                review=self._review([
                    SimpleNamespace(
                        brand_code="DELISKY"
                    )
                ]),
                uploaded_by=self.user,
                reviewer=self.user,
                existing_batches_by_brand={
                    "DELISKY": existing,
                },
            )

    def test_rejects_review_without_brand_partitions(
        self,
    ):
        with self.assertRaisesMessage(
            ValueError,
            "at least one brand partition",
        ):
            persist_raw_items_detail_review(
                source_upload=self.source_upload,
                review=self._review([]),
                uploaded_by=self.user,
                reviewer=self.user,
            )

    def test_rejects_unsaved_source_upload(self):
        unsaved = ImportSourceUpload(
            source_system=self.source_system,
            original_filename="unsaved.xlsx",
            file_sha256="c" * 64,
            uploaded_by=self.user,
        )

        with self.assertRaisesMessage(
            ValueError,
            "source_upload must be saved",
        ):
            persist_raw_items_detail_review(
                source_upload=unsaved,
                review=self._review([
                    SimpleNamespace(
                        brand_code="BIFA"
                    )
                ]),
                uploaded_by=self.user,
                reviewer=self.user,
            )
