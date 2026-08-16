from django.test import SimpleTestCase

from apps.imports.services.source_truck_mapper import (
    SourceTruckMappingError,
    map_source_truck_code,
)


class SourceTruckMapperTests(SimpleTestCase):
    def test_maps_known_source_code_to_official_internal_code(self):
        mapping = {
            "VAN-EXTERNAL-01": "DELISKY LIV01",
        }

        result = map_source_truck_code(
            "VAN-EXTERNAL-01",
            mapping=mapping,
        )

        self.assertEqual(
            result,
            "DELISKY LIV01",
        )

    def test_matching_is_whitespace_and_case_insensitive(self):
        mapping = {
            "Van External 01": "NITA LIV01",
        }

        result = map_source_truck_code(
            "  van   external 01  ",
            mapping=mapping,
        )

        self.assertEqual(
            result,
            "NITA LIV01",
        )

    def test_rejects_unknown_source_code(self):
        with self.assertRaises(SourceTruckMappingError) as context:
            map_source_truck_code(
                "UNKNOWN VAN",
                mapping={
                    "KNOWN VAN": "BIFA PSLIV01",
                },
            )

        self.assertEqual(
            context.exception.code,
            "source_truck_not_mapped",
        )

    def test_rejects_blank_source_code(self):
        with self.assertRaises(SourceTruckMappingError) as context:
            map_source_truck_code(
                "   ",
                mapping={
                    "KNOWN VAN": "BIFA PSLIV01",
                },
            )

        self.assertEqual(
            context.exception.code,
            "missing_source_truck_code",
        )

    def test_allows_duplicate_normalized_aliases_for_same_target(self):
        result = map_source_truck_code(
            " van   01 ",
            mapping={
                "VAN 01": "DELISKY LIV01",
                "van   01": "  delisky   liv01  ",
            },
        )

        self.assertEqual(
            result,
            "DELISKY LIV01",
        )


    def test_rejects_conflicting_normalized_source_mappings(self):
        with self.assertRaises(SourceTruckMappingError) as context:
            map_source_truck_code(
                " van   01 ",
                mapping={
                    "VAN 01": "DELISKY LIV01",
                    "van   01": "NITA LIV01",
                },
            )

        self.assertEqual(
            context.exception.code,
            "ambiguous_source_truck_mapping",
        )


    def test_rejects_blank_target_internal_code(self):
        with self.assertRaises(SourceTruckMappingError) as context:
            map_source_truck_code(
                "KNOWN VAN",
                mapping={
                    "KNOWN VAN": "   ",
                },
            )

        self.assertEqual(
            context.exception.code,
            "invalid_target_truck_code",
        )
