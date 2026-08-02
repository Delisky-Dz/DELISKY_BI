import json
from datetime import date
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.analytics.services.manager_insights_orchestrator import (
    ManagerInsightsResult,
)
from apps.assistant.contracts import (
    AskDeliskyProviderResult,
)
from apps.assistant.provider_factory import (
    AskDeliskyProviderDisabledError,
)
from apps.assistant.runtime import (
    ask_manager_delisky,
)


class FakeProvider:
    def __init__(self):
        self.request = None

    def generate(self, request):
        self.request = request

        return AskDeliskyProviderResult(
            answer="manager answer",
            provider_name="fake-local",
            model_name="fake-model",
        )


class AskManagerDeliskyRuntimeTests(SimpleTestCase):
    def make_insights_result(self):
        return ManagerInsightsResult(
            requested_period_start=date(2026, 7, 1),
            requested_period_end=date(2026, 7, 7),
            brand_id=1,
            insights=(),
        )

    @patch(
        "apps.assistant.runtime.build_manager_insights"
    )
    @patch(
        "apps.assistant.runtime.build_ask_delisky_provider"
    )
    def test_runtime_builds_safe_manager_request(
        self,
        provider_builder,
        insights_builder,
    ):
        provider = FakeProvider()

        provider_builder.return_value = provider
        insights_builder.return_value = (
            self.make_insights_result()
        )

        environ = {
            "ASK_DELISKY_PROVIDER": "local",
        }

        response = ask_manager_delisky(
            question="  Analyze manager data  ",
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
            brand_id=1,
            environ=environ,
        )

        provider_builder.assert_called_once_with(
            environ=environ
        )

        insights_builder.assert_called_once_with(
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
            brand_id=1,
        )

        self.assertEqual(
            provider.request.question,
            "Analyze manager data",
        )

        payload = json.loads(
            provider.request.context_json
        )

        self.assertEqual(
            payload["schema_version"],
            "1",
        )
        self.assertEqual(
            payload["scope"]["period_start"],
            "2026-07-01",
        )
        self.assertEqual(
            payload["scope"]["period_end"],
            "2026-07-07",
        )
        self.assertEqual(
            payload["scope"]["brand_id"],
            1,
        )
        self.assertEqual(
            payload["insights"],
            [],
        )

        self.assertEqual(
            response.answer,
            "manager answer",
        )
        self.assertEqual(
            response.provider_name,
            "fake-local",
        )
        self.assertEqual(
            response.model_name,
            "fake-model",
        )
        self.assertEqual(
            response.context_schema_version,
            "1",
        )

    @patch(
        "apps.assistant.runtime.build_manager_insights"
    )
    @patch(
        "apps.assistant.runtime.build_ask_delisky_provider"
    )
    def test_disabled_provider_fails_before_analytics(
        self,
        provider_builder,
        insights_builder,
    ):
        provider_builder.side_effect = (
            AskDeliskyProviderDisabledError(
                "Ask DELISKY provider is disabled."
            )
        )

        with self.assertRaises(
            AskDeliskyProviderDisabledError
        ):
            ask_manager_delisky(
                question="Analyze",
                period_start=date(2026, 7, 1),
                period_end=date(2026, 7, 7),
                brand_id=1,
                environ={},
            )

        insights_builder.assert_not_called()

    @patch(
        "apps.assistant.runtime.build_manager_insights"
    )
    @patch(
        "apps.assistant.runtime.build_ask_delisky_provider"
    )
    def test_runtime_preserves_unfiltered_scope(
        self,
        provider_builder,
        insights_builder,
    ):
        provider = FakeProvider()

        provider_builder.return_value = provider
        insights_builder.return_value = (
            ManagerInsightsResult(
                requested_period_start=None,
                requested_period_end=None,
                brand_id=None,
                insights=(),
            )
        )

        ask_manager_delisky(
            question="Analyze",
            environ={
                "ASK_DELISKY_PROVIDER": "local",
            },
        )

        payload = json.loads(
            provider.request.context_json
        )

        self.assertIsNone(
            payload["scope"]["period_start"]
        )
        self.assertIsNone(
            payload["scope"]["period_end"]
        )
        self.assertIsNone(
            payload["scope"]["brand_id"]
        )

        insights_builder.assert_called_once_with(
            period_start=None,
            period_end=None,
            brand_id=None,
        )
