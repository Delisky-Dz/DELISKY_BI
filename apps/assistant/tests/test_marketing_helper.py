from django.test import SimpleTestCase

from apps.assistant.marketing_helper import (
    MARKETING_HELPER_SYSTEM_PROMPT,
    MarketingHelperRequest,
    MarketingHelperResponse,
    build_marketing_helper_user_prompt,
)


class MarketingHelperContractTests(
    SimpleTestCase
):
    def test_question_is_trimmed(self):
        request = MarketingHelperRequest(
            question="  Improve sales  "
        )

        self.assertEqual(
            request.question,
            "Improve sales",
        )

    def test_empty_question_is_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            MarketingHelperRequest(
                question="   "
            )

    def test_response_is_normalized(self):
        response = MarketingHelperResponse(
            answer="  Advice  ",
            provider_name=" local ",
            model_name=" qwen3:4b-instruct ",
        )

        self.assertEqual(
            response.answer,
            "Advice",
        )
        self.assertEqual(
            response.provider_name,
            "local",
        )
        self.assertEqual(
            response.model_name,
            "qwen3:4b-instruct",
        )

    def test_user_prompt_contains_no_analytics_context(
        self
    ):
        prompt = build_marketing_helper_user_prompt(
            MarketingHelperRequest(
                question="How can we improve distribution?"
            )
        )

        self.assertIn(
            "How can we improve distribution?",
            prompt,
        )
        self.assertNotIn(
            "ANALYTICAL_CONTEXT_JSON",
            prompt,
        )
        self.assertNotIn(
            "CONTEXT_SCHEMA_VERSION",
            prompt,
        )

    def test_policy_allows_general_commercial_knowledge(
        self
    ):
        self.assertIn(
            "general trained knowledge",
            MARKETING_HELPER_SYSTEM_PROMPT,
        )
        self.assertIn(
            "marketing and trade marketing",
            MARKETING_HELPER_SYSTEM_PROMPT,
        )
        self.assertIn(
            "sales strategy",
            MARKETING_HELPER_SYSTEM_PROMPT,
        )

    def test_policy_forbids_fake_delisky_analysis(
        self
    ):
        self.assertIn(
            "does not receive DELISKY analytical data",
            MARKETING_HELPER_SYSTEM_PROMPT,
        )
        self.assertIn(
            "company-data analysis belongs to Ask DELISKY",
            MARKETING_HELPER_SYSTEM_PROMPT,
        )

    def test_policy_prioritizes_requested_completion(
        self
    ):
        self.assertIn(
            "output exactly that requested set",
            MARKETING_HELPER_SYSTEM_PROMPT,
        )
        self.assertIn(
            "without unnecessary introductions",
            MARKETING_HELPER_SYSTEM_PROMPT,
        )

    def test_policy_prioritizes_compact_complete_plans(
        self
    ):
        self.assertIn(
            "one concise sentence per item",
            MARKETING_HELPER_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Prioritize completing all requested items",
            MARKETING_HELPER_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Do not add an introduction or conclusion",
            MARKETING_HELPER_SYSTEM_PROMPT,
        )

    def test_policy_forbids_fake_live_information(
        self
    ):
        self.assertIn(
            "Do not pretend to have internet access",
            MARKETING_HELPER_SYSTEM_PROMPT,
        )
        self.assertIn(
            "cannot verify it from live sources",
            MARKETING_HELPER_SYSTEM_PROMPT,
        )


class MarketingHelperPlainTextOutputTests(
    SimpleTestCase
):
    def test_policy_requires_plain_text_output(
        self,
    ):
        self.assertIn(
            "Return plain text only",
            MARKETING_HELPER_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Do not use Markdown formatting",
            MARKETING_HELPER_SYSTEM_PROMPT,
        )
