from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

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


class ManagerInsightContractTests(SimpleTestCase):
    def make_evidence(self):
        return InsightEvidence(
            key="total_sales",
            label="إجمالي المبيعات",
            value=Decimal("125000.50"),
            source="sales_aggregation.by_worker",
            unit="DZD",
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
        )

    def test_manager_insight_preserves_grounded_contract(self):
        evidence = self.make_evidence()

        limitation = InsightLimitation(
            code="PARTIAL_ATTRIBUTION",
            message=(
                "بعض السجلات لم يمكن إسنادها "
                "إلى بائع بثقة."
            ),
        )

        worker = InsightEntityRef(
            entity_type=InsightEntityType.WORKER,
            entity_id=17,
            label="البائع أ",
        )

        insight = ManagerInsight(
            code="WORKER_SALES_ATTENTION",
            category=InsightCategory.SALES,
            severity=InsightSeverity.ATTENTION,
            confidence=InsightConfidence.MEDIUM,
            title="مبيعات تحتاج متابعة",
            summary=(
                "ظهرت إشارة تستحق المتابعة "
                "في مبيعات البائع."
            ),
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
            evidence=(evidence,),
            entities=(worker,),
            limitations=(limitation,),
        )

        self.assertEqual(
            insight.evidence,
            (evidence,),
        )
        self.assertEqual(
            insight.entities,
            (worker,),
        )
        self.assertTrue(
            insight.has_limitations
        )

    def test_severity_and_confidence_are_independent(self):
        insight = ManagerInsight(
            code="HIGH_IMPACT_LOW_CONFIDENCE",
            category=InsightCategory.DATA_QUALITY,
            severity=InsightSeverity.CRITICAL,
            confidence=InsightConfidence.LOW,
            title="تنبيه مهم مع دليل محدود",
            summary=(
                "الأثر المحتمل مهم لكن جودة "
                "الدليل لا تسمح بحكم قوي."
            ),
            period_start=None,
            period_end=None,
            evidence=(self.make_evidence(),),
        )

        self.assertEqual(
            insight.severity,
            InsightSeverity.CRITICAL,
        )
        self.assertEqual(
            insight.confidence,
            InsightConfidence.LOW,
        )

    def test_insight_without_evidence_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "must contain evidence",
        ):
            ManagerInsight(
                code="UNGROUNDED",
                category=InsightCategory.SALES,
                severity=InsightSeverity.INFO,
                confidence=InsightConfidence.LOW,
                title="بدون دليل",
                summary="هذا يجب رفضه.",
                period_start=None,
                period_end=None,
                evidence=(),
            )

    def test_invalid_insight_period_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "period_end cannot be before period_start",
        ):
            ManagerInsight(
                code="INVALID_PERIOD",
                category=InsightCategory.VISITS,
                severity=InsightSeverity.WARNING,
                confidence=InsightConfidence.HIGH,
                title="فترة غير صحيحة",
                summary="اختبار حماية الفترة.",
                period_start=date(2026, 7, 10),
                period_end=date(2026, 7, 1),
                evidence=(self.make_evidence(),),
            )

    def test_invalid_evidence_period_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "evidence period_end cannot be before",
        ):
            InsightEvidence(
                key="visit_rate",
                label="نسبة نجاح الزيارة",
                value=Decimal("0.75"),
                source="pos_visit_aggregation.by_worker",
                period_start=date(2026, 7, 10),
                period_end=date(2026, 7, 1),
            )

    def test_empty_machine_identifiers_are_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "evidence key cannot be empty",
        ):
            InsightEvidence(
                key=" ",
                label="مقياس",
                value=1,
                source="test",
            )

        with self.assertRaisesRegex(
            ValueError,
            "entity_id cannot be empty",
        ):
            InsightEntityRef(
                entity_type=InsightEntityType.CLIENT,
                entity_id=" ",
            )
