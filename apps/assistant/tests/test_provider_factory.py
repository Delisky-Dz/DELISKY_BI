from unittest.mock import patch

from django.test import SimpleTestCase

from apps.assistant.contracts import (
    AskDeliskyProviderRequest,
)
from apps.assistant.local_provider import (
    LocalAskDeliskyProvider,
)
from apps.assistant.provider_factory import (
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

        transport_class.assert_called_once_with()

        self.assertIsInstance(
            provider,
            LocalAskDeliskyProvider,
        )

    def test_invalid_provider_configuration_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "must be 'disabled' or 'local'",
        ):
            build_ask_delisky_provider(
                environ={
                    "ASK_DELISKY_PROVIDER": "unknown",
                }
            )
