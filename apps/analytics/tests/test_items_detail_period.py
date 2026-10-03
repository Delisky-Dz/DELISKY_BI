from datetime import date, datetime

from django.test import SimpleTestCase

from apps.analytics.services.items_detail_period import (
    resolve_items_row_period_scope,
)
from apps.analytics.services.items_period_filter import (
    ItemsRowPeriodStatus,
)


class ItemsDetailPeriodScopeTests(SimpleTestCase):
    def test_detail_row_uses_sale_date_for_filter_and_attribution(self):
        result = resolve_items_row_period_scope(
            batch_period_start=date(2026, 4, 4),
            batch_period_end=date(2026, 8, 26),
            sale_datetime=datetime(2026, 6, 15, 10, 30),
            requested_period_start=date(2026, 6, 15),
            requested_period_end=date(2026, 6, 15),
        )

        self.assertEqual(result.status, ItemsRowPeriodStatus.INCLUDED)
        self.assertTrue(result.uses_exact_sale_date)
        self.assertEqual(result.attribution_period_start, date(2026, 6, 15))
        self.assertEqual(result.attribution_period_end, date(2026, 6, 15))

    def test_detail_row_outside_request_keeps_real_attribution_date(self):
        result = resolve_items_row_period_scope(
            batch_period_start=date(2026, 4, 4),
            batch_period_end=date(2026, 8, 26),
            sale_datetime=datetime(2026, 6, 14, 23, 59),
            requested_period_start=date(2026, 6, 15),
            requested_period_end=date(2026, 6, 15),
        )

        self.assertEqual(result.status, ItemsRowPeriodStatus.OUTSIDE)
        self.assertTrue(result.uses_exact_sale_date)
        self.assertEqual(result.attribution_period_start, date(2026, 6, 14))
        self.assertEqual(result.attribution_period_end, date(2026, 6, 14))

    def test_legacy_row_keeps_batch_period_for_attribution(self):
        result = resolve_items_row_period_scope(
            batch_period_start=date(2026, 4, 4),
            batch_period_end=date(2026, 8, 26),
            sale_datetime=None,
            requested_period_start=date(2026, 4, 4),
            requested_period_end=date(2026, 8, 26),
        )

        self.assertEqual(result.status, ItemsRowPeriodStatus.INCLUDED)
        self.assertFalse(result.uses_exact_sale_date)
        self.assertEqual(result.attribution_period_start, date(2026, 4, 4))
        self.assertEqual(result.attribution_period_end, date(2026, 8, 26))

    def test_legacy_partial_overlap_remains_excluded(self):
        result = resolve_items_row_period_scope(
            batch_period_start=date(2026, 4, 4),
            batch_period_end=date(2026, 8, 26),
            sale_datetime=None,
            requested_period_start=date(2026, 6, 1),
            requested_period_end=date(2026, 6, 30),
        )

        self.assertEqual(result.status, ItemsRowPeriodStatus.PARTIAL_OVERLAP)
        self.assertFalse(result.uses_exact_sale_date)
