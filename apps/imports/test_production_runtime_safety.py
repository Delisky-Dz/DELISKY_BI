import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


class ProductionRuntimeSettingsSafetyTests(SimpleTestCase):
    def _run_import(
        self,
        module_name,
        settings_module,
        database_name,
    ):
        env = os.environ.copy()
        env.update(
            {
                "DJANGO_SETTINGS_MODULE": settings_module,
                "DB_NAME": database_name,
                "DB_USER": env.get("DB_USER", "delisky_test"),
                "DB_PASSWORD": env.get("DB_PASSWORD", "test-password"),
                "DB_HOST": env.get("DB_HOST", "127.0.0.1"),
                "DB_PORT": env.get("DB_PORT", "5432"),
                "DJANGO_SECRET_KEY": env.get(
                    "DJANGO_SECRET_KEY",
                    "test-secret-key-for-runtime-safety",
                ),
                "DJANGO_ALLOWED_HOSTS": "app.delisky-dz.com",
                "DJANGO_CSRF_TRUSTED_ORIGINS": (
                    "https://app.delisky-dz.com"
                ),
            }
        )

        return subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    f"import {module_name}; "
                    "import os; "
                    "print(os.environ['DJANGO_SETTINGS_MODULE'])"
                ),
            ],
            cwd=settings.BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
        )

    def test_wsgi_rejects_inherited_development_settings(self):
        result = self._run_import(
            "config.wsgi",
            "config.settings.development",
            "delisky_bi_dev",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "Unsafe WSGI settings configuration",
            result.stderr,
        )

    def test_asgi_rejects_inherited_development_settings(self):
        result = self._run_import(
            "config.asgi",
            "config.settings.development",
            "delisky_bi_dev",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "Unsafe ASGI settings configuration",
            result.stderr,
        )

    def test_wsgi_accepts_explicit_production_settings(self):
        result = self._run_import(
            "config.wsgi",
            "config.settings.production",
            "delisky_bi",
        )

        self.assertEqual(
            result.returncode,
            0,
            msg=result.stderr,
        )
        self.assertEqual(
            result.stdout.strip(),
            "config.settings.production",
        )

    def test_asgi_accepts_explicit_production_settings(self):
        result = self._run_import(
            "config.asgi",
            "config.settings.production",
            "delisky_bi",
        )

        self.assertEqual(
            result.returncode,
            0,
            msg=result.stderr,
        )
        self.assertEqual(
            result.stdout.strip(),
            "config.settings.production",
        )
