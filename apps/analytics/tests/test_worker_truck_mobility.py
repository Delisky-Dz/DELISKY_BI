from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.analytics.services.pos_visit_aggregation import (
    DailyBrandTruckWorkerVisitTotal,
    VisitMetrics,
)
from apps.analytics.services.sales_aggregation import (
    DailyBrandTruckWorkerSalesTotal,
    SalesMetrics,
)
from apps.analytics.services.worker_truck_mobility import (
    MobilityTransitionType,
    build_worker_truck_mobility,
)
from apps.fleet.models import Truck, TruckCrewAssignment
from apps.imports.models import DistributionBrand
from apps.workforce.models import Worker


class WorkerTruckMobilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.brand = DistributionBrand.objects.create(
            code="MOBILITY_TEST",
            name="Mobility Test Brand",
        )

    def create_truck(self, sequence):
        return Truck.objects.create(
            internal_code=f"MOBILITY-TRUCK-{sequence}",
            registration_number=f"MOBILITY-REG-{sequence}",
            brand="TEST",
            model="TEST",
        )

    def create_worker(self, sequence):
        return Worker.objects.create(
            employee_code=f"MOBILITY-WORKER-{sequence}",
            first_name="Test",
            last_name=f"Worker {sequence}",
        )

    def create_assignment(
        self,
        *,
        worker,
        truck,
        start_date,
        end_date,
        primary=True,
    ):
        return TruckCrewAssignment.objects.create(
            worker=worker,
            truck=truck,
            crew_role=(
                TruckCrewAssignment.CrewRole.SELLER
            ),
            is_primary_seller=primary,
            start_date=start_date,
            end_date=end_date,
        )

    def sales_row(
        self,
        *,
        day,
        worker,
        truck,
        total,
    ):
        return DailyBrandTruckWorkerSalesTotal(
            sale_date=day,
            brand_id=self.brand.pk,
            truck_id=truck.pk,
            worker_id=worker.pk,
            metrics=SalesMetrics(
                total_sales=Decimal(total),
                sale_record_count=1,
                positive_sale_record_count=1,
                zero_total_record_count=0,
            ),
        )

    def visit_row(
        self,
        *,
        day,
        worker,
        truck,
        visited,
        not_visited,
    ):
        total = visited + not_visited

        return DailyBrandTruckWorkerVisitTotal(
            visit_date=day,
            brand_id=self.brand.pk,
            truck_id=truck.pk,
            worker_id=worker.pk,
            metrics=VisitMetrics(
                total_record_count=total,
                visited_record_count=visited,
                not_visited_record_count=not_visited,
                unique_client_day_count=total,
            ),
        )

    def test_same_worker_moving_truck_is_compared(self):
        worker = self.create_worker(1)
        first_truck = self.create_truck(1)
        second_truck = self.create_truck(2)

        first = self.create_assignment(
            worker=worker,
            truck=first_truck,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        second = self.create_assignment(
            worker=worker,
            truck=second_truck,
            start_date=date(2026, 7, 4),
            end_date=date(2026, 7, 6),
        )

        result = build_worker_truck_mobility(
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 6),
            assignments=(first, second),
            sales_daily=(
                self.sales_row(
                    day=date(2026, 7, 1),
                    worker=worker,
                    truck=first_truck,
                    total="100",
                ),
                self.sales_row(
                    day=date(2026, 7, 4),
                    worker=worker,
                    truck=second_truck,
                    total="160",
                ),
            ),
            visit_daily=(
                self.visit_row(
                    day=date(2026, 7, 1),
                    worker=worker,
                    truck=first_truck,
                    visited=2,
                    not_visited=2,
                ),
                self.visit_row(
                    day=date(2026, 7, 4),
                    worker=worker,
                    truck=second_truck,
                    visited=3,
                    not_visited=1,
                ),
            ),
        )

        self.assertEqual(
            len(result.worker_moves),
            1,
        )

        comparison = result.worker_moves[0]

        self.assertEqual(
            comparison.transition_type,
            MobilityTransitionType.WORKER_CHANGED_TRUCK,
        )
        self.assertEqual(
            comparison.before.worker_id,
            worker.pk,
        )
        self.assertEqual(
            comparison.after.worker_id,
            worker.pk,
        )
        self.assertEqual(
            comparison.before.truck_id,
            first_truck.pk,
        )
        self.assertEqual(
            comparison.after.truck_id,
            second_truck.pk,
        )
        self.assertEqual(
            comparison.sales_total_delta,
            Decimal("60"),
        )
        self.assertEqual(
            comparison.visit_success_rate_delta,
            Decimal("0.25"),
        )

    def test_same_truck_changing_worker_is_compared(self):
        truck = self.create_truck(3)
        first_worker = self.create_worker(3)
        second_worker = self.create_worker(4)

        first = self.create_assignment(
            worker=first_worker,
            truck=truck,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        second = self.create_assignment(
            worker=second_worker,
            truck=truck,
            start_date=date(2026, 7, 4),
            end_date=date(2026, 7, 6),
        )

        result = build_worker_truck_mobility(
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 6),
            assignments=(first, second),
            sales_daily=(
                self.sales_row(
                    day=date(2026, 7, 1),
                    worker=first_worker,
                    truck=truck,
                    total="100",
                ),
                self.sales_row(
                    day=date(2026, 7, 4),
                    worker=second_worker,
                    truck=truck,
                    total="80",
                ),
            ),
        )

        self.assertEqual(
            len(result.truck_seller_changes),
            1,
        )

        comparison = (
            result.truck_seller_changes[0]
        )

        self.assertEqual(
            comparison.before.worker_id,
            first_worker.pk,
        )
        self.assertEqual(
            comparison.after.worker_id,
            second_worker.pk,
        )
        self.assertEqual(
            comparison.before.truck_id,
            truck.pk,
        )
        self.assertEqual(
            comparison.after.truck_id,
            truck.pk,
        )
        self.assertEqual(
            comparison.sales_total_delta,
            Decimal("-20"),
        )

    def test_windows_use_equal_working_day_count(self):
        worker = self.create_worker(5)
        first_truck = self.create_truck(5)
        second_truck = self.create_truck(6)

        first = self.create_assignment(
            worker=worker,
            truck=first_truck,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 10),
        )
        second = self.create_assignment(
            worker=worker,
            truck=second_truck,
            start_date=date(2026, 7, 11),
            end_date=date(2026, 7, 12),
        )

        result = build_worker_truck_mobility(
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 12),
            assignments=(first, second),
            sales_daily=(
                self.sales_row(
                    day=date(2026, 7, 1),
                    worker=worker,
                    truck=first_truck,
                    total="900",
                ),
                self.sales_row(
                    day=date(2026, 7, 7),
                    worker=worker,
                    truck=first_truck,
                    total="40",
                ),
                self.sales_row(
                    day=date(2026, 7, 8),
                    worker=worker,
                    truck=first_truck,
                    total="60",
                ),
                self.sales_row(
                    day=date(2026, 7, 10),
                    worker=worker,
                    truck=first_truck,
                    total="900",
                ),
                self.sales_row(
                    day=date(2026, 7, 11),
                    worker=worker,
                    truck=second_truck,
                    total="100",
                ),
                self.sales_row(
                    day=date(2026, 7, 12),
                    worker=worker,
                    truck=second_truck,
                    total="120",
                ),
            ),
        )

        comparison = result.worker_moves[0]

        self.assertEqual(
            comparison.before.working_day_count,
            2,
        )
        self.assertEqual(
            comparison.after.working_day_count,
            2,
        )
        self.assertEqual(
            comparison.before.sales_measurement_day_count,
            2,
        )
        self.assertEqual(
            comparison.after.sales_measurement_day_count,
            2,
        )
        self.assertEqual(
            comparison.before.period_start,
            date(2026, 7, 7),
        )
        self.assertEqual(
            comparison.before.period_end,
            date(2026, 7, 8),
        )
        self.assertEqual(
            comparison.before.sales_total,
            Decimal("100"),
        )
        self.assertEqual(
            comparison.after.sales_total,
            Decimal("220"),
        )

    def test_incomparable_measurements_are_not_emitted(self):
        worker = self.create_worker(7)
        first_truck = self.create_truck(7)
        second_truck = self.create_truck(8)

        first = self.create_assignment(
            worker=worker,
            truck=first_truck,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        second = self.create_assignment(
            worker=worker,
            truck=second_truck,
            start_date=date(2026, 7, 4),
            end_date=date(2026, 7, 6),
        )

        result = build_worker_truck_mobility(
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 6),
            assignments=(first, second),
            sales_daily=(
                self.sales_row(
                    day=date(2026, 7, 1),
                    worker=worker,
                    truck=first_truck,
                    total="100",
                ),
            ),
            visit_daily=(
                self.visit_row(
                    day=date(2026, 7, 4),
                    worker=worker,
                    truck=second_truck,
                    visited=1,
                    not_visited=0,
                ),
            ),
        )

        self.assertEqual(
            result.comparisons,
            (),
        )

    def test_non_primary_assignment_is_ignored(self):
        worker = self.create_worker(9)
        first_truck = self.create_truck(9)
        second_truck = self.create_truck(10)

        first = self.create_assignment(
            worker=worker,
            truck=first_truck,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        second = self.create_assignment(
            worker=worker,
            truck=second_truck,
            start_date=date(2026, 7, 4),
            end_date=date(2026, 7, 6),
            primary=False,
        )

        result = build_worker_truck_mobility(
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 6),
            assignments=(first, second),
        )

        self.assertEqual(
            result.comparisons,
            (),
        )

    def test_transition_gap_is_preserved(self):
        worker = self.create_worker(11)
        first_truck = self.create_truck(11)
        second_truck = self.create_truck(12)

        first = self.create_assignment(
            worker=worker,
            truck=first_truck,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        second = self.create_assignment(
            worker=worker,
            truck=second_truck,
            start_date=date(2026, 7, 6),
            end_date=date(2026, 7, 8),
        )

        result = build_worker_truck_mobility(
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 8),
            assignments=(first, second),
            sales_daily=(
                self.sales_row(
                    day=date(2026, 7, 1),
                    worker=worker,
                    truck=first_truck,
                    total="100",
                ),
                self.sales_row(
                    day=date(2026, 7, 6),
                    worker=worker,
                    truck=second_truck,
                    total="120",
                ),
            ),
        )

        comparison = result.worker_moves[0]

        self.assertEqual(
            comparison.gap_working_day_count,
            2,
        )
        self.assertFalse(
            comparison.is_contiguous_transition
        )

    def test_database_assignments_are_used_by_default(self):
        worker = self.create_worker(13)
        first_truck = self.create_truck(13)
        second_truck = self.create_truck(14)

        self.create_assignment(
            worker=worker,
            truck=first_truck,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        self.create_assignment(
            worker=worker,
            truck=second_truck,
            start_date=date(2026, 7, 4),
            end_date=date(2026, 7, 6),
        )

        result = build_worker_truck_mobility(
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 6),
            sales_daily=(
                self.sales_row(
                    day=date(2026, 7, 1),
                    worker=worker,
                    truck=first_truck,
                    total="100",
                ),
                self.sales_row(
                    day=date(2026, 7, 4),
                    worker=worker,
                    truck=second_truck,
                    total="150",
                ),
            ),
        )

        self.assertEqual(
            len(result.worker_moves),
            1,
        )
        self.assertEqual(
            result.worker_moves[0].sales_total_delta,
            Decimal("50"),
        )

    def test_invalid_period_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "period_end cannot be before period_start",
        ):
            build_worker_truck_mobility(
                period_start=date(2026, 7, 10),
                period_end=date(2026, 7, 1),
            )

    def test_thursday_friday_gap_is_operationally_contiguous(
        self,
    ):
        worker = self.create_worker(15)
        first_truck = self.create_truck(15)
        second_truck = self.create_truck(16)

        first = self.create_assignment(
            worker=worker,
            truck=first_truck,
            start_date=date(2026, 7, 6),
            end_date=date(2026, 7, 8),
        )
        second = self.create_assignment(
            worker=worker,
            truck=second_truck,
            start_date=date(2026, 7, 11),
            end_date=date(2026, 7, 13),
        )

        result = build_worker_truck_mobility(
            period_start=date(2026, 7, 6),
            period_end=date(2026, 7, 13),
            assignments=(first, second),
            sales_daily=(
                self.sales_row(
                    day=date(2026, 7, 8),
                    worker=worker,
                    truck=first_truck,
                    total="100",
                ),
                self.sales_row(
                    day=date(2026, 7, 11),
                    worker=worker,
                    truck=second_truck,
                    total="120",
                ),
            ),
        )

        comparison = result.worker_moves[0]

        self.assertEqual(
            comparison.gap_working_day_count,
            0,
        )
        self.assertTrue(
            comparison.is_contiguous_transition
        )

    def test_overlapping_manual_assignments_are_rejected(
        self,
    ):
        worker = self.create_worker(17)
        first_truck = self.create_truck(17)
        second_truck = self.create_truck(18)

        first = TruckCrewAssignment(
            worker=worker,
            truck=first_truck,
            crew_role=(
                TruckCrewAssignment.CrewRole.SELLER
            ),
            is_primary_seller=True,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 5),
        )
        second = TruckCrewAssignment(
            worker=worker,
            truck=second_truck,
            crew_role=(
                TruckCrewAssignment.CrewRole.SELLER
            ),
            is_primary_seller=True,
            start_date=date(2026, 7, 5),
            end_date=date(2026, 7, 8),
        )

        with self.assertRaisesRegex(
            ValueError,
            "Overlapping primary-seller assignments",
        ):
            build_worker_truck_mobility(
                period_start=date(2026, 7, 1),
                period_end=date(2026, 7, 8),
                assignments=(first, second),
            )
