from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.imports.models import (
    DistributionBrand,
    ImportBatch,
    ImportBatchStatus,
    ImportSourceSystem,
    ImportSourceUpload,
)


class RawItemsDetailBatchDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()

        accountant_group = Group.objects.create(
            name="Accountant"
        )
        cls.accountant = user_model.objects.create_user(
            username="items-detail-batch-view",
            password="test-pass-123",
            is_active=True,
        )
        cls.accountant.groups.add(
            accountant_group
        )

        cls.brand = DistributionBrand.objects.create(
            code="BIFA",
            name="BIFA",
        )
        cls.source_system = ImportSourceSystem.objects.create(
            code="BIFA_MILA",
            name="BIFA Mila",
        )

        cls.source_upload = ImportSourceUpload.objects.create(
            source_system=cls.source_system,
            original_filename=(
                "BIFA_Items_DETAIL_"
                "2026-04-04_to_2026-08-26.xlsx"
            ),
            worksheet_name="Classeur",
            file_size_bytes=1000,
            file_sha256="a" * 64,
            uploaded_by=cls.accountant,
            audit_metadata={
                "items_detail": {
                    "transaction_level": True,
                    "excluded_source_row_count": 280,
                    "excluded_source_groups": [
                        {
                            "source_code": "ADV",
                            "reason": "OUT_OF_SCOPE",
                            "count": 280,
                        }
                    ],
                }
            },
        )

        cls.previous = ImportBatch.objects.create(
            brand=cls.brand,
            report_type="ITEMS",
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
            original_filename=(
                "DCV-03 items_"
                "2026-04-04_to_2026-08-26.xlsx"
            ),
            file_size_bytes=500,
            file_sha256="b" * 64,
            content_sha256="c" * 64,
            status=ImportBatchStatus.APPROVED,
            total_rows=0,
            accepted_rows=0,
            excluded_rows=0,
            stopped_rows=0,
            uploaded_by=cls.accountant,
            reviewed_by=cls.accountant,
            approved_by=cls.accountant,
        )

        cls.detail = ImportBatch.objects.create(
            source_upload=cls.source_upload,
            brand=cls.brand,
            report_type="ITEMS",
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
            original_filename=(
                cls.source_upload.original_filename
            ),
            worksheet_name="Classeur",
            file_size_bytes=1000,
            content_sha256="d" * 64,
            status=ImportBatchStatus.REVIEWED,
            total_rows=0,
            accepted_rows=0,
            excluded_rows=0,
            stopped_rows=0,
            uploaded_by=cls.accountant,
            reviewed_by=cls.accountant,
            review_summary={
                "filename": (
                    cls.source_upload.original_filename
                ),
                "report_type": "ITEMS",
                "brand_code": "BIFA",
                "period_start": "2026-04-04",
                "period_end": "2026-08-26",
                "issue_groups": [],
                "items_detail": {
                    "transaction_level": True,
                    "covered_trucks": [
                        "BIFA LIV03",
                        "BIFA LIV07",
                    ],
                    "replacement_batch_ids": [
                        cls.previous.pk,
                    ],
                },
            },
        )

    def test_detail_page_shows_scope_replacements_and_source_audit(self):
        self.client.force_login(
            self.accountant
        )

        response = self.client.get(
            reverse(
                "imports:batch_detail",
                args=[self.detail.pk],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context[
                "source_file_sha256"
            ],
            "a" * 64,
        )
        self.assertEqual(
            [
                batch.pk
                for batch in response.context[
                    "detail_replacement_batches"
                ]
            ],
            [self.previous.pk],
        )

        self.assertContains(
            response,
            "BIFA LIV03",
        )
        self.assertContains(
            response,
            "BIFA LIV07",
        )
        self.assertContains(
            response,
            "ADV",
        )
        self.assertContains(
            response,
            "280",
        )
        self.assertContains(
            response,
            f"#{self.previous.pk}",
        )
        self.assertContains(
            response,
            "a" * 16,
        )
