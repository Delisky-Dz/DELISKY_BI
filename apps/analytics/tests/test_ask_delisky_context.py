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
    InsightEntityRef,
    InsightEntityType,
    InsightEvidence,
    InsightLimitation,
    InsightSeverity,
    ManagerInsight,
)
from apps.analytics.services.manager_insights_orchestrator import (
    ManagerInsightsResult,
)


class AskDeliskyContextTests(SimpleTestCase):
    def make_insight(
        self,
        *,
        code="TEST_SIGNAL",
        value=Decimal("123.450"),
        entity_id=10,
    ):
        return ManagerInsight(
            code=code,
            category=InsightCategory.MOBILITY,
            severity=InsightSeverity.ATTENTION,
            confidence=InsightConfidence.MEDIUM,
            title="Test title",
            summary="Test summary",
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
            evidence=(
                InsightEvidence(
                    key="sales_delta",
                    label="Sales delta",
                    value=value,
                    source=(
                        "internal.analytics."
                        "private.source.path"
                    ),
                    unit="DZD",
                    period_start=date(2026, 7, 1),
                    period_end=date(2026, 7, 7),
                ),
            ),
            entities=(
                InsightEntityRef(
                    entity_type=(
                        InsightEntityType.WORKER
                    ),
                    entity_id=entity_id,
                    label="Worker 10",
                ),
            ),
            limitations=(
                InsightLimitation(
                    code="NOT_CAUSAL",
                    message=(
                        "Association does not prove causation."
                    ),
                ),
            ),
        )

    def make_result(self, *insights):
        return ManagerInsightsResult(
            requested_period_start=date(2026, 7, 1),
            requested_period_end=date(2026, 7, 7),
            brand_id=1,
            insights=tuple(insights),
        )

    def test_context_contains_only_safe_insight_contract(self):
        context = build_ask_delisky_context(
            insights_result=self.make_result(
                self.make_insight()
            )
        )

        payload = context.to_payload()

        self.assertEqual(
            payload["schema_version"],
            "1",
        )
        self.assertEqual(
            payload["scope"],
            {
                "period_start": "2026-07-01",
                "period_end": "2026-07-07",
                "brand_id": 1,
            },
        )

        insight = payload["insights"][0]

        self.assertEqual(
            insight["code"],
            "TEST_SIGNAL",
        )
        self.assertEqual(
            insight["category"],
            "MOBILITY",
        )
        self.assertEqual(
            insight["severity"],
            "ATTENTION",
        )
        self.assertEqual(
            insight["confidence"],
            "MEDIUM",
        )

    def test_decimal_values_are_serialized_without_float_loss(
        self,
    ):
        context = build_ask_delisky_context(
            insights_result=self.make_result(
                self.make_insight(
                    value=Decimal("123.450"),
                )
            )
        )

        evidence = (
            context.to_payload()
            ["insights"][0]
            ["evidence"][0]
        )

        self.assertEqual(
            evidence["value"],
            "123.450",
        )

    def test_internal_evidence_source_is_not_exposed(self):
        context = build_ask_delisky_context(
            insights_result=self.make_result(
                self.make_insight()
            )
        )

        serialized = json.dumps(
            context.to_payload(),
            ensure_ascii=False,
        )

        self.assertNotIn(
            "private.source.path",
            serialized,
        )
        self.assertNotIn(
            '"source"',
            serialized,
        )

    def test_payload_is_json_serializable(self):
        context = build_ask_delisky_context(
            insights_result=self.make_result(
                self.make_insight()
            )
        )

        serialized = json.dumps(
            context.to_payload(),
            ensure_ascii=False,
        )

        self.assertIsInstance(
            serialized,
            str,
        )

    def test_insight_order_is_preserved(self):
        context = build_ask_delisky_context(
            insights_result=self.make_result(
                self.make_insight(
                    code="FIRST",
                ),
                self.make_insight(
                    code="SECOND",
                ),
            )
        )

        self.assertEqual(
            tuple(
                insight.code
                for insight in context.insights
            ),
            (
                "FIRST",
                "SECOND",
            ),
        )

    def test_empty_insights_create_valid_empty_context(self):
        context = build_ask_delisky_context(
            insights_result=self.make_result()
        )

        self.assertFalse(context.has_insights)
        self.assertEqual(
            context.insight_count,
            0,
        )
        self.assertEqual(
            context.to_payload()["insights"],
            [],
        )


    def test_invalid_entity_id_is_rejected(self):
        for invalid_id in (
            True,
            object(),
        ):
            with self.subTest(
                invalid_id=invalid_id
            ):
                with self.assertRaises(TypeError):
                    build_ask_delisky_context(
                        insights_result=self.make_result(
                            self.make_insight(
                                entity_id=invalid_id,
                            )
                        )
                    )

    def test_invalid_brand_id_is_rejected(self):
        result = self.make_result(
            self.make_insight()
        )

        invalid_result = ManagerInsightsResult(
            requested_period_start=(
                result.requested_period_start
            ),
            requested_period_end=(
                result.requested_period_end
            ),
            brand_id=True,
            insights=result.insights,
        )

        with self.assertRaisesRegex(
            TypeError,
            "brand_id must be an integer",
        ):
            build_ask_delisky_context(
                insights_result=invalid_result
            )
