from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.imports.models import DistributionBrand
from apps.workforce.models import Worker

from .models import Truck, TruckCrewAssignment


class TruckCrewAssignmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.brand = DistributionBrand.objects.create(
            code="BIFA",
            name="BIFA",
        )

        cls.first_truck = Truck.objects.create(
            distribution_brand=cls.brand,
            route_type=Truck.RouteType.PSLIV,
            route_number=1,
            registration_number="BIFA-PSLIV-01",
            brand="BIFA",
            model="Distribution",
        )

        cls.second_truck = Truck.objects.create(
            distribution_brand=cls.brand,
            route_type=Truck.RouteType.PSLIV,
            route_number=2,
            registration_number="BIFA-PSLIV-02",
            brand="BIFA",
            model="Distribution",
        )

        cls.workers = [
            Worker.objects.create(
                employee_code=f"CREW-{number:02d}",
                first_name=f"عامل {number}",
                last_name="اختبار",
                is_active=True,
            )
            for number in range(1, 6)
        ]

    def create_assignment(
        self,
        *,
        worker,
        truck=None,
        crew_role=(
            TruckCrewAssignment.CrewRole.DRIVER
        ),
        is_primary_seller=False,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
    ):
        assignment = TruckCrewAssignment(
            worker=worker,
            truck=truck or self.first_truck,
            crew_role=crew_role,
            is_primary_seller=is_primary_seller,
            start_date=start_date,
            end_date=end_date,
        )

        assignment.full_clean()
        assignment.save()

        return assignment

    def test_three_workers_can_share_same_truck_period(
        self,
    ):
        self.create_assignment(
            worker=self.workers[0],
            crew_role=(
                TruckCrewAssignment.CrewRole.SELLER
            ),
            is_primary_seller=True,
        )
        self.create_assignment(
            worker=self.workers[1],
            crew_role=(
                TruckCrewAssignment.CrewRole.DRIVER
            ),
        )
        self.create_assignment(
            worker=self.workers[2],
            crew_role=(
                TruckCrewAssignment
                .CrewRole
                .DISTRIBUTION_ASSISTANT
            ),
        )

        self.assertEqual(
            TruckCrewAssignment.objects.count(),
            3,
        )

    def test_fourth_overlapping_worker_is_rejected(
        self,
    ):
        for index, role in enumerate(
            (
                TruckCrewAssignment.CrewRole.SELLER,
                TruckCrewAssignment.CrewRole.DRIVER,
                (
                    TruckCrewAssignment
                    .CrewRole
                    .DISTRIBUTION_ASSISTANT
                ),
            )
        ):
            self.create_assignment(
                worker=self.workers[index],
                crew_role=role,
                is_primary_seller=(index == 0),
            )

        fourth = TruckCrewAssignment(
            worker=self.workers[3],
            truck=self.first_truck,
            crew_role=(
                TruckCrewAssignment.CrewRole.TRAINEE
            ),
            start_date=date(2026, 7, 10),
            end_date=date(2026, 7, 20),
        )

        with self.assertRaisesMessage(
            ValidationError,
            "لا يمكن أن يتجاوز طاقم الشاحنة 3 عمال",
        ):
            fourth.full_clean()

    def test_worker_cannot_join_two_trucks_in_same_period(
        self,
    ):
        self.create_assignment(
            worker=self.workers[0],
        )

        conflicting = TruckCrewAssignment(
            worker=self.workers[0],
            truck=self.second_truck,
            crew_role=(
                TruckCrewAssignment.CrewRole.DRIVER
            ),
            start_date=date(2026, 7, 15),
            end_date=date(2026, 8, 15),
        )

        with self.assertRaisesMessage(
            ValidationError,
            "هذا العامل موجود ضمن طاقم آخر",
        ):
            conflicting.full_clean()

    def test_second_primary_seller_is_rejected(
        self,
    ):
        self.create_assignment(
            worker=self.workers[0],
            crew_role=(
                TruckCrewAssignment.CrewRole.SELLER
            ),
            is_primary_seller=True,
        )

        conflicting = TruckCrewAssignment(
            worker=self.workers[1],
            truck=self.first_truck,
            crew_role=(
                TruckCrewAssignment.CrewRole.DRIVER
            ),
            is_primary_seller=True,
            start_date=date(2026, 7, 10),
            end_date=date(2026, 7, 20),
        )

        with self.assertRaisesMessage(
            ValidationError,
            "يوجد بائع رئيسي آخر",
        ):
            conflicting.full_clean()

    def test_assistant_cannot_be_primary_seller(
        self,
    ):
        assignment = TruckCrewAssignment(
            worker=self.workers[0],
            truck=self.first_truck,
            crew_role=(
                TruckCrewAssignment
                .CrewRole
                .DISTRIBUTION_ASSISTANT
            ),
            is_primary_seller=True,
            start_date=date(2026, 7, 1),
        )

        with self.assertRaisesMessage(
            ValidationError,
            "المساعد والمتربص لا يمكن",
        ):
            assignment.full_clean()

    def test_end_date_before_start_date_is_rejected(
        self,
    ):
        assignment = TruckCrewAssignment(
            worker=self.workers[0],
            truck=self.first_truck,
            crew_role=(
                TruckCrewAssignment.CrewRole.DRIVER
            ),
            start_date=date(2026, 7, 20),
            end_date=date(2026, 7, 19),
        )

        with self.assertRaisesMessage(
            ValidationError,
            "تاريخ النهاية لا يمكن أن يكون قبل",
        ):
            assignment.full_clean()
