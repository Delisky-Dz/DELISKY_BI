from django.test import TestCase

from apps.fleet.models import Truck
from apps.imports.models import (
    DistributionBrand,
    ImportSourceSystem,
    SourceTruckMapping,
)
from apps.imports.services.source_truck_mapping_store import (
    SourceTruckMappingStoreError,
    build_source_truck_mapping,
)


class SourceTruckMappingStoreTests(TestCase):
    def setUp(self):
        self.delisky = DistributionBrand.objects.create(
            code="DELISKY",
            name="DELISKY",
            is_active=True,
        )

        self.truck = Truck.objects.create(
            internal_code="DELISKY LIV01",
            distribution_brand=self.delisky,
            registration_number="STORE-REG-01",
            brand="TEST BRAND",
            model="TEST MODEL",
        )

        self.source_system = ImportSourceSystem.objects.create(
            code="AIO_WEB",
            name="AIO-WEB",
            is_active=True,
        )

    def test_builds_mapping_from_active_database_rows(self):
        SourceTruckMapping.objects.create(
            source_system=self.source_system,
            source_code="CAMION 01",
            truck=self.truck,
            is_active=True,
        )

        mapping = build_source_truck_mapping(
            "AIO_WEB"
        )

        self.assertEqual(
            mapping,
            {
                "CAMION 01": "DELISKY LIV01",
            },
        )

    def test_ignores_inactive_mapping_rows(self):
        SourceTruckMapping.objects.create(
            source_system=self.source_system,
            source_code="CAMION 01",
            truck=self.truck,
            is_active=False,
        )

        mapping = build_source_truck_mapping(
            "AIO_WEB"
        )

        self.assertEqual(
            mapping,
            {},
        )

    def test_rejects_unknown_source_system(self):
        with self.assertRaises(
            SourceTruckMappingStoreError
        ) as context:
            build_source_truck_mapping(
                "UNKNOWN_SYSTEM"
            )

        self.assertEqual(
            context.exception.code,
            "source_system_not_found",
        )

    def test_rejects_inactive_source_system(self):
        self.source_system.is_active = False
        self.source_system.save(
            update_fields=[
                "is_active",
                "updated_at",
            ]
        )

        with self.assertRaises(
            SourceTruckMappingStoreError
        ) as context:
            build_source_truck_mapping(
                "AIO_WEB"
            )

        self.assertEqual(
            context.exception.code,
            "source_system_inactive",
        )

    def test_rejects_mapping_to_truck_without_internal_code(self):
        legacy_truck = Truck.objects.create(
            internal_code=None,
            distribution_brand=self.delisky,
            registration_number="STORE-LEGACY-01",
            brand="TEST BRAND",
            model="TEST MODEL",
        )

        SourceTruckMapping.objects.create(
            source_system=self.source_system,
            source_code="LEGACY TRUCK",
            truck=legacy_truck,
            is_active=True,
        )

        with self.assertRaises(
            SourceTruckMappingStoreError
        ) as context:
            build_source_truck_mapping(
                "AIO_WEB"
            )

        self.assertEqual(
            context.exception.code,
            "truck_internal_code_missing",
        )
        self.assertEqual(
            context.exception.details["truck_id"],
            legacy_truck.pk,
        )
