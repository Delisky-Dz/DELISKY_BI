from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.imports.models import (
    DistributionBrand,
    ImportBatch,
    ImportBatchStatus,
    ImportReportType,
)

from .templatetags.manager_product_coverage import (
    items_period_guidance,
)


class ManagerItemsPeriodGuidanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="items-period-guidance",
            password="test-password",
        )
        cls.brand = DistributionBrand.objects.create(
            code="GUIDANCE",
            name="Guidance Brand",
            is_active=True,
        )
        cls.other_brand = DistributionBrand.objects.create(
            code="GUIDANCE-OTHER",
            name="Other Guidance Brand",
            is_active=True,
        )
        ImportBatch.objects.create(
            brand=cls.brand,
            report_type=ImportReportType.ITEMS,
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
            original_filename="items-guidance.xlsx",
            status=ImportBatchStatus.APPROVED,
            total_rows=1,
            accepted_rows=1,
            uploaded_by=cls.user,
        )

    def test_partial_month_reports_full_items_source_period(self):
        guidance = items_period_guidance(
            date(2026, 7, 1),
            date(2026, 7, 31),
            self.brand,
        )

        self.assertTrue(guidance.has_overlapping_sources)
        self.assertTrue(guidance.has_partial_overlap)
        self.assertEqual(len(guidance.source_periods), 1)
        self.assertIsNotNone(guidance.suggested_period)
        self.assertEqual(
            guidance.suggested_period.start,
            date(2026, 4, 4),
        )
        self.assertEqual(
            guidance.suggested_period.end,
            date(2026, 8, 26),
        )

    def test_full_items_period_is_not_marked_partial(self):
        guidance = items_period_guidance(
            date(2026, 4, 4),
            date(2026, 8, 26),
            self.brand,
        )

        self.assertTrue(guidance.has_overlapping_sources)
        self.assertFalse(guidance.has_partial_overlap)
        self.assertIsNone(guidance.suggested_period)

    def test_brand_filter_does_not_borrow_other_brand_items(self):
        guidance = items_period_guidance(
            date(2026, 7, 1),
            date(2026, 7, 31),
            self.other_brand,
        )

        self.assertFalse(guidance.has_overlapping_sources)
        self.assertFalse(guidance.has_partial_overlap)
        self.assertEqual(guidance.source_periods, ())
