from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.fleet.models import Truck
from apps.imports.models import (
    DistributionBrand,
    ImportSourceSystem,
    SourceTruckMapping,
)


class SourceTruckMappingModelTests(TestCase):
    def setUp(self):
        self.delisky = DistributionBrand.objects.create(
            code="DELISKY",
            name="DELISKY",
            is_active=True,
        )

        self.truck = Truck.objects.create(
            internal_code="DELISKY LIV01",
            distribution_brand=self.delisky,
            registration_number="SOURCE-MAP-REG-01",
            brand="TEST BRAND",
            model="TEST MODEL",
        )

    def test_creates_source_system_and_truck_mapping(self):
        source_system = ImportSourceSystem.objects.create(
            code="AIO_WEB",
            name="AIO-WEB",
            is_active=True,
        )

        mapping = SourceTruckMapping(
            source_system=source_system,
            source_code="  camion   01 ",
            truck=self.truck,
            is_active=True,
        )

        mapping.full_clean()
        mapping.save()

        mapping.refresh_from_db()

        self.assertEqual(
            source_system.code,
            "AIO_WEB",
        )
        self.assertEqual(
            mapping.source_code,
            "CAMION 01",
        )
        self.assertEqual(
            mapping.truck,
            self.truck,
        )

    def test_rejects_duplicate_normalized_code_in_same_source_system(self):
        source_system = ImportSourceSystem.objects.create(
            code="AIO_WEB",
            name="AIO-WEB",
            is_active=True,
        )

        SourceTruckMapping.objects.create(
            source_system=source_system,
            source_code="CAMION 01",
            truck=self.truck,
            is_active=True,
        )

        duplicate = SourceTruckMapping(
            source_system=source_system,
            source_code="  camion   01 ",
            truck=self.truck,
            is_active=True,
        )

        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_same_source_code_is_allowed_in_different_source_systems(self):
        aio = ImportSourceSystem.objects.create(
            code="AIO_WEB",
            name="AIO-WEB",
            is_active=True,
        )
        bifa = ImportSourceSystem.objects.create(
            code="BIFA_MILA",
            name="BIFA MILA",
            is_active=True,
        )

        first = SourceTruckMapping(
            source_system=aio,
            source_code="LIV01",
            truck=self.truck,
            is_active=True,
        )
        first.full_clean()
        first.save()

        second = SourceTruckMapping(
            source_system=bifa,
            source_code="LIV01",
            truck=self.truck,
            is_active=True,
        )
        second.full_clean()
        second.save()

        self.assertEqual(
            SourceTruckMapping.objects.count(),
            2,
        )
