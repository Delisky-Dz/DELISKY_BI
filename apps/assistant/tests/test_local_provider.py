from django.test import SimpleTestCase

from apps.assistant.config import (
    AskDeliskyProviderConfig,
    AskDeliskyProviderMode,
)
from apps.assistant.contracts import (
    AskDeliskyProviderRequest,
)
from apps.assistant.local_provider import (
    ASK_DELISKY_SYSTEM_PROMPT,
    LocalAskDeliskyProvider,
)


class FakeLocalTransport:
    def __init__(self, answer="local answer"):
        self.answer = answer
        self.kwargs = None

    def generate(self, **kwargs):
        self.kwargs = kwargs
        return self.answer


class LocalAskDeliskyProviderTests(SimpleTestCase):
    def make_config(self):
        return AskDeliskyProviderConfig(
            mode=AskDeliskyProviderMode.LOCAL,
            model_name="test-model",
            base_url="http://127.0.0.1:11434",
            timeout_seconds=30,
        )

    def make_request(self):
        return AskDeliskyProviderRequest(
            question="Analyze the results",
            context_json=(
                '{"schema_version":"1","insights":[]}'
            ),
            context_schema_version="1",
        )

    def test_disabled_configuration_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "requires local mode",
        ):
            LocalAskDeliskyProvider(
                config=AskDeliskyProviderConfig(
                    mode=(
                        AskDeliskyProviderMode.DISABLED
                    ),
                ),
                transport=FakeLocalTransport(),
            )

    def test_transport_receives_local_configuration(self):
        transport = FakeLocalTransport()

        provider = LocalAskDeliskyProvider(
            config=self.make_config(),
            transport=transport,
        )

        provider.generate(
            self.make_request()
        )

        self.assertEqual(
            transport.kwargs["base_url"],
            "http://127.0.0.1:11434",
        )
        self.assertEqual(
            transport.kwargs["model_name"],
            "test-model",
        )
        self.assertEqual(
            transport.kwargs["timeout_seconds"],
            30,
        )

    def test_transport_receives_fixed_system_prompt(self):
        transport = FakeLocalTransport()

        provider = LocalAskDeliskyProvider(
            config=self.make_config(),
            transport=transport,
        )

        provider.generate(
            self.make_request()
        )

        self.assertEqual(
            transport.kwargs["system_prompt"],
            ASK_DELISKY_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Do not invent facts",
            transport.kwargs["system_prompt"],
        )
        self.assertIn(
            "Do not claim causation",
            transport.kwargs["system_prompt"],
        )

    def test_user_prompt_contains_only_provider_request_data(
        self,
    ):
        transport = FakeLocalTransport()

        provider = LocalAskDeliskyProvider(
            config=self.make_config(),
            transport=transport,
        )

        request = self.make_request()

        provider.generate(request)

        user_prompt = transport.kwargs["user_prompt"]

        self.assertIn(
            request.question,
            user_prompt,
        )
        self.assertIn(
            request.context_json,
            user_prompt,
        )
        self.assertIn(
            request.context_schema_version,
            user_prompt,
        )

    def test_provider_returns_local_metadata(self):
        transport = FakeLocalTransport(
            answer="  result  "
        )

        provider = LocalAskDeliskyProvider(
            config=self.make_config(),
            transport=transport,
        )

        result = provider.generate(
            self.make_request()
        )

        self.assertEqual(
            result.answer,
            "result",
        )
        self.assertEqual(
            result.provider_name,
            "local",
        )
        self.assertEqual(
            result.model_name,
            "test-model",
        )

    def test_empty_transport_answer_is_rejected(self):
        provider = LocalAskDeliskyProvider(
            config=self.make_config(),
            transport=FakeLocalTransport(
                answer="   "
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "answer cannot be empty",
        ):
            provider.generate(
                self.make_request()
            )


from django.test import SimpleTestCase

from apps.assistant.local_provider import (
    ASK_DELISKY_SYSTEM_PROMPT,
)


class AskDeliskyAnalyticalBoundaryTests(
    SimpleTestCase
):
    def test_system_prompt_forbids_generic_advice_when_context_is_insufficient(
        self,
    ):
        self.assertIn(
            "say so clearly and stop",
            ASK_DELISKY_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Do not replace missing evidence with general advice",
            ASK_DELISKY_SYSTEM_PROMPT,
        )
        self.assertIn(
            "DELISKY AI Marketing Helper",
            ASK_DELISKY_SYSTEM_PROMPT,
        )
        self.assertIn(
            "do not provide suggestions",
            ASK_DELISKY_SYSTEM_PROMPT,
        )
        self.assertIn(
            "requests for additional data",
            ASK_DELISKY_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Reply briefly",
            ASK_DELISKY_SYSTEM_PROMPT,
        )
        self.assertIn(
            "does not use DELISKY analytical data",
            ASK_DELISKY_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Never claim or imply that Marketing Helper has access to",
            ASK_DELISKY_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Never answer beyond what the supplied analytical context supports",
            ASK_DELISKY_SYSTEM_PROMPT,
        )


class AskDeliskyPlainTextOutputTests(
    SimpleTestCase
):
    def test_system_prompt_requires_plain_text(
        self,
    ):
        self.assertIn(
            "Return plain text only",
            ASK_DELISKY_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Do not use Markdown formatting",
            ASK_DELISKY_SYSTEM_PROMPT,
        )
