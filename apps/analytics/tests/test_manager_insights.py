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
    detect_worker_visit_insights,
    detect_mobility_insights,
)
from apps.analytics.services.truck_operational_status import (
    BrandTruckOperationalState,
    TruckOperationalStatus,
    TruckOperationalStatusResult,
)
from apps.analytics.services.worker_truck_mobility import (
    MobilityTransitionType,
    MobilityWindowMetrics,
    WorkerTruckMobilityComparison,
    WorkerTruckMobilityResult,
)
from apps.analytics.services.worker_performance import (
    PerformanceDataQualitySummary,
    WorkerPerformanceKpi,
    WorkerPerformanceResult,
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


class WorkerVisitInsightDetectorTests(SimpleTestCase):
    def make_worker(
        self,
        worker_id,
        *,
        pos=0,
        visited=0,
        not_visited=0,
    ):
        return WorkerPerformanceKpi(
            worker_id=worker_id,
            total_sales=Decimal("0"),
            sale_record_count=0,
            positive_sale_record_count=0,
            zero_total_record_count=0,
            pos_record_count=pos,
            visited_record_count=visited,
            not_visited_record_count=not_visited,
            unique_client_day_count=pos,
            distinct_brand_client_count=0,
            brand_product_count=0,
            sold_product_count=0,
            not_sold_product_count=0,
            negative_gap_product_count=0,
            sold_without_supply_context_count=0,
        )

    def make_result(self, *workers):
        return WorkerPerformanceResult(
            requested_period_start=date(2026, 7, 1),
            requested_period_end=date(2026, 7, 7),
            brand_id=1,
            workers=tuple(workers),
            operational_states=(),
            data_quality=PerformanceDataQualitySummary(
                sales_attribution_issue_count=0,
                pos_attribution_issue_count=0,
                items_attribution_issue_count=0,
                opening_stock_attribution_issue_count=0,
                chargement_attribution_issue_count=0,
                operational_attribution_issue_count=0,
                pos_numeric_message_warning_count=0,
                pos_duplicate_same_day_warning_count=0,
            ),
        )

    def test_relative_signal_requires_two_measured_workers(self):
        result = self.make_result(
            self.make_worker(
                1,
                pos=10,
                visited=2,
                not_visited=8,
            )
        )

        self.assertEqual(
            detect_worker_visit_insights(
                performance_result=result
            ),
            (),
        )

    def test_worker_above_weighted_team_rate_is_detected(self):
        result = self.make_result(
            self.make_worker(
                1,
                pos=10,
                visited=2,
                not_visited=8,
            ),
            self.make_worker(
                2,
                pos=10,
                visited=8,
                not_visited=2,
            ),
        )

        insight = detect_worker_visit_insights(
            performance_result=result
        )[0]

        self.assertEqual(
            insight.code,
            "WORKER_NON_VISIT_RATE_ABOVE_TEAM",
        )
        self.assertEqual(
            insight.category,
            InsightCategory.VISITS,
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
            evidence["team_non_visit_rate"],
            Decimal("0.5"),
        )
        self.assertEqual(
            evidence["worker_1_non_visit_rate"],
            Decimal("0.8"),
        )

        worker_entities = tuple(
            entity.entity_id
            for entity in insight.entities
            if (
                entity.entity_type
                == InsightEntityType.WORKER
            )
        )

        self.assertEqual(worker_entities, (1,))

    def test_team_rate_is_weighted_by_pos_volume(self):
        result = self.make_result(
            self.make_worker(
                1,
                pos=2,
                visited=0,
                not_visited=2,
            ),
            self.make_worker(
                2,
                pos=18,
                visited=18,
                not_visited=0,
            ),
        )

        insight = detect_worker_visit_insights(
            performance_result=result
        )[0]

        evidence = {
            item.key: item.value
            for item in insight.evidence
        }

        self.assertEqual(
            evidence["team_pos_record_count"],
            20,
        )
        self.assertEqual(
            evidence["team_not_visited_record_count"],
            2,
        )
        self.assertEqual(
            evidence["team_non_visit_rate"],
            Decimal("0.1"),
        )

    def test_equal_team_rates_create_no_attention_signal(self):
        result = self.make_result(
            self.make_worker(
                1,
                pos=10,
                visited=5,
                not_visited=5,
            ),
            self.make_worker(
                2,
                pos=10,
                visited=5,
                not_visited=5,
            ),
        )

        self.assertEqual(
            detect_worker_visit_insights(
                performance_result=result
            ),
            (),
        )

    def test_worker_without_visit_measurement_is_not_failure(self):
        result = self.make_result(
            self.make_worker(1),
            self.make_worker(
                2,
                pos=10,
                visited=5,
                not_visited=5,
            ),
        )

        self.assertEqual(
            detect_worker_visit_insights(
                performance_result=result
            ),
            (),
        )

    def test_multiple_workers_above_team_keep_stable_order(self):
        result = self.make_result(
            self.make_worker(
                1,
                pos=10,
                visited=2,
                not_visited=8,
            ),
            self.make_worker(
                2,
                pos=10,
                visited=4,
                not_visited=6,
            ),
            self.make_worker(
                3,
                pos=10,
                visited=9,
                not_visited=1,
            ),
        )

        insight = detect_worker_visit_insights(
            performance_result=result
        )[0]

        worker_entities = tuple(
            entity.entity_id
            for entity in insight.entities
            if (
                entity.entity_type
                == InsightEntityType.WORKER
            )
        )

        self.assertEqual(worker_entities, (1, 2))


class MobilityInsightDetectorTests(SimpleTestCase):
    def make_window(
        self,
        *,
        worker_id,
        truck_id,
        period_start,
        period_end,
        sales=None,
        sales_days=0,
        pos=None,
        visited=0,
        not_visited=0,
        visit_days=0,
    ):
        has_sales = sales is not None
        has_visits = pos is not None

        return MobilityWindowMetrics(
            brand_id=1,
            worker_id=worker_id,
            truck_id=truck_id,
            period_start=period_start,
            period_end=period_end,
            working_day_count=2,
            sales_measurement_day_count=sales_days,
            visit_measurement_day_count=visit_days,
            sales_total=(
                Decimal(str(sales))
                if has_sales
                else None
            ),
            sale_record_count=(
                sales_days
                if has_sales
                else None
            ),
            positive_sale_record_count=(
                sales_days
                if has_sales
                else None
            ),
            zero_total_record_count=(
                0
                if has_sales
                else None
            ),
            pos_record_count=(
                pos
                if has_visits
                else None
            ),
            visited_record_count=(
                visited
                if has_visits
                else None
            ),
            not_visited_record_count=(
                not_visited
                if has_visits
                else None
            ),
            unique_client_day_count=(
                pos
                if has_visits
                else None
            ),
        )

    def make_worker_move(
        self,
        *,
        before_sales=None,
        after_sales=None,
        before_sales_days=0,
        after_sales_days=0,
        before_pos=None,
        after_pos=None,
        before_visited=0,
        after_visited=0,
        before_not_visited=0,
        after_not_visited=0,
        before_visit_days=0,
        after_visit_days=0,
        gap=0,
    ):
        return WorkerTruckMobilityComparison(
            transition_type=(
                MobilityTransitionType
                .WORKER_CHANGED_TRUCK
            ),
            brand_id=1,
            change_date=date(2026, 7, 4),
            gap_working_day_count=gap,
            before=self.make_window(
                worker_id=10,
                truck_id=20,
                period_start=date(2026, 7, 1),
                period_end=date(2026, 7, 2),
                sales=before_sales,
                sales_days=before_sales_days,
                pos=before_pos,
                visited=before_visited,
                not_visited=before_not_visited,
                visit_days=before_visit_days,
            ),
            after=self.make_window(
                worker_id=10,
                truck_id=21,
                period_start=date(2026, 7, 4),
                period_end=date(2026, 7, 5),
                sales=after_sales,
                sales_days=after_sales_days,
                pos=after_pos,
                visited=after_visited,
                not_visited=after_not_visited,
                visit_days=after_visit_days,
            ),
        )

    def make_truck_seller_change(
        self,
        *,
        before_pos,
        after_pos,
        before_visited,
        after_visited,
    ):
        return WorkerTruckMobilityComparison(
            transition_type=(
                MobilityTransitionType
                .TRUCK_CHANGED_WORKER
            ),
            brand_id=1,
            change_date=date(2026, 7, 4),
            gap_working_day_count=0,
            before=self.make_window(
                worker_id=10,
                truck_id=20,
                period_start=date(2026, 7, 1),
                period_end=date(2026, 7, 2),
                pos=before_pos,
                visited=before_visited,
                not_visited=(
                    before_pos - before_visited
                ),
                visit_days=2,
            ),
            after=self.make_window(
                worker_id=11,
                truck_id=20,
                period_start=date(2026, 7, 4),
                period_end=date(2026, 7, 5),
                pos=after_pos,
                visited=after_visited,
                not_visited=(
                    after_pos - after_visited
                ),
                visit_days=2,
            ),
        )

    def make_result(self, *comparisons):
        return WorkerTruckMobilityResult(
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
            comparisons=tuple(comparisons),
        )

    def test_worker_move_sales_change_emits_high_confidence_signal(
        self,
    ):
        comparison = self.make_worker_move(
            before_sales="100",
            after_sales="160",
            before_sales_days=2,
            after_sales_days=2,
        )

        insight = detect_mobility_insights(
            mobility_result=self.make_result(
                comparison
            )
        )[0]

        self.assertEqual(
            insight.code,
            "WORKER_TRUCK_MOBILITY_SIGNAL",
        )
        self.assertEqual(
            insight.category,
            InsightCategory.MOBILITY,
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
            evidence["sales_total_delta"],
            Decimal("60"),
        )

        entity_types = tuple(
            item.entity_type
            for item in insight.entities
        )

        self.assertEqual(
            entity_types,
            (
                InsightEntityType.BRAND,
                InsightEntityType.WORKER,
                InsightEntityType.TRUCK,
                InsightEntityType.TRUCK,
            ),
        )

    def test_truck_seller_visit_change_emits_signal(self):
        comparison = self.make_truck_seller_change(
            before_pos=4,
            after_pos=4,
            before_visited=2,
            after_visited=3,
        )

        insight = detect_mobility_insights(
            mobility_result=self.make_result(
                comparison
            )
        )[0]

        self.assertEqual(
            insight.code,
            "TRUCK_SELLER_MOBILITY_SIGNAL",
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
            evidence["visit_success_rate_delta"],
            Decimal("0.25"),
        )

        self.assertEqual(
            tuple(
                entity.entity_id
                for entity in insight.entities
                if (
                    entity.entity_type
                    == InsightEntityType.WORKER
                )
            ),
            (10, 11),
        )

    def test_unchanged_results_create_no_signal(self):
        comparison = self.make_worker_move(
            before_sales="100",
            after_sales="100",
            before_sales_days=2,
            after_sales_days=2,
            before_pos=4,
            after_pos=4,
            before_visited=3,
            after_visited=3,
            before_not_visited=1,
            after_not_visited=1,
            before_visit_days=2,
            after_visit_days=2,
        )

        self.assertEqual(
            detect_mobility_insights(
                mobility_result=self.make_result(
                    comparison
                )
            ),
            (),
        )

    def test_coverage_imbalance_lowers_confidence(self):
        comparison = self.make_worker_move(
            before_sales="100",
            after_sales="160",
            before_sales_days=1,
            after_sales_days=2,
        )

        insight = detect_mobility_insights(
            mobility_result=self.make_result(
                comparison
            )
        )[0]

        self.assertEqual(
            insight.confidence,
            InsightConfidence.MEDIUM,
        )

        limitation_codes = {
            item.code
            for item in insight.limitations
        }

        self.assertIn(
            "MOBILITY_MEASUREMENT_COVERAGE_IMBALANCE",
            limitation_codes,
        )

    def test_working_gap_lowers_confidence(self):
        comparison = self.make_worker_move(
            before_sales="100",
            after_sales="160",
            before_sales_days=2,
            after_sales_days=2,
            gap=1,
        )

        insight = detect_mobility_insights(
            mobility_result=self.make_result(
                comparison
            )
        )[0]

        self.assertEqual(
            insight.confidence,
            InsightConfidence.MEDIUM,
        )

        limitation_codes = {
            item.code
            for item in insight.limitations
        }

        self.assertIn(
            "MOBILITY_WORKING_GAP_PRESENT",
            limitation_codes,
        )

    def test_gap_and_incomplete_coverage_are_low_confidence(
        self,
    ):
        comparison = self.make_worker_move(
            before_sales="100",
            after_sales="160",
            before_sales_days=1,
            after_sales_days=2,
            gap=1,
        )

        insight = detect_mobility_insights(
            mobility_result=self.make_result(
                comparison
            )
        )[0]

        self.assertEqual(
            insight.confidence,
            InsightConfidence.LOW,
        )

        limitation_codes = {
            item.code
            for item in insight.limitations
        }

        self.assertIn(
            "MOBILITY_ASSOCIATION_NOT_CAUSATION",
            limitation_codes,
        )
        self.assertIn(
            "MOBILITY_CONTEXT_NOT_CONTROLLED",
            limitation_codes,
        )


    def test_equal_but_incomplete_coverage_lowers_confidence(
        self,
    ):
        comparison = self.make_worker_move(
            before_sales="100",
            after_sales="160",
            before_sales_days=1,
            after_sales_days=1,
        )

        insight = detect_mobility_insights(
            mobility_result=self.make_result(
                comparison
            )
        )[0]

        self.assertEqual(
            insight.confidence,
            InsightConfidence.MEDIUM,
        )

        limitation_codes = {
            item.code
            for item in insight.limitations
        }

        self.assertIn(
            "MOBILITY_INCOMPLETE_MEASUREMENT_COVERAGE",
            limitation_codes,
        )
        self.assertNotIn(
            "MOBILITY_MEASUREMENT_COVERAGE_IMBALANCE",
            limitation_codes,
        )
