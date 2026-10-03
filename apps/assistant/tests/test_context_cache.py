from concurrent.futures import ThreadPoolExecutor
from datetime import date
from importlib import import_module
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.management import call_command
from io import StringIO
from django.db import close_old_connections, connection, transaction
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from apps.analytics.services.ask_delisky_context import AskDeliskyContext
from apps.assistant import context_cache as cache
from apps.imports.models import DistributionBrand


def context():
    return AskDeliskyContext(
        schema_version="2", requested_period_start="2026-04-04",
        requested_period_end="2026-08-26", brand_id=None, insights=(),
    )


def get(build, **overrides):
    scope = dict(period_start=date(2026, 4, 4), period_end=date(2026, 8, 26), brand_id=None)
    scope.update(overrides)
    return cache.get_manager_context(build=build, **scope)


@override_settings(ASK_DELISKY_CONTEXT_CACHE_ENABLED=True)
class ContextCacheUnitTests(SimpleTestCase):
    def setUp(self):
        cache.clear_context_cache()
        self.db = SimpleNamespace(
            vendor="postgresql", alias="default", in_atomic_block=False,
            settings_dict={"NAME": "delisky_bi_dev", "HOST": "localhost", "PORT": "5432"},
            get_autocommit=lambda: True,
        )
        p = patch.object(cache, "connection", self.db)
        p.start()
        self.addCleanup(p.stop)
        p = patch.object(cache, "_data_revision", return_value="revision-1")
        self.revision = p.start()
        self.addCleanup(p.stop)
        self.addCleanup(cache.clear_context_cache)

    def test_same_scope_reuses_immutable_context(self):
        build = Mock(side_effect=context)
        first = get(build)
        self.assertIs(get(build), first)
        self.assertEqual(first.to_payload(), context().to_payload())
        build.assert_called_once()

    def test_period_brand_and_database_are_separate(self):
        build = Mock(side_effect=context)
        get(build)
        get(build, brand_id=1)
        get(build, brand_id=2)
        get(build, period_end=date(2026, 8, 25))
        get(build, period_start=date(2026, 4, 5))
        self.db.settings_dict["HOST"] = "another-dev-host"
        get(build)
        self.assertEqual(build.call_count, 6)

    def test_context_version_change_is_a_miss(self):
        build = Mock(side_effect=context)
        first = get(build)
        with patch.object(cache, "CACHE_VERSION", "new-schema"):
            self.assertIsNot(get(build), first)

    def test_different_questions_reuse_analytics_but_never_provider_answers(self):
        from apps.analytics.services.manager_insights_orchestrator import ManagerInsightsResult
        from apps.assistant.contracts import AskDeliskyProviderResult
        from apps.assistant.runtime import ask_manager_delisky

        provider = Mock()
        provider.generate.side_effect = [
            AskDeliskyProviderResult(answer="First answer", provider_name="local"),
            AskDeliskyProviderResult(answer="Second answer", provider_name="local"),
        ]
        with patch("apps.assistant.runtime.build_ask_delisky_provider", return_value=provider), patch(
            "apps.assistant.runtime.build_manager_insights",
            return_value=ManagerInsightsResult(
                requested_period_start=date(2026, 4, 4),
                requested_period_end=date(2026, 8, 26), brand_id=None, insights=(),
            ),
        ) as analytics:
            answers = [ask_manager_delisky(
                question=question, period_start=date(2026, 4, 4),
                period_end=date(2026, 8, 26),
            ) for question in ("First question", "Second question")]
        analytics.assert_called_once()
        self.assertEqual(provider.generate.call_count, 2)
        requests = [call.args[0] for call in provider.generate.call_args_list]
        self.assertNotEqual(requests[0].question, requests[1].question)
        self.assertEqual(requests[0].context_json, requests[1].context_json)
        self.assertEqual([answer.answer for answer in answers], ["First answer", "Second answer"])

    def test_revision_change_invalidates_all_scopes(self):
        build = Mock(side_effect=context)
        get(build)
        get(build, brand_id=1)
        self.revision.return_value = "revision-2"
        get(build)
        get(build, brand_id=1)
        self.assertEqual(build.call_count, 4)

    def test_change_during_build_is_never_stored(self):
        build = Mock(side_effect=context)
        self.revision.side_effect = ["old", "new", "new", "new"]
        first = get(build)
        self.assertIsNot(get(build), first)
        self.assertEqual(build.call_count, 2)

    def test_expiry_and_lru_bound(self):
        build = Mock(side_effect=context)
        with patch.object(cache, "monotonic", return_value=100) as clock:
            first = get(build, brand_id=0)
            for brand in range(1, cache.CACHE_MAX_ENTRIES + 1):
                get(build, brand_id=brand)
            self.assertEqual(len(cache._entries), cache.CACHE_MAX_ENTRIES)
            self.assertIsNot(get(build, brand_id=0), first)
            retained = get(build, brand_id=0)
            clock.return_value = 100 + cache.CACHE_TTL_SECONDS
            self.assertIsNot(get(build, brand_id=0), retained)

    def test_failures_are_not_cached(self):
        build = Mock(side_effect=[ValueError("failed build"), context()])
        with self.assertRaises(ValueError):
            get(build)
        get(build)
        self.assertEqual(build.call_count, 2)

    def test_disabled_production_and_transactions_bypass_cache(self):
        build = Mock(side_effect=context)
        with override_settings(ASK_DELISKY_CONTEXT_CACHE_ENABLED=False):
            get(build)
            get(build)
        self.db.settings_dict["NAME"] = "delisky_bi"
        get(build)
        get(build)
        self.db.settings_dict["NAME"] = "delisky_bi_dev"
        self.db.in_atomic_block = True
        get(build)
        get(build)
        self.revision.assert_not_called()
        self.assertEqual(build.call_count, 6)

    def test_concurrent_same_scope_builds_once(self):
        entered, release = Event(), Event()
        def build():
            entered.set()
            if not release.wait(5):
                raise AssertionError("test release timed out")
            return context()
        builder = Mock(side_effect=build)
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(get, builder)
            self.assertTrue(entered.wait(5))
            second = pool.submit(get, builder)
            release.set()
            self.assertIs(first.result(timeout=5), second.result(timeout=5))
        builder.assert_called_once()


@override_settings(ASK_DELISKY_CONTEXT_CACHE_ENABLED=True)
class ContextRevisionDatabaseTests(TransactionTestCase):
    def setUp(self):
        call_command("configure_ask_context_cache", enable=True, stdout=StringIO())
        cache.clear_context_cache()
        self.addCleanup(cache.clear_context_cache)
        self.brand = DistributionBrand.objects.create(code="CACHE", name="Cache test")

    def test_all_source_tables_have_statement_triggers(self):
        migration = import_module("apps.assistant.revision_tracking")
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT c.relname FROM pg_trigger t
                JOIN pg_class c ON c.oid = t.tgrelid
                WHERE t.tgname = 'ask_delisky_context_changed'
            """)
            self.assertEqual({row[0] for row in cursor.fetchall()}, set(migration.SOURCE_TABLES))
            for table in migration.SOURCE_TABLES:
                before = cache._data_revision()
                # Statement triggers also cover bulk SQL without model signals.
                cursor.execute(f'UPDATE "{table}" SET id = id WHERE FALSE')
                self.assertNotEqual(cache._data_revision(), before)

    def test_bulk_insert_update_delete_invalidate_context(self):
        build = Mock(side_effect=context)
        previous = get(build)
        other = DistributionBrand(code="CACHE2", name="Another")
        DistributionBrand.objects.bulk_create([other])
        current = get(build)
        self.assertIsNot(current, previous)
        other.name = "Edited"
        DistributionBrand.objects.bulk_update([other], ["name"])
        newer = get(build)
        self.assertIsNot(newer, current)
        DistributionBrand.objects.filter(pk=other.pk).delete()
        self.assertIsNot(get(build), newer)
        self.assertEqual(build.call_count, 4)

    def test_rollback_keeps_committed_cache_and_never_stores_uncommitted(self):
        build = Mock(side_effect=context)
        first = get(build)
        revision = cache._data_revision()
        with transaction.atomic():
            DistributionBrand.objects.filter(pk=self.brand.pk).update(name="Uncommitted")
            self.assertNotEqual(cache._data_revision(), revision)
            self.assertIsNot(get(build), first)
            transaction.set_rollback(True)
        self.assertEqual(cache._data_revision(), revision)
        self.assertIs(get(build), first)
        self.assertEqual(build.call_count, 2)

    def test_other_connection_commit_invalidates_existing_entry(self):
        build = Mock(side_effect=context)
        first = get(build)
        def write():
            close_old_connections()
            try:
                DistributionBrand.objects.filter(pk=self.brand.pk).update(name="Other process")
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(write).result(timeout=10)
        self.assertIsNot(get(build), first)

    def test_commit_during_build_prevents_cache_publication(self):
        def changing_build():
            DistributionBrand.objects.filter(pk=self.brand.pk).update(name="Changed")
            return context()
        first = get(changing_build)
        build = Mock(side_effect=context)
        self.assertIsNot(get(build), first)
        get(build)
        build.assert_called_once()

    def test_opening_stock_before_period_invalidates_later_context(self):
        from django.contrib.auth import get_user_model
        from apps.imports.models import ImportBatch, ImportBatchStatus, ImportReportType

        user = get_user_model().objects.create_user(username="cache_uploader")
        batch = ImportBatch.objects.create(
            brand=self.brand, report_type=ImportReportType.OPENING_STOCK,
            period_start=date(2026, 3, 1), period_end=date(2026, 3, 1),
            original_filename="baseline.xlsx", uploaded_by=user, file_sha256="b" * 64,
            status=ImportBatchStatus.APPROVED,
        )
        build = Mock(side_effect=context)
        first = get(build)
        ImportBatch.objects.filter(pk=batch.pk).update(content_sha256="a" * 64)
        self.assertIsNot(get(build), first)
        self.assertEqual(build.call_count, 2)
