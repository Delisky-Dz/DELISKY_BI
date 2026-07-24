from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.workforce.models import (
    Worker,
    WorkerCategory,
    WorkerPositionPeriod,
)


class WorkerPositionPeriodModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = WorkerCategory.objects.create(
            code="TEST_POSITION",
            name="Test position",
            sort_order=900,
        )
        cls.other_category = WorkerCategory.objects.create(
            code="TEST_POSITION_2",
            name="Second test position",
            sort_order=901,
        )

        cls.worker = Worker.objects.create(
            employee_code="TEST-WORKER-001",
            first_name="First",
            last_name="Worker",
        )
        cls.other_worker = Worker.objects.create(
            employee_code="TEST-WORKER-002",
            first_name="Second",
            last_name="Worker",
        )

    def test_current_period_is_current(self):
        period = WorkerPositionPeriod(
            worker=self.worker,
            category=self.category,
            start_date=date.today(),
            end_date=None,
        )

        self.assertTrue(period.is_current)

    def test_future_period_is_not_current(self):
        period = WorkerPositionPeriod(
            worker=self.worker,
            category=self.category,
            start_date=(
                date.today()
                + timedelta(days=1)
            ),
            end_date=None,
        )

        self.assertFalse(period.is_current)

    def test_finished_period_is_not_current(self):
        period = WorkerPositionPeriod(
            worker=self.worker,
            category=self.category,
            start_date=(
                date.today()
                - timedelta(days=10)
            ),
            end_date=(
                date.today()
                - timedelta(days=1)
            ),
        )

        self.assertFalse(period.is_current)

    def test_end_date_before_start_is_rejected(self):
        period = WorkerPositionPeriod(
            worker=self.worker,
            category=self.category,
            start_date=date(2026, 2, 10),
            end_date=date(2026, 2, 9),
        )

        with self.assertRaises(
            ValidationError
        ) as error:
            period.full_clean()

        self.assertIn(
            "end_date",
            error.exception.message_dict,
        )

    def test_overlapping_period_is_rejected_by_validation(
        self,
    ):
        WorkerPositionPeriod.objects.create(
            worker=self.worker,
            category=self.category,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        overlapping = WorkerPositionPeriod(
            worker=self.worker,
            category=self.other_category,
            start_date=date(2026, 1, 15),
            end_date=date(2026, 2, 15),
        )

        with self.assertRaises(
            ValidationError
        ) as error:
            overlapping.full_clean()

        self.assertIn(
            "worker",
            error.exception.message_dict,
        )

    def test_same_boundary_day_is_overlapping(self):
        WorkerPositionPeriod.objects.create(
            worker=self.worker,
            category=self.category,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        overlapping = WorkerPositionPeriod(
            worker=self.worker,
            category=self.other_category,
            start_date=date(2026, 1, 31),
            end_date=None,
        )

        with self.assertRaises(
            ValidationError
        ):
            overlapping.full_clean()

    def test_next_day_period_is_allowed(self):
        WorkerPositionPeriod.objects.create(
            worker=self.worker,
            category=self.category,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        next_period = WorkerPositionPeriod(
            worker=self.worker,
            category=self.other_category,
            start_date=date(2026, 2, 1),
            end_date=None,
        )

        next_period.full_clean()
        next_period.save()

        self.assertEqual(
            WorkerPositionPeriod.objects.filter(
                worker=self.worker
            ).count(),
            2,
        )

    def test_same_period_is_allowed_for_different_workers(
        self,
    ):
        WorkerPositionPeriod.objects.create(
            worker=self.worker,
            category=self.category,
            start_date=date(2026, 1, 1),
            end_date=None,
        )

        other_period = WorkerPositionPeriod(
            worker=self.other_worker,
            category=self.category,
            start_date=date(2026, 1, 1),
            end_date=None,
        )

        other_period.full_clean()
        other_period.save()

        self.assertEqual(
            WorkerPositionPeriod.objects.count(),
            2,
        )

    def test_database_constraint_rejects_overlap(
        self,
    ):
        WorkerPositionPeriod.objects.create(
            worker=self.worker,
            category=self.category,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WorkerPositionPeriod.objects.create(
                    worker=self.worker,
                    category=self.other_category,
                    start_date=date(2026, 1, 20),
                    end_date=None,
                )
