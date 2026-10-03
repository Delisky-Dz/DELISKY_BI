import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


class ProductionDatabaseSafetyTests(SimpleTestCase):
    def _run_production_settings(self, database_name):
        env = os.environ.copy()
        env.update(
            {
                "DB_NAME": database_name,
                "DB_USER": env.get("DB_USER", "delisky_test"),
                "DB_PASSWORD": env.get("DB_PASSWORD", "test-password"),
                "DB_HOST": env.get("DB_HOST", "127.0.0.1"),
                "DB_PORT": env.get("DB_PORT", "5432"),
                "DJANGO_SECRET_KEY": env.get(
                    "DJANGO_SECRET_KEY",
                    "test-secret-key-for-settings-safety",
                ),
                "DJANGO_SETTINGS_MODULE": "config.settings.production",
            }
        )

        return subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import django; "
                    "django.setup(); "
                    "from django.conf import settings; "
                    "print(settings.DATABASES['default']['NAME'])"
                ),
            ],
            cwd=settings.BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
        )

    def test_production_rejects_non_production_database(self):
        result = self._run_production_settings("delisky_bi_dev")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "Unsafe production database configuration",
            result.stderr,
        )
        self.assertIn(
            "expected 'delisky_bi', got 'delisky_bi_dev'",
            result.stderr,
        )

    def test_production_accepts_production_database(self):
        result = self._run_production_settings("delisky_bi")

        self.assertEqual(
            result.returncode,
            0,
            msg=result.stderr,
        )
        self.assertEqual(result.stdout.strip(), "delisky_bi")
