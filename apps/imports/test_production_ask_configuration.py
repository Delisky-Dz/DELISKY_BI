"""Production configuration imports only; database connections are prohibited."""
import json
import os
import subprocess
import sys
from django.conf import settings
from django.test import SimpleTestCase


class ProductionAskConfigurationTests(SimpleTestCase):
    def run_settings(self, **values):
        env = {k: v for k, v in os.environ.items() if not k.startswith('ASK_DELISKY_')}
        env.update(DB_NAME='delisky_bi', DJANGO_SETTINGS_MODULE='config.settings.production',
                   DJANGO_SECRET_KEY='configuration-test-only', ASK_DELISKY_PROVIDER='local',
                   ASK_DELISKY_LOCAL_MODEL='qwen3:4b-instruct', ASK_DELISKY_TIMEOUT_SECONDS='120')
        env.update(values)
        code = '''
import json
from unittest.mock import patch
with patch('dotenv.load_dotenv'), patch('django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection', side_effect=AssertionError('Database access forbidden')):
    import django
    django.setup()
    from django.conf import settings
    from apps.assistant.provider_factory import build_ask_delisky_provider
    from apps.assistant.marketing_provider_factory import build_marketing_helper_provider
    print(json.dumps(dict(streaming=settings.ASK_DELISKY_STREAMING_ENABLED,
        cache=settings.ASK_DELISKY_CONTEXT_CACHE_ENABLED,
        ask_timeout=build_ask_delisky_provider()._config.timeout_seconds,
        marketing_timeout=build_marketing_helper_provider()._config.timeout_seconds)))
'''
        return subprocess.run([sys.executable, '-c', code], cwd=settings.BASE_DIR,
                              env=env, capture_output=True, text=True, timeout=30)

    def test_defaults_remain_disabled(self):
        result = self.run_settings()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), dict(streaming=False, cache=False, ask_timeout=120, marketing_timeout=120))

    def test_explicit_true_enables_flags_and_ask_timeout_is_isolated(self):
        result = self.run_settings(ASK_DELISKY_STREAMING_ENABLED='true',
            ASK_DELISKY_CONTEXT_CACHE_ENABLED=' TRUE ', ASK_DELISKY_REQUEST_TIMEOUT_SECONDS='180')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), dict(streaming=True, cache=True, ask_timeout=180, marketing_timeout=120))

    def test_explicit_false_disables_flags(self):
        result = self.run_settings(ASK_DELISKY_STREAMING_ENABLED='FALSE', ASK_DELISKY_CONTEXT_CACHE_ENABLED='false')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)['streaming'])
        self.assertFalse(json.loads(result.stdout)['cache'])

    def test_invalid_booleans_fail_configuration(self):
        for name in ['ASK_DELISKY_STREAMING_ENABLED', 'ASK_DELISKY_CONTEXT_CACHE_ENABLED']:
            for value in ['', '1', '0', 'yes', 'tru']:
                with self.subTest(name=name, value=value):
                    result = self.run_settings(**{name:value})
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(name + " must be 'true' or 'false'", result.stderr)
                    self.assertIn('ImproperlyConfigured', result.stderr)

    def test_waitress_has_fixed_bounded_capacity_and_existing_guards(self):
        launcher = (settings.BASE_DIR/'scripts/start_production_waitress.ps1').read_text(encoding='utf-8')
        command = launcher.split('& $Waitress `', 1)[1]
        self.assertIn('"--threads=4"', command)
        self.assertEqual(command.count('--threads'), 1)
        for guard in ['PRODUCTION_BRANCH_GUARD_FAILED', 'PRODUCTION_WORKING_TREE_NOT_CLEAN',
                      'PRODUCTION_HEAD_GUARD_FAILED', 'PRODUCTION_STATIC_MANIFEST_GUARD_FAILED',
                      'PRODUCTION_DJANGO_CHECK_FAILED']:
            self.assertIn(guard, launcher)
