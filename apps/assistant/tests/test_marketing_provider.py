from unittest.mock import patch

from django.test import SimpleTestCase

from apps.assistant.marketing_helper import (
    MarketingHelperRequest,
)
from apps.assistant.marketing_provider import (
    LocalMarketingHelperProvider,
)
from apps.assistant.marketing_provider_factory import (
    MARKETING_HELPER_NUM_PREDICT,
    MarketingHelperProviderConfigurationError,
    MarketingHelperProviderDisabledError,
    build_marketing_helper_provider,
)
from apps.assistant.config import (
    AskDeliskyProviderConfig,
    AskDeliskyProviderMode,
)


class FakeTransport:
    def __init__(self):
        self.kwargs = None

    def generate(self, **kwargs):
        self.kwargs = kwargs
        return "Commercial advice"


class MarketingProviderTests(SimpleTestCase):
    def local_config(self):
        return AskDeliskyProviderConfig(
            mode=AskDeliskyProviderMode.LOCAL,
            model_name="test-model",
            base_url="http://127.0.0.1:11434",
            timeout_seconds=30,
        )

    def test_local_provider_uses_general_marketing_prompt(
        self
    ):
        transport = FakeTransport()

        provider = LocalMarketingHelperProvider(
            config=self.local_config(),
            transport=transport,
        )

        response = provider.generate(
            MarketingHelperRequest(
                question=(
                    "How can we improve supermarket sales?"
                )
            )
        )

        self.assertEqual(
            response.answer,
            "Commercial advice",
        )

        self.assertIn(
            "general trained knowledge",
            transport.kwargs["system_prompt"],
        )
        self.assertNotIn(
            "ANALYTICAL_CONTEXT_JSON",
            transport.kwargs["user_prompt"],
        )
        self.assertIn(
            "How can we improve supermarket sales?",
            transport.kwargs["user_prompt"],
        )

    def test_factory_uses_larger_generation_budget(
        self
    ):
        environ = {
            "ASK_DELISKY_PROVIDER": "local",
            "ASK_DELISKY_LOCAL_MODEL": "test-model",
            "ASK_DELISKY_LOCAL_BASE_URL":
                "http://127.0.0.1:11434",
            "ASK_DELISKY_TIMEOUT_SECONDS": "30",
        }

        with patch(
            "apps.assistant.marketing_provider_factory."
            "OllamaTransport"
        ) as transport_class:
            build_marketing_helper_provider(
                environ=environ
            )

        transport_class.assert_called_once_with(
            num_predict=MARKETING_HELPER_NUM_PREDICT
        )

        self.assertEqual(
            MARKETING_HELPER_NUM_PREDICT,
            256,
        )

    def test_disabled_provider_is_rejected(self):
        with self.assertRaises(
            MarketingHelperProviderDisabledError
        ):
            build_marketing_helper_provider(
                environ={
                    "ASK_DELISKY_PROVIDER": "disabled",
                }
            )

    def test_invalid_provider_config_is_normalized(
        self
    ):
        with self.assertRaises(
            MarketingHelperProviderConfigurationError
        ):
            build_marketing_helper_provider(
                environ={
                    "ASK_DELISKY_PROVIDER": "invalid",
                }
            )
