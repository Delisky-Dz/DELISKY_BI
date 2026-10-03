import os
from importlib import import_module
from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, migrations
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from apps.assistant import context_cache
from apps.assistant.contracts import AskDeliskyProviderRequest
from apps.assistant.marketing_helper import MarketingHelperRequest
from apps.assistant.marketing_provider_factory import build_marketing_helper_provider
from apps.assistant.models import AskDeliskyDataRevision
from apps.assistant.provider_factory import (
    AskDeliskyProviderConfigurationError, build_ask_delisky_provider,
)
from apps.assistant.revision_tracking import tracking_installed
from apps.assistant.tests.test_context_cache import context, get
from apps.assistant.tests.test_provider_factory import FakeLocalTransport
from apps.imports.models import DistributionBrand


class AskTimeoutConfigurationTests(SimpleTestCase):
    def environment(self):
        return {
            "ASK_DELISKY_PROVIDER": "local",
            "ASK_DELISKY_LOCAL_MODEL": "qwen3:4b-instruct",
            "ASK_DELISKY_LOCAL_BASE_URL": "http://127.0.0.1:11434",
            "ASK_DELISKY_TIMEOUT_SECONDS": "120",
        }

    def ask_timeout(self, **kwargs):
        transport = FakeLocalTransport()
        provider = build_ask_delisky_provider(local_transport=transport, **kwargs)
        provider.generate(AskDeliskyProviderRequest(
            question="Analyze", context_json="{}", context_schema_version="2",
        ))
        return transport.kwargs["timeout_seconds"]

    @override_settings(ASK_DELISKY_REQUEST_TIMEOUT_SECONDS=180)
    def test_dev_default_is_ask_only_and_does_not_mutate_environment(self):
        with patch.dict(os.environ, self.environment(), clear=True):
            before = dict(os.environ)
            self.assertEqual(self.ask_timeout(), 180)
            transport = FakeLocalTransport()
            marketing = build_marketing_helper_provider(local_transport=transport)
            marketing.generate(MarketingHelperRequest(question="Give advice"))
            self.assertEqual(transport.kwargs["timeout_seconds"], 120)
            self.assertEqual(dict(os.environ), before)

    @override_settings(ASK_DELISKY_REQUEST_TIMEOUT_SECONDS=180)
    def test_explicit_ask_environment_precedes_settings(self):
        env = {**self.environment(), "ASK_DELISKY_REQUEST_TIMEOUT_SECONDS": "150"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(self.ask_timeout(), 150)
        self.assertEqual(self.ask_timeout(environ=env), 150)

    @override_settings(ASK_DELISKY_REQUEST_TIMEOUT_SECONDS=None)
    def test_without_dev_default_legacy_configuration_is_preserved(self):
        with patch.dict(os.environ, self.environment(), clear=True):
            self.assertEqual(self.ask_timeout(), 120)

    def test_invalid_ask_override_is_rejected(self):
        for value in ("0", "-1", "bad", ""):
            with self.subTest(value=value), self.assertRaises(AskDeliskyProviderConfigurationError):
                self.ask_timeout(environ={
                    **self.environment(), "ASK_DELISKY_REQUEST_TIMEOUT_SECONDS": value,
                })

    def test_fresh_0004_has_schema_only_and_no_trigger_installation(self):
        migration = import_module("apps.assistant.migrations.0004_askdeliskydatarevision")
        self.assertEqual(len(migration.Migration.operations), 1)
        self.assertIsInstance(migration.Migration.operations[0], migrations.CreateModel)


@override_settings(ASK_DELISKY_CONTEXT_CACHE_ENABLED=True)
class OptionalRevisionTrackingTests(TransactionTestCase):
    def setUp(self):
        context_cache.clear_context_cache()
        self.command(enable=True)
        self.brand = DistributionBrand.objects.create(code="OPTIN", name="Tracking")
        self.addCleanup(context_cache.clear_context_cache)

    def command(self, **options):
        output = StringIO()
        call_command("configure_ask_context_cache", stdout=output, **options)
        return output.getvalue().strip()

    def test_cleanup_migration_removes_old_triggers_without_write_overhead(self):
        migration = import_module("apps.assistant.migrations.0005_remove_implicit_context_triggers")
        self.assertTrue(tracking_installed())
        with connection.schema_editor() as editor:
            migration.remove_implicit_tracking(None, editor)
        self.assertFalse(tracking_installed())
        before = AskDeliskyDataRevision.objects.get(pk=1).token
        DistributionBrand.objects.filter(pk=self.brand.pk).update(name="Changed without tracking")
        self.assertEqual(AskDeliskyDataRevision.objects.get(pk=1).token, before)
        # Cleanup is safe both after the old 0004 and on a fresh installation.
        with connection.schema_editor() as editor:
            migration.remove_implicit_tracking(None, editor)
        build = Mock(side_effect=context)
        self.assertIsNot(get(build), get(build))
        self.assertEqual(build.call_count, 2)

    @override_settings(ASK_DELISKY_CONTEXT_CACHE_ENABLED=False)
    def test_disabled_environment_cannot_install_triggers(self):
        self.command(disable=True)
        with self.assertRaisesMessage(CommandError, "ASK_DELISKY_CONTEXT_CACHE_ENABLED"):
            self.command(enable=True)
        self.assertFalse(tracking_installed())

    def test_disable_and_reenable_rotate_revision_and_prevent_stale_reuse(self):
        build = Mock(side_effect=context)
        first = get(build)
        original_revision = context_cache._data_revision()
        self.command(disable=True)
        self.assertEqual(self.command(status=True), "disabled")
        DistributionBrand.objects.filter(pk=self.brand.pk).update(name="Untracked edit")
        self.command(enable=True)
        self.assertEqual(self.command(status=True), "enabled")
        self.assertNotEqual(context_cache._data_revision(), original_revision)
        self.assertIsNot(get(build), first)
        get(build)
        self.assertEqual(build.call_count, 2)

    def test_missing_one_trigger_bypasses_existing_cache(self):
        build = Mock(side_effect=context)
        first = get(build)
        with connection.cursor() as cursor:
            cursor.execute("DROP TRIGGER ask_delisky_context_changed ON fleet_truck")
        self.assertFalse(tracking_installed())
        self.assertIsNot(get(build), first)
        get(build)
        self.assertEqual(build.call_count, 3)

    def test_reverse_cleanup_removes_explicit_tracking_before_table_rollback(self):
        migration = import_module("apps.assistant.migrations.0005_remove_implicit_context_triggers")
        self.assertTrue(tracking_installed())
        with connection.schema_editor() as editor:
            migration.Migration.operations[0].reverse_code(None, editor)
        self.assertFalse(tracking_installed())
