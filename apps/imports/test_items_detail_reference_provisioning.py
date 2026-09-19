from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.fleet.models import Truck, TruckCrewAssignment
from apps.imports.management.commands.provision_items_detail_reference_data import (
    GENERIC_WORKERS,
    HISTORICAL_TRUCKS,
    SOURCE_EXCLUSIONS,
    SOURCE_MAPPINGS,
    START_DATE,
)
from apps.imports.models import (
    DistributionBrand,
    ImportSourceSystem,
    SourceTruckExclusion,
    SourceTruckMapping,
)
from apps.workforce.models import Worker


class ItemsDetailReferenceProvisioningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.brands = {
            code: DistributionBrand.objects.create(
                code=code,
                name=code,
            )
            for code in ("BIFA", "DELISKY", "NITA")
        }
        cls.sources = {
            code: ImportSourceSystem.objects.create(
                code=code,
                name=code,
                is_active=True,
            )
            for code in SOURCE_MAPPINGS
        }

        historical_codes = {
            spec[0]
            for spec in HISTORICAL_TRUCKS
        }
        target_codes = {
            truck_code
            for specs in SOURCE_MAPPINGS.values()
            for _, truck_code in specs
        }

        for sequence, code in enumerate(
            sorted(target_codes - historical_codes),
            start=1,
        ):
            brand_code, route = code.split()
            if route.startswith("PSLIV"):
                route_type = Truck.RouteType.PSLIV
                route_number = int(route.removeprefix("PSLIV"))
            elif route.startswith("PLIV"):
                route_type = Truck.RouteType.PLIV
                route_number = int(route.removeprefix("PLIV"))
            else:
                route_type = Truck.RouteType.LIV
                route_number = int(route.removeprefix("LIV"))

            Truck.objects.create(
                distribution_brand=cls.brands[brand_code],
                route_type=route_type,
                route_number=route_number,
                registration_number=f"DETAIL-REF-{sequence:02d}",
                brand=brand_code,
                model="TEST",
                is_active=True,
            )

    def test_dry_run_makes_no_changes(self):
        output = StringIO()

        call_command(
            "provision_items_detail_reference_data",
            stdout=output,
        )

        self.assertIn("DRY RUN: PASS", output.getvalue())
        self.assertEqual(
            Worker.objects.filter(
                employee_code__in=[
                    spec[0]
                    for spec in GENERIC_WORKERS
                ]
            ).count(),
            0,
        )
        self.assertEqual(
            SourceTruckMapping.objects.count(),
            0,
        )
        self.assertEqual(
            SourceTruckExclusion.objects.count(),
            0,
        )

    def test_apply_is_idempotent_and_provisions_confirmed_scope(self):
        first_output = StringIO()

        call_command(
            "provision_items_detail_reference_data",
            "--apply",
            stdout=first_output,
        )

        self.assertIn(
            "ITEMS DETAIL REFERENCE DATA: APPLIED",
            first_output.getvalue(),
        )

        for code, route_type, route_number, notes in HISTORICAL_TRUCKS:
            truck = Truck.objects.get(internal_code=code)
            self.assertEqual(
                truck.distribution_brand.code,
                "BIFA",
            )
            self.assertEqual(truck.route_type, route_type)
            self.assertEqual(truck.route_number, route_number)
            self.assertFalse(truck.is_active)

        self.assertEqual(
            Worker.objects.filter(
                employee_code__in=[
                    spec[0]
                    for spec in GENERIC_WORKERS
                ]
            ).count(),
            4,
        )
        self.assertEqual(
            TruckCrewAssignment.objects.filter(
                worker__employee_code__in=[
                    spec[0]
                    for spec in GENERIC_WORKERS
                ],
                is_primary_seller=True,
                start_date=START_DATE,
            ).count(),
            4,
        )

        self.assertEqual(
            SourceTruckMapping.objects.filter(
                source_system=self.sources["AIO_WEB"],
            ).count(),
            len(SOURCE_MAPPINGS["AIO_WEB"]),
        )
        self.assertEqual(
            SourceTruckMapping.objects.filter(
                source_system=self.sources["BIFA_MILA"],
            ).count(),
            len(SOURCE_MAPPINGS["BIFA_MILA"]),
        )
        self.assertEqual(
            SourceTruckExclusion.objects.filter(
                source_system=self.sources["AIO_WEB"],
            ).count(),
            len(SOURCE_EXCLUSIONS["AIO_WEB"]),
        )
        self.assertEqual(
            SourceTruckExclusion.objects.filter(
                source_system=self.sources["BIFA_MILA"],
            ).count(),
            len(SOURCE_EXCLUSIONS["BIFA_MILA"]),
        )

        first_counts = (
            Truck.objects.count(),
            Worker.objects.count(),
            TruckCrewAssignment.objects.count(),
            SourceTruckMapping.objects.count(),
            SourceTruckExclusion.objects.count(),
        )

        second_output = StringIO()
        call_command(
            "provision_items_detail_reference_data",
            "--apply",
            stdout=second_output,
        )

        self.assertIn(
            "ITEMS DETAIL REFERENCE DATA: APPLIED",
            second_output.getvalue(),
        )
        self.assertEqual(
            (
                Truck.objects.count(),
                Worker.objects.count(),
                TruckCrewAssignment.objects.count(),
                SourceTruckMapping.objects.count(),
                SourceTruckExclusion.objects.count(),
            ),
            first_counts,
        )

    def test_conflicting_mapping_is_rejected(self):
        source = self.sources["BIFA_MILA"]
        wrong_truck = Truck.objects.get(
            internal_code="BIFA LIV03"
        )
        SourceTruckMapping.objects.create(
            source_system=source,
            source_code="CV-04",
            truck=wrong_truck,
            is_active=True,
        )

        with self.assertRaisesRegex(
            CommandError,
            "Mapping conflict",
        ):
            call_command(
                "provision_items_detail_reference_data",
                stdout=StringIO(),
            )
