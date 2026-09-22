import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class BackupDatabaseSafetyTests(SimpleTestCase):
    def _run_backup_helper(self, expected_database):
        env = os.environ.copy()
        env.update(
            {
                "DB_NAME": "delisky_bi_dev",
                "DB_USER": env.get("DB_USER", "delisky_test"),
                "DB_PASSWORD": env.get("DB_PASSWORD", "test-password"),
                "DB_HOST": env.get("DB_HOST", "127.0.0.1"),
                "DB_PORT": env.get("DB_PORT", "5432"),
                "DJANGO_SECRET_KEY": env.get(
                    "DJANGO_SECRET_KEY",
                    "test-secret-key-for-backup-safety",
                ),
                "DELISKY_BACKUP_DJANGO_SETTINGS": (
                    "config.settings.development"
                ),
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "backup.dump"

            return subprocess.run(
                [
                    sys.executable,
                    str(
                        settings.BASE_DIR
                        / "scripts"
                        / "backup_database.py"
                    ),
                    "--output",
                    str(output_path),
                    "--pg-dump",
                    str(Path(temp_dir) / "missing-pg-dump"),
                    "--expected-database",
                    expected_database,
                ],
                cwd=settings.BASE_DIR,
                env=env,
                capture_output=True,
                text=True,
            )

    def test_backup_helper_rejects_wrong_expected_database(self):
        result = self._run_backup_helper("delisky_bi")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "Unsafe backup database configuration",
            result.stderr,
        )
        self.assertIn(
            "expected 'delisky_bi', got 'delisky_bi_dev'",
            result.stderr,
        )

    def test_backup_helper_accepts_identity_before_tool_check(self):
        result = self._run_backup_helper("delisky_bi_dev")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "pg_dump not found",
            result.stderr,
        )
        self.assertNotIn(
            "Unsafe backup database configuration",
            result.stderr,
        )
