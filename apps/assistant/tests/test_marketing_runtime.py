import ast
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.assistant.marketing_helper import (
    MarketingHelperResponse,
)
from apps.assistant.marketing_runtime import (
    ask_marketing_helper,
)
from apps.assistant.marketing_provider_factory import (
    MarketingHelperProviderDisabledError,
)


class FakeMarketingProvider:
    def __init__(self):
        self.request = None

    def generate(self, request):
        self.request = request

        return MarketingHelperResponse(
            answer="Marketing answer",
            provider_name="fake-local",
            model_name="fake-model",
        )


class MarketingRuntimeTests(SimpleTestCase):
    @patch(
        "apps.assistant.marketing_runtime."
        "build_marketing_helper_provider"
    )
    def test_runtime_builds_general_knowledge_request(
        self,
        provider_builder,
    ):
        provider = FakeMarketingProvider()
        provider_builder.return_value = provider

        environ = {
            "ASK_DELISKY_PROVIDER": "local",
        }

        response = ask_marketing_helper(
            question="  Give me promotion ideas  ",
            environ=environ,
        )

        provider_builder.assert_called_once_with(
            environ=environ
        )

        self.assertEqual(
            provider.request.question,
            "Give me promotion ideas",
        )
        self.assertEqual(
            response.answer,
            "Marketing answer",
        )

    @patch(
        "apps.assistant.marketing_runtime."
        "build_marketing_helper_provider"
    )
    def test_disabled_provider_fails_early(
        self,
        provider_builder,
    ):
        provider_builder.side_effect = (
            MarketingHelperProviderDisabledError(
                "disabled"
            )
        )

        with self.assertRaises(
            MarketingHelperProviderDisabledError
        ):
            ask_marketing_helper(
                question="Help",
                environ={},
            )

    def test_runtime_module_has_no_analytics_dependency(
        self
    ):
        import apps.assistant.marketing_runtime as module

        source = Path(
            module.__file__
        ).read_text(
            encoding="utf-8"
        )

        tree = ast.parse(
            source
        )

        imported_modules = set()
        imported_names = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(
                        alias.name
                    )

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.add(
                        node.module
                    )

                for alias in node.names:
                    imported_names.add(
                        alias.name
                    )

        self.assertFalse(
            any(
                module_name == "apps.analytics"
                or module_name.startswith(
                    "apps.analytics."
                )
                for module_name in imported_modules
            )
        )

        self.assertNotIn(
            "AskDeliskyContext",
            imported_names,
        )

        self.assertNotIn(
            "build_manager_insights",
            imported_names,
        )
