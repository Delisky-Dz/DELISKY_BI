from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.assistant.marketing_helper import (
    MarketingHelperResponse,
)
from apps.assistant.marketing_provider_factory import (
    MarketingHelperProviderConfigurationError,
    MarketingHelperProviderDisabledError,
)
from apps.assistant.models import (
    AskDeliskyAuditEvent,
    AskDeliskyAuditOutcome,
    AskDeliskyAuditScope,
    AskDeliskyRateLimit,
)
from apps.assistant.ollama_transport import (
    OllamaTransportError,
)
from apps.assistant.rate_limit import (
    MARKETING_HELPER_SCOPE,
    AskDeliskyRateLimitConfigurationError,
    AskDeliskyRateLimitResult,
)

from .forms import MarketingHelperForm


class MarketingHelperFormTests(TestCase):
    def test_question_is_required(self):
        form = MarketingHelperForm(
            data={
                "question": "   ",
            }
        )

        self.assertFalse(
            form.is_valid()
        )
        self.assertIn(
            "question",
            form.errors,
        )

    def test_question_is_limited_to_1000_characters(
        self
    ):
        form = MarketingHelperForm(
            data={
                "question": "x" * 1001,
            }
        )

        self.assertFalse(
            form.is_valid()
        )


class MarketingHelperApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

        User = get_user_model()

        cls.manager = User.objects.create_user(
            username="marketing_helper_manager",
            password="Temporary-Test-Password-2026",
            is_active=True,
        )
        cls.manager.groups.add(
            Group.objects.get(name="Manager")
        )

        cls.accountant = User.objects.create_user(
            username="marketing_helper_accountant",
            password="Temporary-Test-Password-2026",
            is_active=True,
        )
        cls.accountant.groups.add(
            Group.objects.get(name="Accountant")
        )

    def api_url(self):
        return reverse(
            "dashboard:marketing_helper"
        )

    def test_manager_dashboard_renders_both_ai_assistants(
        self
    ):
        self.client.force_login(
            self.manager
        )

        response = self.client.get(
            reverse(
                "dashboard:manager_dashboard"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        html = response.content.decode(
            "utf-8"
        )

        self.assertIn(
            "data-ask-delisky",
            html,
        )
        self.assertIn(
            "data-marketing-helper",
            html,
        )
        self.assertIn(
            'data-assistant-kind="analytics"',
            html,
        )
        self.assertIn(
            'data-assistant-kind="marketing"',
            html,
        )
        self.assertIn(
            'href="#marketing-helper-title"',
            html,
        )
        self.assertIn(
            reverse(
                "dashboard:marketing_helper"
            ),
            html,
        )
        self.assertGreaterEqual(
            html.count(
                "data-robot-icon"
            ),
            2,
        )

    def test_anonymous_user_is_redirected(self):
        response = self.client.post(
            self.api_url(),
            {
                "question": "Give advice",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_accountant_cannot_use_helper(self):
        self.client.force_login(
            self.accountant
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Give advice",
            },
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_manager_get_is_not_allowed(self):
        self.client.force_login(
            self.manager
        )

        response = self.client.get(
            self.api_url()
        )

        self.assertEqual(
            response.status_code,
            405,
        )

    @patch(
        "apps.dashboard.views.ask_marketing_helper"
    )
    def test_valid_request_calls_runtime(
        self,
        mocked_runtime,
    ):
        mocked_runtime.return_value = (
            MarketingHelperResponse(
                answer="Commercial advice",
                provider_name="local",
                model_name="qwen3:4b-instruct",
            )
        )

        self.client.force_login(
            self.manager
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "  Improve distribution  ",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        mocked_runtime.assert_called_once_with(
            question="Improve distribution",
        )

        self.assertEqual(
            response.json(),
            {
                "ok": True,
                "answer": "Commercial advice",
                "provider": "local",
                "model": "qwen3:4b-instruct",
            },
        )

        bucket = AskDeliskyRateLimit.objects.get(
            user=self.manager,
            scope=MARKETING_HELPER_SCOPE,
        )

        self.assertEqual(
            bucket.request_count,
            1,
        )

    @patch(
        "apps.dashboard.views.ask_marketing_helper"
    )
    def test_invalid_request_does_not_call_runtime(
        self,
        mocked_runtime,
    ):
        self.client.force_login(
            self.manager
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "   ",
            },
        )

        self.assertEqual(
            response.status_code,
            400,
        )
        mocked_runtime.assert_not_called()

        self.assertEqual(
            response.json()["error"]["code"],
            "INVALID_REQUEST",
        )

    @patch(
        "apps.dashboard.views.ask_marketing_helper"
    )
    @patch(
        "apps.dashboard.views.check_ask_delisky_rate_limit"
    )
    def test_rate_limit_uses_marketing_scope(
        self,
        mocked_rate_limit,
        mocked_runtime,
    ):
        mocked_rate_limit.return_value = (
            AskDeliskyRateLimitResult(
                allowed=True
            )
        )

        mocked_runtime.return_value = (
            MarketingHelperResponse(
                answer="Advice",
                provider_name="local",
                model_name="model",
            )
        )

        self.client.force_login(
            self.manager
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Help",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        mocked_rate_limit.assert_called_once_with(
            user=self.manager,
            scope=MARKETING_HELPER_SCOPE,
        )

    @patch(
        "apps.dashboard.views.ask_marketing_helper"
    )
    @patch(
        "apps.dashboard.views.check_ask_delisky_rate_limit"
    )
    def test_rate_limited_request_does_not_call_runtime(
        self,
        mocked_rate_limit,
        mocked_runtime,
    ):
        mocked_rate_limit.return_value = (
            AskDeliskyRateLimitResult(
                allowed=False,
                retry_after_seconds=31,
            )
        )

        self.client.force_login(
            self.manager
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Help",
            },
        )

        self.assertEqual(
            response.status_code,
            429,
        )
        self.assertEqual(
            response["Retry-After"],
            "31",
        )
        mocked_runtime.assert_not_called()

    @patch(
        "apps.dashboard.views.ask_marketing_helper"
    )
    @patch(
        "apps.dashboard.views.check_ask_delisky_rate_limit"
    )
    def test_invalid_rate_limit_config_is_safe(
        self,
        mocked_rate_limit,
        mocked_runtime,
    ):
        mocked_rate_limit.side_effect = (
            AskDeliskyRateLimitConfigurationError(
                "private detail"
            )
        )

        self.client.force_login(
            self.manager
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Help",
            },
        )

        self.assertEqual(
            response.status_code,
            503,
        )
        self.assertNotIn(
            "private detail",
            str(response.json()),
        )
        mocked_runtime.assert_not_called()

    @patch(
        "apps.dashboard.views.ask_marketing_helper"
    )
    def test_provider_configuration_error_is_safe(
        self,
        mocked_runtime,
    ):
        mocked_runtime.side_effect = (
            MarketingHelperProviderConfigurationError(
                "private detail"
            )
        )

        self.client.force_login(
            self.manager
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Help",
            },
        )

        self.assertEqual(
            response.status_code,
            503,
        )
        self.assertEqual(
            response.json()["error"]["code"],
            "PROVIDER_CONFIGURATION_ERROR",
        )
        self.assertNotIn(
            "private detail",
            str(response.json()),
        )

    @patch(
        "apps.dashboard.views.ask_marketing_helper"
    )
    def test_disabled_provider_is_safe(
        self,
        mocked_runtime,
    ):
        mocked_runtime.side_effect = (
            MarketingHelperProviderDisabledError(
                "private detail"
            )
        )

        self.client.force_login(
            self.manager
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Help",
            },
        )

        self.assertEqual(
            response.status_code,
            503,
        )
        self.assertEqual(
            response.json()["error"]["code"],
            "PROVIDER_DISABLED",
        )

    @patch(
        "apps.dashboard.views.ask_marketing_helper"
    )
    def test_ollama_failure_is_safe(
        self,
        mocked_runtime,
    ):
        mocked_runtime.side_effect = (
            OllamaTransportError(
                "private detail"
            )
        )

        self.client.force_login(
            self.manager
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Help",
            },
        )

        self.assertEqual(
            response.status_code,
            503,
        )
        self.assertEqual(
            response.json()["error"]["code"],
            "PROVIDER_UNAVAILABLE",
        )
        self.assertNotIn(
            "private detail",
            str(response.json()),
        )


class MarketingHelperAuditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

        User = get_user_model()

        cls.manager = User.objects.create_user(
            username="marketing_audit_manager",
            password="Temporary-Test-Password-2026",
            is_active=True,
        )
        cls.manager.groups.add(
            Group.objects.get(name="Manager")
        )

    def setUp(self):
        self.client.force_login(
            self.manager
        )

    def api_url(self):
        return reverse(
            "dashboard:marketing_helper"
        )

    def latest_event(self):
        return (
            AskDeliskyAuditEvent.objects
            .filter(
                scope=(
                    AskDeliskyAuditScope
                    .MARKETING_HELPER
                )
            )
            .latest("created_at")
        )

    @patch(
        "apps.dashboard.views.ask_marketing_helper"
    )
    def test_success_is_audited_without_content(
        self,
        mocked_runtime,
    ):
        mocked_runtime.return_value = (
            MarketingHelperResponse(
                answer="PRIVATE ANSWER MUST NOT BE STORED",
                provider_name="local",
                model_name="model",
            )
        )

        response = self.client.post(
            self.api_url(),
            {
                "question":
                    "PRIVATE QUESTION MUST NOT BE STORED",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        event = self.latest_event()

        self.assertEqual(
            event.user,
            self.manager,
        )
        self.assertEqual(
            event.scope,
            AskDeliskyAuditScope.MARKETING_HELPER,
        )
        self.assertEqual(
            event.outcome,
            AskDeliskyAuditOutcome.SUCCESS,
        )
        self.assertEqual(
            event.http_status,
            200,
        )
        self.assertIsNotNone(
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

        stored_values = " ".join(
            str(value)
            for value in event.__dict__.values()
        )

        self.assertNotIn(
            "PRIVATE QUESTION MUST NOT BE STORED",
            stored_values,
        )
        self.assertNotIn(
            "PRIVATE ANSWER MUST NOT BE STORED",
            stored_values,
        )

    @patch(
        "apps.dashboard.views.ask_marketing_helper"
    )
    def test_invalid_request_is_audited(
        self,
        mocked_runtime,
    ):
        response = self.client.post(
            self.api_url(),
            {
                "question": "   ",
            },
        )

        self.assertEqual(
            response.status_code,
            400,
        )
        mocked_runtime.assert_not_called()

        event = self.latest_event()

        self.assertEqual(
            event.outcome,
            AskDeliskyAuditOutcome.INVALID_REQUEST,
        )
        self.assertEqual(
            event.http_status,
            400,
        )

    @patch(
        "apps.dashboard.views.ask_marketing_helper"
    )
    @patch(
        "apps.dashboard.views.check_ask_delisky_rate_limit"
    )
    def test_rate_limited_request_is_audited(
        self,
        mocked_rate_limit,
        mocked_runtime,
    ):
        mocked_rate_limit.return_value = (
            AskDeliskyRateLimitResult(
                allowed=False,
                retry_after_seconds=20,
            )
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Help",
            },
        )

        self.assertEqual(
            response.status_code,
            429,
        )
        mocked_runtime.assert_not_called()

        event = self.latest_event()

        self.assertEqual(
            event.outcome,
            AskDeliskyAuditOutcome.RATE_LIMITED,
        )
        self.assertEqual(
            event.http_status,
            429,
        )

    @patch(
        "apps.dashboard.views.ask_marketing_helper"
    )
    def test_provider_unavailable_is_audited(
        self,
        mocked_runtime,
    ):
        mocked_runtime.side_effect = (
            OllamaTransportError(
                "private detail"
            )
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Help",
            },
        )

        self.assertEqual(
            response.status_code,
            503,
        )

        event = self.latest_event()

        self.assertEqual(
            event.outcome,
            AskDeliskyAuditOutcome.PROVIDER_UNAVAILABLE,
        )
        self.assertEqual(
            event.http_status,
            503,
        )
