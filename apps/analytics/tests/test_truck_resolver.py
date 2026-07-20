from django.test import TestCase

from apps.analytics.services.truck_resolver import (
    TruckResolutionStatus,
    build_truck_code_index,
    resolve_truck_by_van,
)
from apps.fleet.models import Truck


class TruckResolverTests(TestCase):
    def create_truck(
        self,
        *,
        internal_code,
        registration_number,
        is_active=True,
    ):
        return Truck.objects.create(
            internal_code=internal_code,
            registration_number=registration_number,
            brand="TEST BRAND",
            model="TEST MODEL",
            is_active=is_active,
        )

    def test_matches_van_to_internal_code(self):
        truck = self.create_truck(
            internal_code="TEST-VAN-001",
            registration_number="TEST-REG-001",
        )

        result = resolve_truck_by_van("TEST-VAN-001")

        self.assertEqual(
            result.status,
            TruckResolutionStatus.MATCHED,
        )
        self.assertTrue(result.is_matched)
        self.assertEqual(result.truck, truck)
        self.assertEqual(
            result.matching_truck_ids,
            (truck.pk,),
        )

    def test_matching_uses_normalized_text(self):
        truck = self.create_truck(
            internal_code="TEST-VAN-002",
            registration_number="TEST-REG-002",
        )

        result = resolve_truck_by_van(
            "  test-van-002  "
        )

        self.assertEqual(
            result.status,
            TruckResolutionStatus.MATCHED,
        )
        self.assertEqual(result.truck, truck)
        self.assertEqual(
            result.normalized_van,
            "test-van-002",
        )

    def test_blank_van_returns_missing_van(self):
        result = resolve_truck_by_van("   ")

        self.assertEqual(
            result.status,
            TruckResolutionStatus.MISSING_VAN,
        )
        self.assertFalse(result.is_matched)
        self.assertIsNone(result.normalized_van)
        self.assertIsNone(result.truck)

    def test_unknown_van_returns_truck_not_found(self):
        result = resolve_truck_by_van(
            "TEST-UNKNOWN-VAN"
        )

        self.assertEqual(
            result.status,
            TruckResolutionStatus.TRUCK_NOT_FOUND,
        )
        self.assertFalse(result.is_matched)
        self.assertIsNone(result.truck)

    def test_registration_number_is_not_used_as_fallback(self):
        self.create_truck(
            internal_code="TEST-VAN-003",
            registration_number="TEST-REG-003",
        )

        result = resolve_truck_by_van(
            "TEST-REG-003"
        )

        self.assertEqual(
            result.status,
            TruckResolutionStatus.TRUCK_NOT_FOUND,
        )
        self.assertIsNone(result.truck)

    def test_inactive_truck_is_available_for_historical_analysis(self):
        truck = self.create_truck(
            internal_code="TEST-VAN-INACTIVE",
            registration_number="TEST-REG-INACTIVE",
            is_active=False,
        )

        result = resolve_truck_by_van(
            "test-van-inactive"
        )

        self.assertEqual(
            result.status,
            TruckResolutionStatus.MATCHED,
        )
        self.assertEqual(result.truck, truck)

    def test_truck_without_internal_code_is_ignored(self):
        self.create_truck(
            internal_code=None,
            registration_number="TEST-REG-NO-CODE",
        )

        index = build_truck_code_index()

        self.assertEqual(index, {})

    def test_duplicate_normalized_codes_are_ambiguous(self):
        first_truck = self.create_truck(
            internal_code="TEST-VAN-DUPLICATE",
            registration_number="TEST-REG-DUPLICATE-1",
        )
        second_truck = self.create_truck(
            internal_code=" test-van-duplicate ",
            registration_number="TEST-REG-DUPLICATE-2",
        )

        result = resolve_truck_by_van(
            "TEST-VAN-DUPLICATE"
        )

        self.assertEqual(
            result.status,
            TruckResolutionStatus.AMBIGUOUS_TRUCK_CODE,
        )
        self.assertFalse(result.is_matched)
        self.assertIsNone(result.truck)
        self.assertEqual(
            result.matching_truck_ids,
            tuple(
                sorted(
                    (
                        first_truck.pk,
                        second_truck.pk,
                    )
                )
            ),
        )
