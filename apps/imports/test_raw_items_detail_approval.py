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
from apps.imports.services.raw_items_detail_approval import (
    approve_items_detail_batch,
)


class RawItemsDetailApprovalTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="items-detail-approver", password="x"
        )
        self.brand = DistributionBrand.objects.create(
            code="BIFA",
            name="BIFA",
        )
        self.source_system = ImportSourceSystem.objects.create(
            code="BIFA_MILA",
            name="BIFA Mila",
        )

        self.liv03 = Truck.objects.create(
            internal_code="BIFA LIV03",
            distribution_brand=self.brand,
            registration_number="DETAIL-APPROVAL-LIV03",
            brand="BIFA",
            model="",
        )
        self.liv07 = Truck.objects.create(
            internal_code="BIFA LIV07",
            distribution_brand=self.brand,
            registration_number="DETAIL-APPROVAL-LIV07",
            brand="BIFA",
            model="",
        )

        for source_code, truck in (
            ("DCV-03", self.liv03),
            ("DCV-07", self.liv07),
        ):
            SourceTruckMapping.objects.create(
                source_system=self.source_system,
                source_code=source_code,
                truck=truck,
                is_active=True,
            )

    def _upload(self, filename, sha):
        return ImportSourceUpload.objects.create(
            source_system=self.source_system,
            original_filename=filename,
            file_size_bytes=1,
            file_sha256=sha,
            uploaded_by=self.user,
        )

    def _legacy(self, filename, sha):
        return ImportBatch.objects.create(
            source_upload=self._upload(filename, sha),
            brand=self.brand,
            report_type="ITEMS",
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
            original_filename=filename,
            status=ImportBatchStatus.APPROVED,
            content_sha256=sha,
            uploaded_by=self.user,
            reviewed_by=self.user,
            approved_by=self.user,
        )

    def test_approval_supersedes_all_covered_legacy_batches_atomically(self):
        first = self._legacy(
            "DCV-03 items_2026-04-04_to_2026-08-26.xlsx",
            "1" * 64,
        )
        second = self._legacy(
            "DCV-07 items_2026-04-04_to_2026-08-26.xlsx",
            "2" * 64,
        )
        detail_upload = self._upload(
            "BIFA_Items_DETAIL_2026-04-04_to_2026-08-26.xlsx",
            "3" * 64,
        )
        detail = ImportBatch.objects.create(
            source_upload=detail_upload,
            brand=self.brand,
            report_type="ITEMS",
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
            original_filename=detail_upload.original_filename,
            status=ImportBatchStatus.REVIEWED,
            content_sha256="4" * 64,
            uploaded_by=self.user,
            reviewed_by=self.user,
            review_summary={
                "items_detail": {
                    "transaction_level": True,
                    "covered_trucks": [
                        "BIFA LIV03",
                        "BIFA LIV07",
                    ],
                }
            },
        )

        result = approve_items_detail_batch(
            detail,
            approved_by=self.user,
        )

        detail.refresh_from_db()
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(
            detail.status,
            ImportBatchStatus.APPROVED,
        )
        self.assertEqual(
            first.status,
            ImportBatchStatus.SUPERSEDED,
        )
        self.assertEqual(
            second.status,
            ImportBatchStatus.SUPERSEDED,
        )
        self.assertEqual(
            result.superseded_batch_ids,
            (first.pk, second.pk),
        )
