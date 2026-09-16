from django.test import SimpleTestCase

from apps.imports.services.source_truck_scope_snapshot import (
    build_source_truck_scope_snapshot,
)


class SourceTruckScopeSnapshotTests(SimpleTestCase):
    def test_snapshot_is_canonical_and_order_independent(self):
        first = build_source_truck_scope_snapshot(
            mappings={
                " van2 ": "DELISKY LIV02",
                "VAN1": "DELISKY LIV01",
            },
            exclusions={
                " admin ": "non distribution user",
            },
        )
        second = build_source_truck_scope_snapshot(
            mappings={
                "van1": "delisky liv01",
                "VAN2": "delisky   liv02",
            },
            exclusions={
                "ADMIN": "NON DISTRIBUTION USER",
            },
        )

        self.assertEqual(first, second)
        self.assertEqual(
            first.mappings,
            (
                ("VAN1", "DELISKY LIV01"),
                ("VAN2", "DELISKY LIV02"),
            ),
        )
        self.assertEqual(
            first.exclusions,
            (("ADMIN", "NON DISTRIBUTION USER"),),
        )
        self.assertEqual(len(first.sha256), 64)

    def test_snapshot_rejects_mapping_exclusion_conflict(self):
        with self.assertRaisesRegex(
            ValueError,
            "VAN1",
        ):
            build_source_truck_scope_snapshot(
                mappings={"VAN1": "DELISKY LIV01"},
                exclusions={" van1 ": "OUT_OF_SCOPE"},
            )

    def test_snapshot_hash_changes_when_scope_changes(self):
        baseline = build_source_truck_scope_snapshot(
            mappings={"VAN1": "DELISKY LIV01"},
            exclusions={},
        )
        changed = build_source_truck_scope_snapshot(
            mappings={
                "VAN1": "DELISKY LIV01",
                "VAN2": "DELISKY LIV02",
            },
            exclusions={},
        )

        self.assertNotEqual(
            baseline.sha256,
            changed.sha256,
        )
