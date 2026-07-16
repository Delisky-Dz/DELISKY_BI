from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.workforce.models import Worker

from .models import Truck, WorkerTruckAssignment


class WorkerTruckAssignmentTests(TestCase):
    def setUp(self):
        self.worker_1 = Worker.objects.create(
            employee_code="TEST-W001",
            first_name="Worker",
            last_name="One",
        )
        self.worker_2 = Worker.objects.create(
            employee_code="TEST-W002",
            first_name="Worker",
            last_name="Two",
        )

        self.truck_1 = Truck.objects.create(
            internal_code="TEST-T001",
            registration_number="TEST-001-26",
            brand="Test",
            model="Truck One",
            manufacturing_year=2020,
        )
        self.truck_2 = Truck.objects.create(
            internal_code="TEST-T002",
            registration_number="TEST-002-26",
            brand="Test",
            model="Truck Two",
            manufacturing_year=2021,
        )

    def test_accepts_valid_non_overlapping_assignments(self):
        WorkerTruckAssignment.objects.create(
            worker=self.worker_1,
            truck=self.truck_1,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 10),
        )

        assignment = WorkerTruckAssignment(
            worker=self.worker_2,
            truck=self.truck_1,
            start_date=date(2026, 7, 11),
            end_date=date(2026, 7, 20),
        )

        assignment.full_clean()
        assignment.save()

        self.assertEqual(
            WorkerTruckAssignment.objects.count(),
            2,
        )

    def test_rejects_overlapping_workers_on_same_truck(self):
        WorkerTruckAssignment.objects.create(
            worker=self.worker_1,
            truck=self.truck_1,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 15),
        )

        assignment = WorkerTruckAssignment(
            worker=self.worker_2,
            truck=self.truck_1,
            start_date=date(2026, 7, 10),
            end_date=date(2026, 7, 20),
        )

        with self.assertRaises(ValidationError):
            assignment.full_clean()

    def test_rejects_same_worker_on_overlapping_trucks(self):
        WorkerTruckAssignment.objects.create(
            worker=self.worker_1,
            truck=self.truck_1,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 15),
        )

        assignment = WorkerTruckAssignment(
            worker=self.worker_1,
            truck=self.truck_2,
            start_date=date(2026, 7, 10),
            end_date=date(2026, 7, 20),
        )

        with self.assertRaises(ValidationError):
            assignment.full_clean()

    def test_rejects_end_date_before_start_date(self):
        assignment = WorkerTruckAssignment(
            worker=self.worker_1,
            truck=self.truck_1,
            start_date=date(2026, 7, 20),
            end_date=date(2026, 7, 10),
        )

        with self.assertRaises(ValidationError):
            assignment.full_clean()

    def test_open_ended_assignment_blocks_future_overlap(self):
        WorkerTruckAssignment.objects.create(
            worker=self.worker_1,
            truck=self.truck_1,
            start_date=date(2026, 7, 1),
            end_date=None,
        )

        assignment = WorkerTruckAssignment(
            worker=self.worker_2,
            truck=self.truck_1,
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
        )

        with self.assertRaises(ValidationError):
            assignment.full_clean()


from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError


class TruckModelTests(TestCase):
    def setUp(self):
        self.truck = Truck.objects.create(
            internal_code="TRUCK-MODEL-001",
            registration_number="REG-MODEL-001",
            brand="Test Brand",
            model="Test Model",
            manufacturing_year=2020,
            is_active=True,
        )

    def test_duplicate_registration_number_is_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Truck.objects.create(
                    internal_code="TRUCK-MODEL-002",
                    registration_number="REG-MODEL-001",
                    brand="Other Brand",
                    model="Other Model",
                    manufacturing_year=2021,
                )

    def test_duplicate_internal_code_is_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Truck.objects.create(
                    internal_code="TRUCK-MODEL-001",
                    registration_number="REG-MODEL-002",
                    brand="Other Brand",
                    model="Other Model",
                    manufacturing_year=2021,
                )

    def test_invalid_manufacturing_year_is_rejected(self):
        truck = Truck(
            internal_code="TRUCK-INVALID-YEAR",
            registration_number="REG-INVALID-YEAR",
            brand="Test",
            model="Invalid Year",
            manufacturing_year=2200,
        )

        with self.assertRaises(ValidationError):
            truck.full_clean()

    def test_truck_can_be_deactivated_without_deletion(self):
        self.truck.is_active = False
        self.truck.save()

        self.truck.refresh_from_db()

        self.assertFalse(self.truck.is_active)
        self.assertTrue(
            Truck.objects.filter(
                pk=self.truck.pk
            ).exists()
        )

    def test_assigned_truck_is_protected_from_deletion(self):
        worker = Worker.objects.create(
            employee_code="WORKER-FOR-TRUCK",
            first_name="Worker",
            last_name="Truck Test",
        )

        WorkerTruckAssignment.objects.create(
            worker=worker,
            truck=self.truck,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 15),
        )

        with self.assertRaises(ProtectedError):
            self.truck.delete()

        self.assertTrue(
            Truck.objects.filter(
                pk=self.truck.pk
            ).exists()
        )
