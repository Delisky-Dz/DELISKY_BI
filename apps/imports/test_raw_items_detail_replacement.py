from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.fleet.models import Truck
from apps.imports.models import (
    DistributionBrand,
    ImportBatch,
    ImportBatchStatus,
    ImportSourceSystem,
    ImportSourceUpload,
    SourceTruckMapping,
)
from apps.imports.services.raw_items_detail_replacement import (
    RawItemsDetailReplacementError,
    plan_items_detail_replacements,
)


class RawItemsDetailReplacementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="items-detail-replacement-user",
            password="test",
        )
        self.brand = DistributionBrand.objects.create(
            code="BIFA",
            name="BIFA",
            is_active=True,
        )
        self.source_system = ImportSourceSystem.objects.create(
            code="BIFA_MILA",
            name="BIFA Mila",
            is_active=True,
        )

        self.liv03 = Truck.objects.create(
            internal_code="BIFA LIV03",
            distribution_brand=self.brand,
            registration_number="DETAIL-REPL-LIV03",
            brand="BIFA",
            model="",
        )
        self.pliv01 = Truck.objects.create(
            internal_code="BIFA PLIV01",
            distribution_brand=self.brand,
            registration_number="DETAIL-REPL-PLIV01",
            brand="BIFA",
            model="",
        )
        self.liv07 = Truck.objects.create(
            internal_code="BIFA LIV07",
            distribution_brand=self.brand,
            registration_number="DETAIL-REPL-LIV07",
            brand="BIFA",
            model="",
        )

        for source_code, truck in (
            ("DCV-03", self.liv03),
            ("DLV-01", self.pliv01),
            ("DCV-07", self.liv07),
        ):
            SourceTruckMapping.objects.create(
                source_system=self.source_system,
                source_code=source_code,
                truck=truck,
                is_active=True,
            )

        self._sha_counter = 0

    def source_upload(self, filename):
        self._sha_counter += 1
        return ImportSourceUpload.objects.create(
            source_system=self.source_system,
            original_filename=filename,
            worksheet_name="Classeur",
            file_size_bytes=1,
            file_sha256=(
                f"{self._sha_counter:064x}"
            ),
            uploaded_by=self.user,
        )

    def batch(
        self,
        filename,
        *,
        status=ImportBatchStatus.APPROVED,
        period_start=date(2026, 4, 4),
        period_end=date(2026, 8, 26),
        review_summary=None,
    ):
        return ImportBatch.objects.create(
            source_upload=self.source_upload(filename),
            brand=self.brand,
            report_type="ITEMS",
            period_start=period_start,
            period_end=period_end,
            original_filename=filename,
            worksheet_name="Classeur",
            status=status,
            total_rows=0,
            accepted_rows=0,
            excluded_rows=0,
            stopped_rows=0,
            content_sha256=(
                f"{1000 + self._sha_counter:064x}"
                if status == ImportBatchStatus.APPROVED
                else ""
            ),
            review_summary=review_summary or {},
            uploaded_by=self.user,
            reviewed_by=self.user,
            approved_by=(
                self.user
                if status == ImportBatchStatus.APPROVED
                else None
            ),
        )

    def test_selects_multiple_legacy_approved_batches(self):
        liv03 = self.batch(
            "DCV-03 items_2026-04-04_to_2026-08-26.xlsx"
        )
        pliv01 = self.batch(
            "DLV-01 items_2026-04-04_to_2026-08-26.xlsx"
        )
        outside = self.batch(
            "DCV-07 items_2026-04-04_to_2026-08-26.xlsx"
        )

        plan = plan_items_detail_replacements(
            source_system_code="BIFA_MILA",
            brand_code="BIFA",
            covered_trucks=("BIFA LIV03", "BIFA PLIV01"),
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
        )

        self.assertEqual(
            plan.replacement_batch_ids,
            (liv03.pk, pliv01.pk),
        )
        self.assertNotIn(
            outside.pk,
            plan.replacement_batch_ids,
        )

    def test_mutable_overlap_for_covered_truck_is_rejected(self):
        mutable = self.batch(
            "DCV-03 items_2026-04-04_to_2026-08-26.xlsx",
            status=ImportBatchStatus.REVIEWED,
        )

        with self.assertRaises(
            RawItemsDetailReplacementError
        ) as captured:
            plan_items_detail_replacements(
                source_system_code="BIFA_MILA",
                brand_code="BIFA",
                covered_trucks=("BIFA LIV03",),
                period_start=date(2026, 4, 4),
                period_end=date(2026, 8, 26),
            )

        self.assertEqual(
            captured.exception.code,
            "items_detail_mutable_overlap_conflict",
        )
        self.assertEqual(
            captured.exception.details["batch_id"],
            mutable.pk,
        )

    def test_partial_period_overlap_is_rejected(self):
        approved = self.batch(
            "DCV-03 items_2026-04-04_to_2026-08-26.xlsx",
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 10),
        )

        with self.assertRaises(
            RawItemsDetailReplacementError
        ) as captured:
            plan_items_detail_replacements(
                source_system_code="BIFA_MILA",
                brand_code="BIFA",
                covered_trucks=("BIFA LIV03",),
                period_start=date(2026, 4, 4),
                period_end=date(2026, 8, 26),
            )

        self.assertEqual(
            captured.exception.code,
            "items_detail_period_overlap_conflict",
        )
        self.assertEqual(
            captured.exception.details["batch_id"],
            approved.pk,
        )

    def test_previous_detail_batch_can_be_replaced_as_one_target(self):
        previous = self.batch(
            "BIFA_Items_DETAIL_old.xlsx",
            review_summary={
                "items_detail": {
                    "transaction_level": True,
                    "covered_trucks": [
                        "BIFA LIV03",
                        "BIFA PLIV01",
                    ],
                }
            },
        )

        plan = plan_items_detail_replacements(
            source_system_code="BIFA_MILA",
            brand_code="BIFA",
            covered_trucks=("BIFA LIV03", "BIFA PLIV01"),
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
        )

        self.assertEqual(
            plan.replacement_batch_ids,
            (previous.pk,),
        )

    def test_previous_detail_batch_partial_truck_scope_is_rejected(self):
        previous = self.batch(
            "BIFA_Items_DETAIL_old.xlsx",
            review_summary={
                "items_detail": {
                    "transaction_level": True,
                    "covered_trucks": [
                        "BIFA LIV03",
                        "BIFA PLIV01",
                    ],
                }
            },
        )

        with self.assertRaises(
            RawItemsDetailReplacementError
        ) as captured:
            plan_items_detail_replacements(
                source_system_code="BIFA_MILA",
                brand_code="BIFA",
                covered_trucks=("BIFA LIV03",),
                period_start=date(2026, 4, 4),
                period_end=date(2026, 8, 26),
            )

        self.assertEqual(
            captured.exception.code,
            "items_detail_partial_truck_scope_conflict",
        )
        self.assertEqual(
            captured.exception.details["batch_id"],
            previous.pk,
        )
