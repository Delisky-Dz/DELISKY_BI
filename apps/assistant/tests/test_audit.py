from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.assistant.audit import (
    AskDeliskyAuditRecord,
    record_ask_delisky_audit_event,
)
from apps.assistant.models import (
    AskDeliskyAuditEvent,
    AskDeliskyAuditOutcome,
    AskDeliskyAuditScope,
)


class AskDeliskyAuditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.user = User.objects.create_user(
            username="ask_audit_manager",
            password="Temporary-Test-Password-2026",
        )

    def test_records_safe_operational_metadata(self):
        event = record_ask_delisky_audit_event(
            user=self.user,
            record=AskDeliskyAuditRecord(
                outcome=(
                    AskDeliskyAuditOutcome.SUCCESS
                ),
                http_status=200,
                duration_ms=1420,
                period_start=date(
                    2026,
                    7,
                    1,
                ),
                period_end=date(
                    2026,
                    7,
                    20,
                ),
                brand_id=7,
            ),
        )

        event.refresh_from_db()

        self.assertEqual(
            event.user,
            self.user,
        )
        self.assertEqual(
            event.outcome,
            AskDeliskyAuditOutcome.SUCCESS,
        )
        self.assertEqual(
            event.http_status,
            200,
        )
        self.assertEqual(
            event.duration_ms,
            1420,
        )
        self.assertEqual(
            event.period_start,
            date(2026, 7, 1),
        )
        self.assertEqual(
            event.period_end,
            date(2026, 7, 20),
        )
        self.assertEqual(
            event.brand_id_value,
            7,
        )

    def test_audit_model_has_no_sensitive_content_fields(
        self
    ):
        field_names = {
            field.name
            for field in (
                AskDeliskyAuditEvent._meta.fields
            )
        }

        forbidden = {
            "question",
            "answer",
            "prompt",
            "context",
            "source",
            "credentials",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                field_names
            )
        )

    def test_default_scope_is_manager_ask(self):
        event = record_ask_delisky_audit_event(
            user=self.user,
            record=AskDeliskyAuditRecord(
                outcome=AskDeliskyAuditOutcome.SUCCESS,
                http_status=200,
            ),
        )

        self.assertEqual(
            event.scope,
            AskDeliskyAuditScope.MANAGER_ASK,
        )

    def test_marketing_helper_scope_is_supported(self):
        event = record_ask_delisky_audit_event(
            user=self.user,
            record=AskDeliskyAuditRecord(
                outcome=AskDeliskyAuditOutcome.SUCCESS,
                http_status=200,
                scope=(
                    AskDeliskyAuditScope
                    .MARKETING_HELPER
                ),
            ),
        )

        self.assertEqual(
            event.scope,
            AskDeliskyAuditScope.MARKETING_HELPER,
        )

    def test_minimal_failure_event_is_supported(self):
        event = record_ask_delisky_audit_event(
            user=self.user,
            record=AskDeliskyAuditRecord(
                outcome=(
                    AskDeliskyAuditOutcome.RATE_LIMITED
                ),
                http_status=429,
            ),
        )

        self.assertEqual(
            event.outcome,
            AskDeliskyAuditOutcome.RATE_LIMITED,
        )
        self.assertIsNone(
            event.duration_ms
        )
        self.assertIsNone(
            event.period_start
        )
        self.assertIsNone(
            event.period_end
        )
        self.assertIsNone(
            event.brand_id_value
        )
