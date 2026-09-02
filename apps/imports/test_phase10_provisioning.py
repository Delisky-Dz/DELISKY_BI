from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.fleet.models import Truck, TruckCrewAssignment
from apps.imports.management.commands.provision_phase10_reference_data import (
    PRODUCT_ALIASES,
    SOURCE_SYSTEM_CODE,
    TRUCK_EXCLUSIONS,
    WORKERS,
)
from apps.imports.models import (
    ImportSourceSystem,
    SourceProductAlias,
    SourceProductPackaging,
    SourceTruckExclusion,
)
from apps.workforce.models import Worker


class Phase10ReferenceDataProvisioningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.source = ImportSourceSystem.objects.create(
            code=SOURCE_SYSTEM_CODE,
            name="AIO Web",
            is_active=True,
        )

        for sequence, spec in enumerate(
            PRODUCT_ALIASES,
            start=1,
        ):
            (
                alias_name,
                target_name,
                barcode,
                units_per_carton,
                notes,
            ) = spec

            SourceProductPackaging.objects.create(
                source_system=cls.source,
                source_product_code=(
                    f"PHASE10-PRODUCT-{sequence}"
                ),
                barcode=barcode,
                reference=(
                    f"PHASE10-REF-{sequence}"
                ),
                designation=target_name,
                normalized_designation=target_name.upper(),
                units_per_carton=units_per_carton,
                needs_review=False,
                is_active=True,
            )

        for sequence, spec in enumerate(
            WORKERS,
            start=1,
        ):
            (
                employee_code,
                first_name,
                truck_code,
                end_date,
            ) = spec

            Truck.objects.create(
                internal_code=truck_code,
                registration_number=(
                    f"PHASE10-REG-{sequence:02d}"
                ),
                brand="PHASE10 TEST",
                model="TEST",
                is_active=True,
            )

    def test_apply_creates_reference_data_and_is_idempotent(
        self,
    ):
        first_output = StringIO()

        call_command(
            "provision_phase10_reference_data",
            "--apply",
            stdout=first_output,
        )

        self.assertIn(
            "PHASE 10 REFERENCE DATA: APPLIED",
            first_output.getvalue(),
        )

        self.assertEqual(
            SourceProductAlias.objects.filter(
                source_system=self.source,
            ).count(),
            5,
        )

        self.assertEqual(
            SourceTruckExclusion.objects.filter(
                source_system=self.source,
            ).count(),
            2,
        )

        self.assertEqual(
            Worker.objects.filter(
                employee_code__startswith="GEN-",
            ).count(),
            13,
        )

        self.assertEqual(
            TruckCrewAssignment.objects.filter(
                worker__employee_code__startswith="GEN-",
            ).count(),
            13,
        )

        delisky_assignment = (
            TruckCrewAssignment.objects.get(
                worker__employee_code=(
                    "GEN-DELISKY-LIV01"
                )
            )
        )

        self.assertEqual(
            str(delisky_assignment.start_date),
            "2026-04-04",
        )

        self.assertEqual(
            str(delisky_assignment.end_date),
            "2026-08-17",
        )

        first_counts = (
            SourceProductAlias.objects.count(),
            SourceTruckExclusion.objects.count(),
            Worker.objects.count(),
            TruckCrewAssignment.objects.count(),
        )

        second_output = StringIO()

        call_command(
            "provision_phase10_reference_data",
            "--apply",
            stdout=second_output,
        )

        self.assertIn(
            "PHASE 10 REFERENCE DATA: APPLIED",
            second_output.getvalue(),
        )

        second_counts = (
            SourceProductAlias.objects.count(),
            SourceTruckExclusion.objects.count(),
            Worker.objects.count(),
            TruckCrewAssignment.objects.count(),
        )

        self.assertEqual(
            second_counts,
            first_counts,
        )

        self.assertEqual(
            second_counts,
            (
                5,
                2,
                13,
                13,
            ),
        )

        dry_run_output = StringIO()

        call_command(
            "provision_phase10_reference_data",
            stdout=dry_run_output,
        )

        self.assertIn(
            "DRY RUN: PASS",
            dry_run_output.getvalue(),
        )

        self.assertNotIn(
            "[CREATE]",
            dry_run_output.getvalue(),
        )

        self.assertNotIn(
            "[UPDATE]",
            dry_run_output.getvalue(),
        )
