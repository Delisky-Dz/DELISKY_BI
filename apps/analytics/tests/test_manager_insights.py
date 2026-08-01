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
    detect_data_quality_insights,
    detect_operational_insights,
)
from apps.analytics.services.truck_operational_status import (
    BrandTruckOperationalState,
    TruckOperationalStatus,
    TruckOperationalStatusResult,
)
from apps.analytics.services.worker_performance import (
    PerformanceDataQualitySummary,
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


class DataQualityInsightDetectorTests(SimpleTestCase):
    def make_data_quality(
        self,
        *,
        sales=0,
        pos=0,
        items=0,
        opening=0,
        chargement=0,
        operational=0,
        numeric=0,
        duplicates=0,
    ):
        return PerformanceDataQualitySummary(
            sales_attribution_issue_count=sales,
            pos_attribution_issue_count=pos,
            items_attribution_issue_count=items,
            opening_stock_attribution_issue_count=opening,
            chargement_attribution_issue_count=chargement,
            operational_attribution_issue_count=operational,
            pos_numeric_message_warning_count=numeric,
            pos_duplicate_same_day_warning_count=duplicates,
        )

    def test_invalid_period_is_rejected_even_with_clean_data(self):
        with self.assertRaisesRegex(
            ValueError,
            "period_end cannot be before period_start",
        ):
            detect_data_quality_insights(
                data_quality=self.make_data_quality(),
                period_start=date(2026, 7, 10),
                period_end=date(2026, 7, 1),
            )

    def test_clean_data_returns_no_insights(self):
        insights = detect_data_quality_insights(
            data_quality=self.make_data_quality(),
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
        )

        self.assertEqual(insights, ())

    def test_attribution_issues_create_grounded_warning(self):
        insights = detect_data_quality_insights(
            data_quality=self.make_data_quality(
                sales=3,
                pos=2,
            ),
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
        )

        self.assertEqual(len(insights), 1)

        insight = insights[0]

        self.assertEqual(
            insight.code,
            "DATA_ATTRIBUTION_ISSUES",
        )
        self.assertEqual(
            insight.severity,
            InsightSeverity.WARNING,
        )
        self.assertEqual(
            insight.confidence,
            InsightConfidence.HIGH,
        )

        evidence = {
            item.key: item.value
            for item in insight.evidence
        }

        self.assertEqual(
            evidence,
            {
                "sales_attribution_issues": 3,
                "pos_attribution_issues": 2,
            },
        )

        self.assertEqual(
            insight.limitations[0].code,
            "ATTRIBUTION_NOT_PERFORMANCE_FAILURE",
        )

    def test_all_attribution_sources_are_preserved(self):
        insights = detect_data_quality_insights(
            data_quality=self.make_data_quality(
                sales=1,
                pos=2,
                items=3,
                opening=4,
                chargement=5,
                operational=6,
            ),
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
        )

        self.assertEqual(len(insights), 1)

        evidence = {
            item.key: item.value
            for item in insights[0].evidence
        }

        self.assertEqual(
            evidence,
            {
                "sales_attribution_issues": 1,
                "pos_attribution_issues": 2,
                "items_attribution_issues": 3,
                "opening_stock_attribution_issues": 4,
                "chargement_attribution_issues": 5,
                "operational_attribution_issues": 6,
            },
        )

    def test_pos_warnings_are_not_reclassified_as_failures(self):
        insights = detect_data_quality_insights(
            data_quality=self.make_data_quality(
                numeric=4,
                duplicates=2,
            ),
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
        )

        self.assertEqual(len(insights), 1)

        insight = insights[0]

        self.assertEqual(
            insight.code,
            "POS_DATA_WARNINGS",
        )
        self.assertEqual(
            insight.severity,
            InsightSeverity.ATTENTION,
        )
        self.assertEqual(
            insight.confidence,
            InsightConfidence.HIGH,
        )

        evidence = {
            item.key: item.value
            for item in insight.evidence
        }

        self.assertEqual(
            evidence,
            {
                "pos_numeric_message_warnings": 4,
                "pos_duplicate_same_day_warnings": 2,
            },
        )

        self.assertEqual(
            insight.limitations[0].code,
            "POS_WARNING_NOT_AUTOMATIC_EXCLUSION",
        )

    def test_attribution_and_pos_warnings_keep_stable_order(self):
        insights = detect_data_quality_insights(
            data_quality=self.make_data_quality(
                items=1,
                duplicates=1,
            ),
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
        )

        self.assertEqual(
            tuple(item.code for item in insights),
            (
                "DATA_ATTRIBUTION_ISSUES",
                "POS_DATA_WARNINGS",
            ),
        )

        for insight in insights:
            self.assertEqual(
                insight.period_start,
                date(2026, 7, 1),
            )
            self.assertEqual(
                insight.period_end,
                date(2026, 7, 7),
            )

            for evidence in insight.evidence:
                self.assertEqual(
                    evidence.period_start,
                    date(2026, 7, 1),
                )
                self.assertEqual(
                    evidence.period_end,
                    date(2026, 7, 7),
                )


class OperationalInsightDetectorTests(SimpleTestCase):
    def make_result(self, *states):
        return TruckOperationalStatusResult(
            requested_period_start=date(2026, 7, 1),
            requested_period_end=date(2026, 7, 7),
            source_row_count=0,
            included_evidence_row_count=0,
            ignored_accepted_non_sales_count=0,
            outside_requested_period_count=0,
            partial_overlap_excluded_count=0,
            states=tuple(states),
            attribution_issues=(),
        )

    def make_state(
        self,
        *,
        truck_id,
        status,
        sales_activity=0,
        sales_total=Decimal("0"),
        authoritative=0,
        possible=0,
    ):
        return BrandTruckOperationalState(
            brand_id=1,
            truck_id=truck_id,
            status=status,
            sales_activity_count=sales_activity,
            sales_total=sales_total,
            authoritative_stopped_count=authoritative,
            possible_stopped_count=possible,
            activity_row_ids=(),
            authoritative_stopped_row_ids=(),
            possible_stopped_row_ids=(),
        )

    def test_active_truck_produces_no_attention_insight(self):
        result = self.make_result(
            self.make_state(
                truck_id=1,
                status=TruckOperationalStatus.ACTIVE,
                sales_activity=2,
                sales_total=Decimal("50000"),
            )
        )

        self.assertEqual(
            detect_operational_insights(
                operational_result=result
            ),
            (),
        )

    def test_confirmed_stopped_truck_is_high_confidence(self):
        result = self.make_result(
            self.make_state(
                truck_id=2,
                status=(
                    TruckOperationalStatus.CONFIRMED_STOPPED
                ),
                authoritative=1,
            )
        )

        insight = detect_operational_insights(
            operational_result=result
        )[0]

        self.assertEqual(
            insight.code,
            "TRUCK_CONFIRMED_STOPPED",
        )
        self.assertEqual(
            insight.confidence,
            InsightConfidence.HIGH,
        )
        self.assertEqual(
            insight.entities[1].entity_id,
            2,
        )

    def test_possible_stop_is_not_presented_as_confirmed(self):
        result = self.make_result(
            self.make_state(
                truck_id=3,
                status=(
                    TruckOperationalStatus.POSSIBLE_STOPPED
                ),
                possible=2,
            )
        )

        insight = detect_operational_insights(
            operational_result=result
        )[0]

        self.assertEqual(
            insight.code,
            "TRUCK_POSSIBLE_STOPPED",
        )
        self.assertEqual(
            insight.severity,
            InsightSeverity.ATTENTION,
        )
        self.assertEqual(
            insight.confidence,
            InsightConfidence.MEDIUM,
        )

    def test_conflicting_evidence_is_preserved(self):
        result = self.make_result(
            self.make_state(
                truck_id=4,
                status=(
                    TruckOperationalStatus.CONFLICTING_EVIDENCE
                ),
                sales_activity=1,
                sales_total=Decimal("25000"),
                authoritative=1,
            )
        )

        insight = detect_operational_insights(
            operational_result=result
        )[0]

        self.assertEqual(
            insight.code,
            "TRUCK_OPERATIONAL_CONFLICT",
        )

        limitation_codes = {
            item.code
            for item in insight.limitations
        }

        self.assertEqual(
            limitation_codes,
            {
                "TRUCK_STATUS_NOT_WORKER_FAILURE",
                "CONFLICTING_OPERATIONAL_EVIDENCE",
            },
        )

    def test_non_active_states_keep_stable_order(self):
        result = self.make_result(
            self.make_state(
                truck_id=5,
                status=(
                    TruckOperationalStatus.POSSIBLE_STOPPED
                ),
                possible=1,
            ),
            self.make_state(
                truck_id=6,
                status=(
                    TruckOperationalStatus.CONFIRMED_STOPPED
                ),
                authoritative=1,
            ),
        )

        insights = detect_operational_insights(
            operational_result=result
        )

        self.assertEqual(
            tuple(item.entities[1].entity_id for item in insights),
            (5, 6),
        )
