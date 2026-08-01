import json
from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from apps.analytics.services.ask_delisky_context import (
    build_ask_delisky_context,
)
from apps.analytics.services.manager_insights import (
    InsightCategory,
    InsightConfidence,
    InsightEvidence,
    InsightSeverity,
    ManagerInsight,
)
from apps.analytics.services.manager_insights_orchestrator import (
    ManagerInsightsResult,
)
from apps.assistant.contracts import (
    AskDeliskyProviderResult,
    AskDeliskyRequest,
)
from apps.assistant.service import ask_delisky


class FakeProvider:
    def __init__(self):
        self.request = None

    def generate(self, request):
        self.request = request

        return AskDeliskyProviderResult(
            answer="  تحليل DELISKY جاهز.  ",
            provider_name="  fake-provider  ",
            model_name="  fake-model  ",
        )


class AskDeliskyServiceTests(SimpleTestCase):
    def make_context(self):
        insight = ManagerInsight(
            code="TEST_SIGNAL",
            category=InsightCategory.MOBILITY,
            severity=InsightSeverity.ATTENTION,
            confidence=InsightConfidence.HIGH,
            title="Test title",
            summary="Test summary",
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
            evidence=(
                InsightEvidence(
                    key="sales_delta",
                    label="Sales delta",
                    value=Decimal("25.50"),
                    source=(
                        "internal.analytics."
                        "private.source.path"
                    ),
                    unit="DZD",
                ),
            ),
        )

        result = ManagerInsightsResult(
            requested_period_start=date(2026, 7, 1),
            requested_period_end=date(2026, 7, 7),
            brand_id=1,
            insights=(insight,),
        )

        return build_ask_delisky_context(
            insights_result=result
        )

    def test_invalid_context_type_is_rejected(self):
        with self.assertRaisesRegex(
            TypeError,
            "context must be an AskDeliskyContext",
        ):
            AskDeliskyRequest(
                question="test",
                context=object(),
            )

    def test_empty_question_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "question cannot be empty",
        ):
            AskDeliskyRequest(
                question="   ",
                context=self.make_context(),
            )

    def test_question_is_trimmed_before_provider(self):
        provider = FakeProvider()

        ask_delisky(
            request=AskDeliskyRequest(
                question="  ما هي أهم الملاحظات؟  ",
                context=self.make_context(),
            ),
            provider=provider,
        )

        self.assertEqual(
            provider.request.question,
            "ما هي أهم الملاحظات؟",
        )

    def test_provider_receives_safe_json_only(self):
        provider = FakeProvider()
        context = self.make_context()

        ask_delisky(
            request=AskDeliskyRequest(
                question="حلل النتائج",
                context=context,
            ),
            provider=provider,
        )

        payload = json.loads(
            provider.request.context_json
        )

        self.assertEqual(
            payload,
            context.to_payload(),
        )

        self.assertNotIn(
            "private.source.path",
            provider.request.context_json,
        )
        self.assertNotIn(
            '"source"',
            provider.request.context_json,
        )

    def test_provider_receives_schema_version(self):
        provider = FakeProvider()
        context = self.make_context()

        ask_delisky(
            request=AskDeliskyRequest(
                question="حلل النتائج",
                context=context,
            ),
            provider=provider,
        )

        self.assertEqual(
            provider.request.context_schema_version,
            "1",
        )

    def test_response_preserves_provider_metadata(self):
        provider = FakeProvider()

        response = ask_delisky(
            request=AskDeliskyRequest(
                question="حلل النتائج",
                context=self.make_context(),
            ),
            provider=provider,
        )

        self.assertEqual(
            response.answer,
            "تحليل DELISKY جاهز.",
        )
        self.assertEqual(
            response.provider_name,
            "fake-provider",
        )
        self.assertEqual(
            response.model_name,
            "fake-model",
        )
        self.assertEqual(
            response.context_schema_version,
            "1",
        )

    def test_empty_provider_answer_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "answer cannot be empty",
        ):
            AskDeliskyProviderResult(
                answer="   ",
                provider_name="fake",
            )

    def test_empty_provider_name_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "Provider name cannot be empty",
        ):
            AskDeliskyProviderResult(
                answer="answer",
                provider_name="   ",
            )
