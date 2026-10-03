import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase


def load_restore_verifier():
    module_path = (
        Path(settings.BASE_DIR)
        / "scripts"
        / "verify_backup_restore.py"
    )
    spec = importlib.util.spec_from_file_location(
        "delisky_verify_backup_restore",
        module_path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "Unable to load backup restore verifier module."
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BackupRestoreVerifierTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.verifier = load_restore_verifier()

    def test_safe_restore_database_name_is_scoped(self):
        name = self.verifier.safe_restore_database_name(
            "delisky_bi"
        )

        self.assertNotEqual(name, "delisky_bi")
        self.assertTrue(
            name.startswith(
                "delisky_bi_restore_verify_"
            )
        )
        self.assertLessEqual(len(name), 63)

    def test_safe_restore_database_name_rejects_long_name(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "too long",
        ):
            self.verifier.safe_restore_database_name(
                "x" * 60
            )

    def test_archive_database_name_reads_pg_restore_header(self):
        completed = SimpleNamespace(
            stdout=(
                ";\n"
                "; Archive created at 2026-09-21 21:28:56\n"
                ";     dbname: delisky_bi\n"
            )
        )

        with patch.object(
            self.verifier.subprocess,
            "run",
            return_value=completed,
        ):
            database_name = (
                self.verifier.archive_database_name(
                    "pg_restore",
                    "backup.dump",
                )
            )

        self.assertEqual(
            database_name,
            "delisky_bi",
        )

    def test_validate_restored_metadata_accepts_expected_baseline(self):
        self.verifier.validate_restored_metadata(
            public_tables=31,
            migration_count=48,
            extensions=["btree_gist", "plpgsql"],
            minimum_public_tables=31,
            minimum_django_migrations=48,
            required_extensions=["btree_gist", "plpgsql"],
        )

    def test_validate_restored_metadata_rejects_missing_extension(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "missing required extension",
        ):
            self.verifier.validate_restored_metadata(
                public_tables=31,
                migration_count=48,
                extensions=["plpgsql"],
                minimum_public_tables=31,
                minimum_django_migrations=48,
                required_extensions=[
                    "btree_gist",
                    "plpgsql",
                ],
            )

    def test_archive_database_name_requires_header_database(self):
        completed = SimpleNamespace(
            stdout="; archive without database metadata\n"
        )

        with patch.object(
            self.verifier.subprocess,
            "run",
            return_value=completed,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "source database name",
            ):
                self.verifier.archive_database_name(
                    "pg_restore",
                    "backup.dump",
                )
