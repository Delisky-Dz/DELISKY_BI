from datetime import date

from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from apps.fleet.models import Truck, WorkerTruckAssignment

from .models import Worker


class WorkerModelTests(TestCase):
    def setUp(self):
        self.worker = Worker.objects.create(
            employee_code="WORKER-001",
            first_name="Ahmed",
            last_name="Test",
            phone="0550000000",
            is_active=True,
        )

    def test_worker_full_name(self):
        self.assertEqual(
            self.worker.full_name,
            "Test Ahmed",
        )

    def test_duplicate_employee_code_is_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Worker.objects.create(
                    employee_code="WORKER-001",
                    first_name="Mohamed",
                    last_name="Duplicate",
                )

    def test_worker_can_be_deactivated_without_deletion(self):
        self.worker.is_active = False
        self.worker.save()

        self.worker.refresh_from_db()

        self.assertFalse(self.worker.is_active)
        self.assertTrue(
            Worker.objects.filter(
                pk=self.worker.pk
            ).exists()
        )

    def test_assigned_worker_is_protected_from_deletion(self):
        truck = Truck.objects.create(
            internal_code="TRUCK-001",
            registration_number="TEST-TRUCK-001",
            brand="Test",
            model="Truck",
            manufacturing_year=2020,
        )

        WorkerTruckAssignment.objects.create(
            worker=self.worker,
            truck=truck,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 15),
        )

        with self.assertRaises(ProtectedError):
            self.worker.delete()

        self.assertTrue(
            Worker.objects.filter(
                pk=self.worker.pk
            ).exists()
        )
