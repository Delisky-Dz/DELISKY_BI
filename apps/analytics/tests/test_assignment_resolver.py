from datetime import date

from django.test import TestCase

from apps.analytics.services.assignment_resolver import (
    AssignmentResolutionStatus,
    build_assignment_index,
    resolve_worker_for_date,
    resolve_worker_for_period,
)
from apps.fleet.models import Truck, TruckCrewAssignment
from apps.workforce.models import Worker


class AssignmentResolverTests(TestCase):
    def create_worker(
        self,
        code,
        *,
        is_active=True,
    ):
        return Worker.objects.create(
            employee_code=code,
            first_name="Test",
            last_name=code,
            is_active=is_active,
        )

    def create_truck(
        self,
        code,
        *,
        is_active=True,
    ):
        return Truck.objects.create(
            internal_code=code,
            registration_number=f"REG-{code}",
            brand="TEST BRAND",
            model="TEST MODEL",
            is_active=is_active,
        )

    def create_assignment(
        self,
        *,
        worker,
        truck,
        start_date,
        end_date=None,
    ):
        return TruckCrewAssignment.objects.create(
            worker=worker,
            truck=truck,
            crew_role=(
                TruckCrewAssignment.CrewRole.SELLER
            ),
            is_primary_seller=True,
            start_date=start_date,
            end_date=end_date,
        )

    def test_index_includes_inactive_historical_records(self):
        worker = self.create_worker(
            "WORKER-INACTIVE",
            is_active=False,
        )
        truck = self.create_truck(
            "TRUCK-INACTIVE",
            is_active=False,
        )
        assignment = self.create_assignment(
            worker=worker,
            truck=truck,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        index = build_assignment_index()

        self.assertIn(truck.pk, index)
        self.assertEqual(
            index[truck.pk],
            (assignment,),
        )

    def test_exact_date_resolves_matching_worker(self):
        worker = self.create_worker("WORKER-DATE")
        truck = self.create_truck("TRUCK-DATE")
        assignment = self.create_assignment(
            worker=worker,
            truck=truck,
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 10),
        )

        result = resolve_worker_for_date(
            truck,
            date(2026, 2, 5),
        )

        self.assertEqual(
            result.status,
            AssignmentResolutionStatus.MATCHED,
        )
        self.assertTrue(result.is_matched)
        self.assertEqual(result.worker, worker)
        self.assertEqual(result.assignment, assignment)

    def test_exact_date_boundaries_are_inclusive(self):
        worker = self.create_worker("WORKER-BOUNDARY")
        truck = self.create_truck("TRUCK-BOUNDARY")
        self.create_assignment(
            worker=worker,
            truck=truck,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 7),
        )

        start_result = resolve_worker_for_date(
            truck,
            date(2026, 3, 1),
        )
        end_result = resolve_worker_for_date(
            truck,
            date(2026, 3, 7),
        )

        self.assertEqual(
            start_result.status,
            AssignmentResolutionStatus.MATCHED,
        )
        self.assertEqual(
            end_result.status,
            AssignmentResolutionStatus.MATCHED,
        )
        self.assertEqual(start_result.worker, worker)
        self.assertEqual(end_result.worker, worker)

    def test_exact_date_without_assignment(self):
        truck = self.create_truck("TRUCK-NO-DATE")

        result = resolve_worker_for_date(
            truck,
            date(2026, 4, 1),
        )

        self.assertEqual(
            result.status,
            AssignmentResolutionStatus.NO_ASSIGNMENT,
        )
        self.assertFalse(result.is_matched)
        self.assertIsNone(result.worker)

    def test_exact_date_multiple_matches_are_ambiguous(self):
        truck = self.create_truck("TRUCK-AMBIGUOUS")
        first_worker = self.create_worker("WORKER-AMBIGUOUS-1")
        second_worker = self.create_worker("WORKER-AMBIGUOUS-2")

        first_assignment = TruckCrewAssignment(
            pk=9001,
            worker=first_worker,
            truck=truck,
            crew_role=(
                TruckCrewAssignment.CrewRole.SELLER
            ),
            is_primary_seller=True,
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 10),
        )
        second_assignment = TruckCrewAssignment(
            pk=9002,
            worker=second_worker,
            truck=truck,
            crew_role=(
                TruckCrewAssignment.CrewRole.SELLER
            ),
            is_primary_seller=True,
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 10),
        )

        result = resolve_worker_for_date(
            truck,
            date(2026, 5, 5),
            assignment_index={
                truck.pk: (
                    first_assignment,
                    second_assignment,
                )
            },
        )

        self.assertEqual(
            result.status,
            AssignmentResolutionStatus.AMBIGUOUS_ASSIGNMENT,
        )
        self.assertFalse(result.is_matched)
        self.assertIsNone(result.worker)
        self.assertEqual(
            result.matching_assignment_ids,
            (9001, 9002),
        )

    def test_period_with_full_coverage_resolves_worker(self):
        worker = self.create_worker("WORKER-PERIOD")
        truck = self.create_truck("TRUCK-PERIOD")
        assignment = self.create_assignment(
            worker=worker,
            truck=truck,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
        )

        result = resolve_worker_for_period(
            truck,
            date(2026, 6, 5),
            date(2026, 6, 20),
        )

        self.assertEqual(
            result.status,
            AssignmentResolutionStatus.MATCHED,
        )
        self.assertTrue(result.is_matched)
        self.assertEqual(result.worker, worker)
        self.assertEqual(result.assignment, assignment)

    def test_period_with_partial_coverage_is_not_attributed(self):
        worker = self.create_worker("WORKER-PARTIAL")
        truck = self.create_truck("TRUCK-PARTIAL")
        assignment = self.create_assignment(
            worker=worker,
            truck=truck,
            start_date=date(2026, 7, 3),
            end_date=date(2026, 7, 7),
        )

        result = resolve_worker_for_period(
            truck,
            date(2026, 7, 1),
            date(2026, 7, 7),
        )

        self.assertEqual(
            result.status,
            AssignmentResolutionStatus.PARTIAL_COVERAGE,
        )
        self.assertFalse(result.is_matched)
        self.assertIsNone(result.worker)
        self.assertEqual(
            result.matching_assignment_ids,
            (assignment.pk,),
        )

    def test_period_with_worker_change_is_not_attributed(self):
        truck = self.create_truck("TRUCK-CHANGE")
        first_worker = self.create_worker("WORKER-CHANGE-1")
        second_worker = self.create_worker("WORKER-CHANGE-2")

        first_assignment = self.create_assignment(
            worker=first_worker,
            truck=truck,
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 3),
        )
        second_assignment = self.create_assignment(
            worker=second_worker,
            truck=truck,
            start_date=date(2026, 8, 4),
            end_date=date(2026, 8, 7),
        )

        result = resolve_worker_for_period(
            truck,
            date(2026, 8, 1),
            date(2026, 8, 7),
        )

        self.assertEqual(
            result.status,
            AssignmentResolutionStatus.MULTIPLE_ASSIGNMENTS,
        )
        self.assertFalse(result.is_matched)
        self.assertIsNone(result.worker)
        self.assertEqual(
            result.matching_assignment_ids,
            tuple(
                sorted(
                    (
                        first_assignment.pk,
                        second_assignment.pk,
                    )
                )
            ),
        )

    def test_invalid_period_is_rejected(self):
        truck = self.create_truck("TRUCK-INVALID-PERIOD")

        result = resolve_worker_for_period(
            truck,
            date(2026, 9, 10),
            date(2026, 9, 1),
        )

        self.assertEqual(
            result.status,
            AssignmentResolutionStatus.INVALID_PERIOD,
        )
        self.assertFalse(result.is_matched)

    def test_missing_truck_is_reported(self):
        date_result = resolve_worker_for_date(
            None,
            date(2026, 10, 1),
        )
        period_result = resolve_worker_for_period(
            None,
            date(2026, 10, 1),
            date(2026, 10, 7),
        )

        self.assertEqual(
            date_result.status,
            AssignmentResolutionStatus.MISSING_TRUCK,
        )
        self.assertEqual(
            period_result.status,
            AssignmentResolutionStatus.MISSING_TRUCK,
        )
