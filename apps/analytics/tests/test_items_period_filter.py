from datetime import date, datetime

from django.test import SimpleTestCase

from apps.analytics.services.items_period_filter import (
    ItemsRowPeriodStatus,
    decide_items_row_period,
)


class ItemsRowPeriodFilterTests(SimpleTestCase):
    def test_detail_row_uses_sale_date_inside_partial_batch_overlap(self):
        decision = decide_items_row_period(
            batch_period_start=date(2026, 4, 4),
            batch_period_end=date(2026, 8, 26),
            sale_datetime=datetime(2026, 7, 5, 10, 30),
            requested_period_start=date(2026, 7, 5),
            requested_period_end=date(2026, 7, 5),
        )

        self.assertEqual(decision.status, ItemsRowPeriodStatus.INCLUDED)
        self.assertTrue(decision.uses_exact_sale_date)

    def test_detail_row_outside_requested_day_is_excluded_exactly(self):
        decision = decide_items_row_period(
            batch_period_start=date(2026, 4, 4),
            batch_period_end=date(2026, 8, 26),
            sale_datetime=datetime(2026, 7, 6, 0, 1),
            requested_period_start=date(2026, 7, 5),
            requested_period_end=date(2026, 7, 5),
        )

        self.assertEqual(decision.status, ItemsRowPeriodStatus.OUTSIDE)
        self.assertTrue(decision.uses_exact_sale_date)

    def test_legacy_row_keeps_conservative_partial_overlap_rule(self):
        decision = decide_items_row_period(
            batch_period_start=date(2026, 7, 1),
            batch_period_end=date(2026, 7, 7),
            sale_datetime=None,
            requested_period_start=date(2026, 7, 3),
            requested_period_end=date(2026, 7, 7),
        )

        self.assertEqual(
            decision.status,
            ItemsRowPeriodStatus.PARTIAL_OVERLAP,
        )
        self.assertFalse(decision.uses_exact_sale_date)

    def test_legacy_row_fully_contained_is_included(self):
        decision = decide_items_row_period(
            batch_period_start=date(2026, 7, 1),
            batch_period_end=date(2026, 7, 7),
            sale_datetime=None,
            requested_period_start=date(2026, 7, 1),
            requested_period_end=date(2026, 7, 31),
        )

        self.assertEqual(decision.status, ItemsRowPeriodStatus.INCLUDED)
        self.assertFalse(decision.uses_exact_sale_date)
