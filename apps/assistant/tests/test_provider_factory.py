import json
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.assistant.contracts import (
    AskDeliskyProviderRequest,
)
from apps.assistant.local_provider import (
    LocalAskDeliskyProvider,
)
from apps.assistant.provider_factory import (
    AskDeliskyProviderConfigurationError,
    AskDeliskyProviderDisabledError,
    build_ask_delisky_provider,
)


class FakeLocalTransport:
    def __init__(self):
        self.kwargs = None

    def generate(self, **kwargs):
        self.kwargs = kwargs
        return "factory answer"


class AskDeliskyProviderFactoryTests(SimpleTestCase):
    def local_environment(self):
        return {
            "ASK_DELISKY_PROVIDER": "local",
            "ASK_DELISKY_LOCAL_MODEL": (
                "qwen3:4b-instruct"
            ),
            "ASK_DELISKY_LOCAL_BASE_URL": (
                "http://127.0.0.1:11434"
            ),
            "ASK_DELISKY_TIMEOUT_SECONDS": "120",
        }

    def test_provider_is_disabled_by_default(self):
        with self.assertRaisesRegex(
            AskDeliskyProviderDisabledError,
            "provider is disabled",
        ):
            build_ask_delisky_provider(
                environ={}
            )

    def test_local_provider_uses_injected_transport(self):
        transport = FakeLocalTransport()

        provider = build_ask_delisky_provider(
            environ=self.local_environment(),
            local_transport=transport,
        )

        self.assertIsInstance(
            provider,
            LocalAskDeliskyProvider,
        )

        result = provider.generate(
            AskDeliskyProviderRequest(
                question="Analyze",
                context_json='{"insights":[]}',
                context_schema_version="1",
            )
        )

        self.assertEqual(
            result.answer,
            "factory answer",
        )
        self.assertEqual(
            result.provider_name,
            "local",
        )
        self.assertEqual(
            result.model_name,
            "qwen3:4b-instruct",
        )

        self.assertEqual(
            transport.kwargs["base_url"],
            "http://127.0.0.1:11434",
        )
        self.assertEqual(
            transport.kwargs["timeout_seconds"],
            120,
        )

    def test_default_local_transport_is_ollama(self):
        with patch(
            "apps.assistant.provider_factory.OllamaTransport"
        ) as transport_class:
            provider = build_ask_delisky_provider(
                environ=self.local_environment()
            )

        transport_class.assert_called_once_with(
            num_predict=256
        )

        self.assertIsInstance(
            provider,
            LocalAskDeliskyProvider,
        )

    def test_invalid_provider_configuration_is_rejected(self):
        with self.assertRaises(
            AskDeliskyProviderConfigurationError
        ):
            build_ask_delisky_provider(
                environ={
                    "ASK_DELISKY_PROVIDER": "unknown",
                }
            )

    def test_analytical_answer_budget_reaches_ollama_request(self):
        # Regression: the 96-token default cut real Arabic analysis
        # mid-sentence before the evidence limitations were returned.
        from apps.assistant.tests.test_ollama_transport import (
            FakeOpener,
            FakeResponse,
        )

        opener = FakeOpener(
            response=FakeResponse(
                b'{"response":"Complete analysis.","done":true}'
            )
        )
        provider = build_ask_delisky_provider(
            environ=self.local_environment()
        )
        with patch(
            "apps.assistant.ollama_transport.build_opener",
            return_value=opener,
        ):
            result = provider.generate(
                AskDeliskyProviderRequest(
                    question="Give one insight, evidence and limitations.",
                    context_json='{"schema_version":"2","insights":[]}',
                    context_schema_version="2",
                )
            )

        payload = json.loads(opener.request.data.decode("utf-8"))
        self.assertEqual(payload["options"]["num_predict"], 256)
        self.assertEqual(result.answer, "Complete analysis.")
        self.assertEqual(opener.timeout, 120)
