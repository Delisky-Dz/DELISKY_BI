from datetime import date
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.assistant.contracts import (
    AskDeliskyResponse,
)
from apps.assistant.models import (
    AskDeliskyAuditEvent,
    AskDeliskyAuditOutcome,
)
from apps.assistant.ollama_transport import (
    OllamaTransportError,
)
from apps.assistant.provider_factory import (
    AskDeliskyProviderConfigurationError,
    AskDeliskyProviderDisabledError,
)
from apps.assistant.rate_limit import (
    AskDeliskyRateLimitConfigurationError,
    AskDeliskyRateLimitResult,
)
from apps.imports.models import DistributionBrand

from .forms import AskDeliskyForm


class AskDeliskyFormTests(TestCase):
    def test_question_is_required(self):
        form = AskDeliskyForm(
            data={
                "question": "   ",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            "question",
            form.errors,
        )

    def test_filter_validation_is_reused(self):
        form = AskDeliskyForm(
            data={
                "question": "Analyze",
                "period_start": "2026-07-20",
                "period_end": "2026-07-01",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertTrue(
            form.non_field_errors()
        )


class AskDeliskyApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

        User = get_user_model()

        cls.manager = User.objects.create_user(
            username="ask_delisky_manager",
            password="Temporary-Test-Password-2026",
            is_active=True,
        )
        cls.manager.groups.add(
            Group.objects.get(name="Manager")
        )

        cls.accountant = User.objects.create_user(
            username="ask_delisky_accountant",
            password="Temporary-Test-Password-2026",
            is_active=True,
        )
        cls.accountant.groups.add(
            Group.objects.get(name="Accountant")
        )

        cls.accountant_manager = User.objects.create_user(
            username="ask_delisky_accountant_manager",
            password="Temporary-Test-Password-2026",
            is_active=True,
        )
        cls.accountant_manager.groups.add(
            Group.objects.get(name="Accountant"),
            Group.objects.get(name="Manager"),
        )

        cls.superuser_manager = User.objects.create_user(
            username="ask_delisky_superuser_manager",
            password="Temporary-Test-Password-2026",
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        cls.superuser_manager.groups.add(
            Group.objects.get(name="Manager")
        )

        cls.super_admin_manager = User.objects.create_user(
            username="ask_delisky_super_admin_manager",
            password="Temporary-Test-Password-2026",
            is_active=True,
        )
        cls.super_admin_manager.groups.add(
            Group.objects.get(name="Super Admin"),
            Group.objects.get(name="Manager"),
        )

        cls.brand = DistributionBrand.objects.create(
            code="ASKTEST",
            name="Ask DELISKY Test",
            is_active=True,
        )

    def api_url(self):
        return reverse(
            "dashboard:ask_delisky"
        )

    def test_anonymous_user_is_redirected(self):
        response = self.client.post(
            self.api_url(),
            {
                "question": "Analyze",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_accountant_cannot_use_assistant(self):
        self.client.force_login(
            self.accountant
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Analyze",
            },
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_accountant_role_cannot_use_assistant_even_in_manager_group(
        self
    ):
        self.client.force_login(
            self.accountant_manager
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Analyze",
            },
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_superuser_cannot_use_assistant_even_in_manager_group(
        self
    ):
        self.client.force_login(
            self.superuser_manager
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Analyze",
            },
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_super_admin_role_cannot_use_assistant_even_in_manager_group(
        self
    ):
        self.client.force_login(
            self.super_admin_manager
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Analyze",
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
        "apps.dashboard.views.ask_manager_delisky"
    )
    def test_valid_request_calls_runtime(
        self,
        mocked_runtime,
    ):
        mocked_runtime.return_value = (
            AskDeliskyResponse(
                answer="Manager answer",
                provider_name="local",
                model_name="qwen3:4b-instruct",
                context_schema_version="1",
            )
        )

        self.client.force_login(
            self.manager
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "  Analyze results  ",
                "period_start": "2026-07-01",
                "period_end": "2026-07-20",
                "brand": str(self.brand.pk),
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        mocked_runtime.assert_called_once_with(
            question="Analyze results",
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 20),
            brand_id=self.brand.pk,
        )

        payload = response.json()

        self.assertEqual(
            payload,
            {
                "ok": True,
                "answer": "Manager answer",
                "provider": "local",
                "model": "qwen3:4b-instruct",
                "context_schema_version": "1",
            },
        )

        self.assertNotIn(
            "context",
            payload,
        )

    @patch(
        "apps.dashboard.views.ask_manager_delisky"
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
                retry_after_seconds=37,
            )
        )

        self.client.force_login(
            self.manager
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Analyze",
            },
        )

        self.assertEqual(
            response.status_code,
            429,
        )
        self.assertEqual(
            response["Retry-After"],
            "37",
        )

        payload = response.json()

        self.assertFalse(
            payload["ok"]
        )
        self.assertEqual(
            payload["error"]["code"],
            "RATE_LIMITED",
        )

        mocked_runtime.assert_not_called()

    @patch(
        "apps.dashboard.views.ask_manager_delisky"
    )
    @patch(
        "apps.dashboard.views.check_ask_delisky_rate_limit"
    )
    def test_invalid_rate_limit_config_is_safe_503(
        self,
        mocked_rate_limit,
        mocked_runtime,
    ):
        mocked_rate_limit.side_effect = (
            AskDeliskyRateLimitConfigurationError(
                "private rate-limit detail"
            )
        )

        self.client.force_login(
            self.manager
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Analyze",
            },
        )

        self.assertEqual(
            response.status_code,
            503,
        )

        payload = response.json()

        self.assertEqual(
            payload["error"]["code"],
            "RATE_LIMIT_CONFIGURATION_ERROR",
        )
        self.assertNotIn(
            "private rate-limit detail",
            str(payload),
        )

        mocked_runtime.assert_not_called()

    @patch(
        "apps.dashboard.views.ask_manager_delisky"
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
                "period_start": "2026-07-20",
                "period_end": "2026-07-01",
            },
        )

        self.assertEqual(
            response.status_code,
            400,
        )
        mocked_runtime.assert_not_called()

        payload = response.json()

        self.assertFalse(payload["ok"])
        self.assertEqual(
            payload["error"]["code"],
            "INVALID_REQUEST",
        )

    @patch(
        "apps.dashboard.views.ask_manager_delisky"
    )
    def test_invalid_provider_config_is_safe_503(
        self,
        mocked_runtime,
    ):
        mocked_runtime.side_effect = (
            AskDeliskyProviderConfigurationError(
                "private configuration detail"
            )
        )

        self.client.force_login(
            self.manager
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Analyze",
            },
        )

        self.assertEqual(
            response.status_code,
            503,
        )

        payload = response.json()

        self.assertEqual(
            payload["error"]["code"],
            "PROVIDER_CONFIGURATION_ERROR",
        )
        self.assertNotIn(
            "private configuration detail",
            str(payload),
        )

    @patch(
        "apps.dashboard.views.ask_manager_delisky"
    )
    def test_disabled_provider_is_safe_503(
        self,
        mocked_runtime,
    ):
        mocked_runtime.side_effect = (
            AskDeliskyProviderDisabledError(
                "internal detail"
            )
        )

        self.client.force_login(
            self.manager
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Analyze",
            },
        )

        self.assertEqual(
            response.status_code,
            503,
        )

        payload = response.json()

        self.assertEqual(
            payload["error"]["code"],
            "PROVIDER_DISABLED",
        )
        self.assertNotIn(
            "internal detail",
            str(payload),
        )

    @patch(
        "apps.dashboard.views.ask_manager_delisky"
    )
    def test_ollama_failure_is_safe_503(
        self,
        mocked_runtime,
    ):
        mocked_runtime.side_effect = (
            OllamaTransportError(
                "private transport detail"
            )
        )

        self.client.force_login(
            self.manager
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Analyze",
            },
        )

        self.assertEqual(
            response.status_code,
            503,
        )

        payload = response.json()

        self.assertEqual(
            payload["error"]["code"],
            "PROVIDER_UNAVAILABLE",
        )
        self.assertNotIn(
            "private transport detail",
            str(payload),
        )



class AskDeliskyEndpointAuditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

        User = get_user_model()

        cls.manager = User.objects.create_user(
            username="ask_endpoint_audit_manager",
            password="Temporary-Test-Password-2026",
            is_active=True,
        )
        cls.manager.groups.add(
            Group.objects.get(name="Manager")
        )

        cls.brand = DistributionBrand.objects.create(
            code="ASKAUDIT",
            name="Ask DELISKY Audit",
            is_active=True,
        )

    def setUp(self):
        self.client.force_login(
            self.manager
        )

    def api_url(self):
        return reverse(
            "dashboard:ask_delisky"
        )

    def assert_latest_event(
        self,
        *,
        outcome,
        http_status,
    ):
        event = (
            AskDeliskyAuditEvent.objects
            .latest("created_at")
        )

        self.assertEqual(
            event.user,
            self.manager,
        )
        self.assertEqual(
            event.outcome,
            outcome,
        )
        self.assertEqual(
            event.http_status,
            http_status,
        )
        self.assertIsNotNone(
            event.duration_ms
        )
        self.assertGreaterEqual(
            event.duration_ms,
            0,
        )

        return event

    @patch(
        "apps.dashboard.views.ask_manager_delisky"
    )
    def test_success_is_audited(
        self,
        mocked_runtime,
    ):
        mocked_runtime.return_value = (
            AskDeliskyResponse(
                answer="Safe answer",
                provider_name="local",
                model_name="qwen3:4b-instruct",
                context_schema_version="1",
            )
        )

        response = self.client.post(
            self.api_url(),
            {
                "question":
                    "PRIVATE QUESTION MUST NOT BE STORED",
                "period_start": "2026-07-01",
                "period_end": "2026-07-20",
                "brand": str(self.brand.pk),
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        event = self.assert_latest_event(
            outcome=(
                AskDeliskyAuditOutcome.SUCCESS
            ),
            http_status=200,
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
            self.brand.pk,
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
            "Safe answer",
            stored_values,
        )

    @patch(
        "apps.dashboard.views.ask_manager_delisky"
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

        self.assert_latest_event(
            outcome=(
                AskDeliskyAuditOutcome.INVALID_REQUEST
            ),
            http_status=400,
        )

    @patch(
        "apps.dashboard.views.ask_manager_delisky"
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
                retry_after_seconds=30,
            )
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Analyze",
            },
        )

        self.assertEqual(
            response.status_code,
            429,
        )
        mocked_runtime.assert_not_called()

        self.assert_latest_event(
            outcome=(
                AskDeliskyAuditOutcome.RATE_LIMITED
            ),
            http_status=429,
        )

    @patch(
        "apps.dashboard.views.ask_manager_delisky"
    )
    @patch(
        "apps.dashboard.views.check_ask_delisky_rate_limit"
    )
    def test_rate_limit_configuration_error_is_audited(
        self,
        mocked_rate_limit,
        mocked_runtime,
    ):
        mocked_rate_limit.side_effect = (
            AskDeliskyRateLimitConfigurationError(
                "private detail"
            )
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Analyze",
            },
        )

        self.assertEqual(
            response.status_code,
            503,
        )
        mocked_runtime.assert_not_called()

        self.assert_latest_event(
            outcome=(
                AskDeliskyAuditOutcome
                .RATE_LIMIT_CONFIGURATION_ERROR
            ),
            http_status=503,
        )

    @patch(
        "apps.dashboard.views.ask_manager_delisky"
    )
    def test_provider_configuration_error_is_audited(
        self,
        mocked_runtime,
    ):
        mocked_runtime.side_effect = (
            AskDeliskyProviderConfigurationError(
                "private detail"
            )
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Analyze",
            },
        )

        self.assertEqual(
            response.status_code,
            503,
        )

        self.assert_latest_event(
            outcome=(
                AskDeliskyAuditOutcome
                .PROVIDER_CONFIGURATION_ERROR
            ),
            http_status=503,
        )

    @patch(
        "apps.dashboard.views.ask_manager_delisky"
    )
    def test_disabled_provider_is_audited(
        self,
        mocked_runtime,
    ):
        mocked_runtime.side_effect = (
            AskDeliskyProviderDisabledError(
                "private detail"
            )
        )

        response = self.client.post(
            self.api_url(),
            {
                "question": "Analyze",
            },
        )

        self.assertEqual(
            response.status_code,
            503,
        )

        self.assert_latest_event(
            outcome=(
                AskDeliskyAuditOutcome.PROVIDER_DISABLED
            ),
            http_status=503,
        )

    @patch(
        "apps.dashboard.views.ask_manager_delisky"
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
                "question": "Analyze",
            },
        )

        self.assertEqual(
            response.status_code,
            503,
        )

        self.assert_latest_event(
            outcome=(
                AskDeliskyAuditOutcome
                .PROVIDER_UNAVAILABLE
            ),
            http_status=503,
        )


class AskDeliskyUiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_roles",
            stdout=StringIO(),
        )

        User = get_user_model()

        cls.manager = User.objects.create_user(
            username="ask_delisky_ui_manager",
            password="Temporary-Test-Password-2026",
            is_active=True,
        )
        cls.manager.groups.add(
            Group.objects.get(name="Manager")
        )

        cls.brand = DistributionBrand.objects.create(
            code="ASKUI",
            name="Ask DELISKY UI",
            is_active=True,
        )

    def setUp(self):
        self.client.force_login(
            self.manager
        )

    @patch(
        "apps.dashboard.views.build_manager_dashboard"
    )
    def test_dashboard_renders_assistant_with_filters(
        self,
        mocked_dashboard,
    ):
        from types import SimpleNamespace

        mocked_dashboard.return_value = (
            SimpleNamespace(
                summary=None,
                coverage=None,
                data_quality=None,
            )
        )

        response = self.client.get(
            reverse(
                "dashboard:manager_dashboard"
            ),
            {
                "period_start": "2026-07-01",
                "period_end": "2026-07-20",
                "brand": str(self.brand.pk),
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertTemplateUsed(
            response,
            "dashboard/partials/ask_delisky.html",
        )

        html = response.content.decode("utf-8")

        self.assertIn(
            "data-ask-delisky",
            html,
        )
        self.assertIn(
            "data-ask-delisky-form",
            html,
        )
        self.assertIn(
            'name="period_start"',
            html,
        )
        self.assertIn(
            'value="2026-07-01"',
            html,
        )
        self.assertIn(
            'value="2026-07-20"',
            html,
        )
        self.assertIn(
            f'value="{self.brand.pk}"',
            html,
        )
        self.assertIn(
            "csrfmiddlewaretoken",
            html,
        )

    @patch(
        "apps.dashboard.views.build_manager_dashboard"
    )
    def test_dashboard_renders_assistant_sidebar_link(
        self,
        mocked_dashboard,
    ):
        from types import SimpleNamespace

        mocked_dashboard.return_value = (
            SimpleNamespace(
                summary=None,
                coverage=None,
                data_quality=None,
            )
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

        html = response.content.decode("utf-8")

        self.assertIn(
            'href="#ask-delisky-title"',
            html,
        )
        self.assertIn(
            'id="ask-delisky-title"',
            html,
        )
        self.assertIn(
            "Ask DELISKY",
            html,
        )

    @patch(
        "apps.dashboard.views.build_manager_dashboard"
    )
    def test_invalid_filter_hides_assistant(
        self,
        mocked_dashboard,
    ):
        response = self.client.get(
            reverse(
                "dashboard:manager_dashboard"
            ),
            {
                "period_start": "2026-07-20",
                "period_end": "2026-07-01",
            },
        )

        self.assertEqual(
            response.status_code,
            400,
        )
        mocked_dashboard.assert_not_called()

        self.assertNotContains(
            response,
            "data-ask-delisky-form",
            status_code=400,
        )


class AskDeliskyJavascriptSafetyTests(TestCase):
    def test_assistant_uses_safe_text_rendering(self):
        javascript_path = (
            Path(__file__).resolve().parent
            / "static"
            / "dashboard"
            / "js"
            / "dashboard.js"
        )

        javascript = javascript_path.read_text(
            encoding="utf-8"
        )

        assistant_javascript = javascript.split(
            "/* DELISKY AI ASSISTANTS V2 */",
            maxsplit=1,
        )[1]

        self.assertIn(
            "fetch(",
            assistant_javascript,
        )
        self.assertIn(
            "new FormData(form)",
            assistant_javascript,
        )
        self.assertIn(
            "answerText.textContent",
            assistant_javascript,
        )
        self.assertIn(
            "form.reportValidity()",
            assistant_javascript,
        )
        self.assertNotIn(
            "innerHTML",
            assistant_javascript,
        )
