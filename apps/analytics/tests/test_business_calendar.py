from datetime import date

from django.test import SimpleTestCase

from apps.analytics.services.business_calendar import (
    delisky_working_dates,
    is_delisky_working_day,
)


class BusinessCalendarTests(SimpleTestCase):
    def test_delisky_weekly_working_days(self):
        self.assertTrue(
            is_delisky_working_day(
                date(2026, 7, 8)
            )
        )
        self.assertFalse(
            is_delisky_working_day(
                date(2026, 7, 9)
            )
        )
        self.assertFalse(
            is_delisky_working_day(
                date(2026, 7, 10)
            )
        )
        self.assertTrue(
            is_delisky_working_day(
                date(2026, 7, 11)
            )
        )
        self.assertTrue(
            is_delisky_working_day(
                date(2026, 7, 12)
            )
        )

    def test_working_dates_exclude_thursday_and_friday(self):
        self.assertEqual(
            delisky_working_dates(
                date(2026, 7, 8),
                date(2026, 7, 12),
            ),
            (
                date(2026, 7, 8),
                date(2026, 7, 11),
                date(2026, 7, 12),
            ),
        )

    def test_invalid_period_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "period_end cannot be before period_start",
        ):
            delisky_working_dates(
                date(2026, 7, 10),
                date(2026, 7, 1),
            )
