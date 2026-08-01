from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from apps.analytics.services.items_aggregation import (
    ItemMetrics,
    ItemsAggregationResult,
)
from apps.analytics.services.manager_dashboard import (
    build_manager_dashboard,
    combine_manager_dashboard,
)
from apps.analytics.services.pos_visit_aggregation import (
    BrandClientVisitTotal,
    PosVisitAggregationResult,
    VisitMetrics,
)
from apps.analytics.services.product_performance import (
    ProductPerformanceResult,
    ProductQuantityContext,
    TruckProductPerformance,
    WorkerProductPerformance,
)
from apps.analytics.services.sales_aggregation import (
    SalesAggregationResult,
    SalesMetrics,
)
from apps.analytics.services.stock_flow_aggregation import (
    QuantityMetrics,
    StockFlowAggregationResult,
)
from apps.analytics.services.truck_operational_status import (
    BrandTruckOperationalState,
    TruckOperationalStatus,
    TruckOperationalStatusResult,
)
from apps.analytics.services.worker_performance import (
    PerformanceDataQualitySummary,
    WorkerPerformanceKpi,
    WorkerPerformanceResult,
)
from apps.imports.models import ImportReportType


class ManagerDashboardTests(SimpleTestCase):
    period_start = date(2026, 7, 1)
    period_end = date(2026, 7, 7)

    def sales_metrics(
        self,
        total="0",
        *,
        records=0,
        positive=0,
        zero=0,
    ):
        return SalesMetrics(
            total_sales=Decimal(str(total)),
            sale_record_count=records,
            positive_sale_record_count=positive,
            zero_total_record_count=zero,
        )

    def visit_metrics(
        self,
        *,
        total=0,
        visited=0,
        not_visited=0,
        unique_days=0,
    ):
        return VisitMetrics(
            total_record_count=total,
            visited_record_count=visited,
            not_visited_record_count=not_visited,
            unique_client_day_count=unique_days,
        )

    def empty_item_metrics(self):
        return ItemMetrics(
            quantity_sold=Decimal("0"),
            item_record_count=0,
            positive_quantity_record_count=0,
            zero_quantity_record_count=0,
        )

    def empty_quantity_metrics(self):
        return QuantityMetrics(
            total_quantity=Decimal("0"),
            record_count=0,
            positive_quantity_record_count=0,
            zero_quantity_record_count=0,
        )

    def quality(
        self,
        *,
        sales=0,
        pos=0,
        items=0,
        opening=0,
        chargement=0,
        operational=0,
        numeric=0,
        duplicate=0,
    ):
        return PerformanceDataQualitySummary(
            sales_attribution_issue_count=sales,
            pos_attribution_issue_count=pos,
            items_attribution_issue_count=items,
            opening_stock_attribution_issue_count=opening,
            chargement_attribution_issue_count=chargement,
            operational_attribution_issue_count=operational,
            pos_numeric_message_warning_count=numeric,
            pos_duplicate_same_day_warning_count=duplicate,
        )

    def worker_kpi(
        self,
        worker_id,
        *,
        total_sales="0",
        sale_records=0,
        positive_sales=0,
        zero_sales=0,
        pos_records=0,
        visited=0,
        not_visited=0,
        unique_days=0,
        clients=0,
        products=0,
        sold_products=0,
        not_sold_products=0,
        negative_products=0,
        sold_without_supply=0,
    ):
        return WorkerPerformanceKpi(
            worker_id=worker_id,
            total_sales=Decimal(str(total_sales)),
            sale_record_count=sale_records,
            positive_sale_record_count=positive_sales,
            zero_total_record_count=zero_sales,
            pos_record_count=pos_records,
            visited_record_count=visited,
            not_visited_record_count=not_visited,
            unique_client_day_count=unique_days,
            distinct_brand_client_count=clients,
            brand_product_count=products,
            sold_product_count=sold_products,
            not_sold_product_count=not_sold_products,
            negative_gap_product_count=negative_products,
            sold_without_supply_context_count=(
                sold_without_supply
            ),
        )

    def worker_product(
        self,
        *,
        worker_id,
        article,
        normalized,
        opening="0",
        chargement="0",
        sold="0",
        brand_id=1,
    ):
        return WorkerProductPerformance(
            brand_id=brand_id,
            worker_id=worker_id,
            article=article,
            article_normalized=normalized,
            quantities=ProductQuantityContext(
                opening_quantity=Decimal(opening),
                chargement_quantity=Decimal(chargement),
                sold_quantity=Decimal(sold),
            ),
        )

    def truck_product(
        self,
        *,
        truck_id,
        article,
        normalized,
        opening="0",
        chargement="0",
        sold="0",
        brand_id=1,
    ):
        return TruckProductPerformance(
            brand_id=brand_id,
            truck_id=truck_id,
            article=article,
            article_normalized=normalized,
            quantities=ProductQuantityContext(
                opening_quantity=Decimal(opening),
                chargement_quantity=Decimal(chargement),
                sold_quantity=Decimal(sold),
            ),
        )

    def operational_state(
        self,
        truck_id,
        status,
        *,
        brand_id=1,
    ):
        return BrandTruckOperationalState(
            brand_id=brand_id,
            truck_id=truck_id,
            status=status,
            sales_activity_count=(
                1
                if status == TruckOperationalStatus.ACTIVE
                else 0
            ),
            sales_total=Decimal("0"),
            authoritative_stopped_count=(
                1
                if status
                == TruckOperationalStatus.CONFIRMED_STOPPED
                else 0
            ),
            possible_stopped_count=(
                1
                if status
                == TruckOperationalStatus.POSSIBLE_STOPPED
                else 0
            ),
            activity_row_ids=(),
            authoritative_stopped_row_ids=(),
            possible_stopped_row_ids=(),
        )

    def make_sales(
        self,
        *,
        overall=None,
        source=0,
        included=0,
        outside=0,
        period_start=None,
        period_end=None,
    ):
        return SalesAggregationResult(
            requested_period_start=(
                self.period_start
                if period_start is None
                else period_start
            ),
            requested_period_end=(
                self.period_end
                if period_end is None
                else period_end
            ),
            source_row_count=source,
            included_row_count=included,
            outside_requested_period_count=outside,
            overall=overall or self.sales_metrics(),
            by_brand=(),
            by_truck=(),
            by_worker=(),
            by_brand_truck=(),
            by_brand_worker=(),
            by_brand_truck_worker=(),
            attribution_issues=(),
        )

    def make_visits(
        self,
        *,
        overall=None,
        clients=(),
        source=0,
        included=0,
        outside=0,
        numeric_warnings=0,
        duplicate_warnings=0,
        period_start=None,
        period_end=None,
    ):
        return PosVisitAggregationResult(
            requested_period_start=(
                self.period_start
                if period_start is None
                else period_start
            ),
            requested_period_end=(
                self.period_end
                if period_end is None
                else period_end
            ),
            source_row_count=source,
            included_row_count=included,
            outside_requested_period_count=outside,
            numeric_message_warning_count=(
                numeric_warnings
            ),
            duplicate_same_day_warning_count=(
                duplicate_warnings
            ),
            duplicate_same_day_row_ids=(),
            overall=overall or self.visit_metrics(),
            by_brand=(),
            by_truck=(),
            by_worker=(),
            by_brand_truck_worker=(),
            by_brand_client=tuple(clients),
            by_brand_truck_client=(),
            by_brand_worker_client=(),
            attribution_issues=(),
        )

    def make_items(
        self,
        *,
        source=0,
        included=0,
        outside=0,
        partial=0,
        period_start=None,
        period_end=None,
    ):
        return ItemsAggregationResult(
            requested_period_start=(
                self.period_start
                if period_start is None
                else period_start
            ),
            requested_period_end=(
                self.period_end
                if period_end is None
                else period_end
            ),
            source_row_count=source,
            included_row_count=included,
            outside_requested_period_count=outside,
            partial_overlap_excluded_count=partial,
            overall=self.empty_item_metrics(),
            by_brand=(),
            by_truck=(),
            by_worker=(),
            by_brand_product=(),
            by_brand_truck_product=(),
            by_brand_worker_product=(),
            attribution_issues=(),
        )

    def make_stock(
        self,
        report_type,
        *,
        source=0,
        included=0,
        outside=0,
        partial=0,
        period_start=None,
        period_end=None,
    ):
        return StockFlowAggregationResult(
            report_type=report_type,
            requested_period_start=(
                self.period_start
                if period_start is None
                else period_start
            ),
            requested_period_end=(
                self.period_end
                if period_end is None
                else period_end
            ),
            source_row_count=source,
            included_row_count=included,
            outside_requested_period_count=outside,
            partial_overlap_excluded_count=partial,
            overall=self.empty_quantity_metrics(),
            by_brand=(),
            by_truck=(),
            by_worker=(),
            by_brand_product=(),
            by_brand_truck_product=(),
            by_brand_worker_product=(),
            attribution_issues=(),
        )

    def make_products(
        self,
        *,
        workers=(),
        trucks=(),
        period_start=None,
        period_end=None,
    ):
        return ProductPerformanceResult(
            requested_period_start=(
                self.period_start
                if period_start is None
                else period_start
            ),
            requested_period_end=(
                self.period_end
                if period_end is None
                else period_end
            ),
            worker_products=tuple(workers),
            truck_products=tuple(trucks),
            items_attribution_issue_count=0,
            opening_stock_attribution_issue_count=0,
            chargement_attribution_issue_count=0,
        )

    def make_operational(
        self,
        *,
        states=(),
        source=0,
        included=0,
        outside=0,
        partial=0,
        period_start=None,
        period_end=None,
    ):
        return TruckOperationalStatusResult(
            requested_period_start=(
                self.period_start
                if period_start is None
                else period_start
            ),
            requested_period_end=(
                self.period_end
                if period_end is None
                else period_end
            ),
            source_row_count=source,
            included_evidence_row_count=included,
            ignored_accepted_non_sales_count=0,
            outside_requested_period_count=outside,
            partial_overlap_excluded_count=partial,
            states=tuple(states),
            attribution_issues=(),
        )

    def make_worker_performance(
        self,
        *,
        workers=(),
        states=(),
        quality=None,
        period_start=None,
        period_end=None,
    ):
        return WorkerPerformanceResult(
            requested_period_start=(
                self.period_start
                if period_start is None
                else period_start
            ),
            requested_period_end=(
                self.period_end
                if period_end is None
                else period_end
            ),
            brand_id=None,
            workers=tuple(workers),
            operational_states=tuple(states),
            data_quality=quality or self.quality(),
        )

    def combine(
        self,
        *,
        sales=None,
        visits=None,
        items=None,
        opening=None,
        chargement=None,
        products=None,
        operational=None,
        workers=None,
        product_limit=10,
    ):
        return combine_manager_dashboard(
            sales=sales or self.make_sales(),
            visits=visits or self.make_visits(),
            items=items or self.make_items(),
            opening_stock=(
                opening
                or self.make_stock(
                    ImportReportType.OPENING_STOCK
                )
            ),
            chargement=(
                chargement
                or self.make_stock(
                    ImportReportType.CHARGEMENT
                )
            ),
            products=products or self.make_products(),
            operational=(
                operational
                or self.make_operational()
            ),
            worker_performance=(
                workers
                or self.make_worker_performance()
            ),
            product_limit=product_limit,
        )

    def test_builds_manager_summary(self):
        sales = self.make_sales(
            overall=self.sales_metrics(
                "1000",
                records=4,
                positive=3,
                zero=1,
            ),
        )

        clients = (
            BrandClientVisitTotal(
                brand_id=1,
                client="Client A",
                client_normalized="client a",
                metrics=self.visit_metrics(
                    total=2,
                    visited=2,
                    unique_days=2,
                ),
            ),
            BrandClientVisitTotal(
                brand_id=1,
                client="Client B",
                client_normalized="client b",
                metrics=self.visit_metrics(
                    total=3,
                    visited=2,
                    not_visited=1,
                    unique_days=3,
                ),
            ),
        )

        visits = self.make_visits(
            overall=self.visit_metrics(
                total=5,
                visited=4,
                not_visited=1,
                unique_days=5,
            ),
            clients=clients,
        )

        products = self.make_products(
            workers=(
                self.worker_product(
                    worker_id=10,
                    article="Unsold Worker Product",
                    normalized="unsold worker product",
                    opening="10",
                ),
                self.worker_product(
                    worker_id=10,
                    article="Negative Worker Product",
                    normalized="negative worker product",
                    sold="3",
                ),
            ),
            trucks=(
                self.truck_product(
                    truck_id=20,
                    article="Unsold Truck Product",
                    normalized="unsold truck product",
                    chargement="8",
                ),
                self.truck_product(
                    truck_id=20,
                    article="Negative Truck Product",
                    normalized="negative truck product",
                    sold="2",
                ),
            ),
        )

        states = (
            self.operational_state(
                1,
                TruckOperationalStatus.CONFIRMED_STOPPED,
            ),
            self.operational_state(
                2,
                TruckOperationalStatus.POSSIBLE_STOPPED,
            ),
            self.operational_state(
                3,
                TruckOperationalStatus.CONFLICTING_EVIDENCE,
            ),
        )

        worker_performance = self.make_worker_performance(
            workers=(
                self.worker_kpi(
                    10,
                    total_sales="1000",
                    sale_records=4,
                    positive_sales=3,
                    zero_sales=1,
                ),
                self.worker_kpi(
                    11,
                    pos_records=1,
                    visited=1,
                ),
            ),
            states=states,
        )

        result = self.combine(
            sales=sales,
            visits=visits,
            products=products,
            operational=self.make_operational(
                states=states,
            ),
            workers=worker_performance,
        )

        summary = result.summary

        self.assertEqual(
            summary.total_sales,
            Decimal("1000"),
        )
        self.assertEqual(
            summary.average_sale_value,
            Decimal("250"),
        )
        self.assertEqual(
            summary.average_positive_sale_value,
            Decimal("1000") / Decimal("3"),
        )
        self.assertEqual(
            summary.visit_success_rate,
            Decimal("0.8"),
        )
        self.assertEqual(
            summary.non_visit_rate,
            Decimal("0.2"),
        )
        self.assertEqual(
            summary.distinct_brand_client_count,
            2,
        )
        self.assertEqual(summary.worker_count, 2)
        self.assertEqual(
            summary.measured_sales_worker_count,
            1,
        )
        self.assertEqual(
            summary.worker_not_sold_product_count,
            1,
        )
        self.assertEqual(
            summary.truck_not_sold_product_count,
            1,
        )
        self.assertEqual(
            summary.worker_negative_gap_product_count,
            1,
        )
        self.assertEqual(
            summary.truck_negative_gap_product_count,
            1,
        )
        self.assertEqual(
            summary.confirmed_stopped_truck_count,
            1,
        )
        self.assertEqual(
            summary.possible_stopped_truck_count,
            1,
        )
        self.assertEqual(
            summary.conflicting_truck_state_count,
            1,
        )

    def test_builds_worker_product_cards(self):
        products = self.make_products(
            workers=(
                self.worker_product(
                    worker_id=10,
                    article="Unsold Large",
                    normalized="unsold large",
                    opening="20",
                ),
                self.worker_product(
                    worker_id=10,
                    article="Sold Two",
                    normalized="sold two",
                    chargement="10",
                    sold="2",
                ),
                self.worker_product(
                    worker_id=10,
                    article="Sold Five",
                    normalized="sold five",
                    chargement="10",
                    sold="5",
                ),
                self.worker_product(
                    worker_id=10,
                    article="No Supply",
                    normalized="no supply",
                    sold="3",
                ),
            ),
        )

        workers = self.make_worker_performance(
            workers=(
                self.worker_kpi(
                    10,
                    products=4,
                    sold_products=3,
                    not_sold_products=1,
                    negative_products=1,
                    sold_without_supply=1,
                ),
            ),
        )

        result = self.combine(
            products=products,
            workers=workers,
            product_limit=2,
        )

        card = result.worker_card(10)

        self.assertIsNotNone(card)
        self.assertEqual(card.worker_id, 10)
        self.assertEqual(
            [
                item.article_normalized
                for item in card.not_sold_products
            ],
            ["unsold large"],
        )
        self.assertEqual(
            [
                item.article_normalized
                for item in card.least_sold_products
            ],
            ["sold two", "no supply"],
        )
        self.assertEqual(
            [
                item.article_normalized
                for item in card.negative_gap_products
            ],
            ["no supply"],
        )
        self.assertEqual(
            [
                item.article_normalized
                for item
                in card.sold_without_supply_context_products
            ],
            ["no supply"],
        )
        self.assertTrue(
            card.has_product_attention_items
        )
        self.assertIsNone(
            result.worker_card(999)
        )

    def test_product_limit_is_applied_and_validated(self):
        products = self.make_products(
            workers=tuple(
                self.worker_product(
                    worker_id=10,
                    article=f"Unsold {number}",
                    normalized=f"unsold {number}",
                    opening=str(number),
                )
                for number in range(1, 5)
            ),
        )

        workers = self.make_worker_performance(
            workers=(
                self.worker_kpi(
                    10,
                    products=4,
                    not_sold_products=4,
                ),
            ),
        )

        result = self.combine(
            products=products,
            workers=workers,
            product_limit=2,
        )

        self.assertEqual(
            len(
                result.worker_cards[0]
                .not_sold_products
            ),
            2,
        )

        with self.assertRaisesRegex(
            ValueError,
            "product_limit cannot be negative",
        ):
            self.combine(product_limit=-1)

    def test_coverage_summary_preserves_exclusions(self):
        result = self.combine(
            sales=self.make_sales(
                source=10,
                included=8,
                outside=2,
            ),
            visits=self.make_visits(
                source=9,
                included=7,
                outside=2,
            ),
            items=self.make_items(
                source=8,
                included=5,
                outside=1,
                partial=2,
            ),
            opening=self.make_stock(
                ImportReportType.OPENING_STOCK,
                source=4,
                included=2,
                outside=1,
                partial=1,
            ),
            chargement=self.make_stock(
                ImportReportType.CHARGEMENT,
                source=7,
                included=4,
                outside=1,
                partial=2,
            ),
            operational=self.make_operational(
                source=6,
                included=3,
                outside=1,
                partial=2,
            ),
        )

        coverage = result.coverage

        self.assertEqual(
            coverage.period_excluded_row_count,
            15,
        )
        self.assertTrue(
            coverage.has_partial_period_exclusions
        )
        self.assertEqual(
            coverage.sales_source_row_count,
            10,
        )
        self.assertEqual(
            coverage.chargement_included_row_count,
            4,
        )

    def test_data_quality_is_passed_through(self):
        quality = self.quality(
            sales=1,
            pos=2,
            items=3,
            opening=4,
            chargement=5,
            operational=6,
            numeric=7,
            duplicate=8,
        )

        result = self.combine(
            workers=self.make_worker_performance(
                quality=quality,
            ),
        )

        self.assertIs(
            result.data_quality,
            quality,
        )
        self.assertEqual(
            result.data_quality.attribution_issue_count,
            21,
        )
        self.assertEqual(
            result.data_quality.warning_count,
            15,
        )

    def test_dashboard_delegates_worker_rankings(self):
        workers = self.make_worker_performance(
            workers=(
                self.worker_kpi(
                    1,
                    total_sales="500",
                    sale_records=2,
                    positive_sales=2,
                    pos_records=10,
                    visited=9,
                    not_visited=1,
                ),
                self.worker_kpi(
                    2,
                    total_sales="100",
                    sale_records=1,
                    positive_sales=1,
                    pos_records=10,
                    visited=5,
                    not_visited=5,
                ),
            ),
        )

        result = self.combine(workers=workers)

        self.assertEqual(
            [
                item.worker_id
                for item in result.top_sales_workers()
            ],
            [1, 2],
        )
        self.assertEqual(
            [
                item.worker_id
                for item in result.lowest_sales_workers()
            ],
            [2, 1],
        )
        self.assertEqual(
            [
                item.worker_id
                for item
                in result.highest_non_visit_rate_workers()
            ],
            [2, 1],
        )

    def test_empty_summary_rates_are_none(self):
        result = self.combine()

        self.assertIsNone(
            result.summary.average_sale_value
        )
        self.assertIsNone(
            result.summary
            .average_positive_sale_value
        )
        self.assertIsNone(
            result.summary.visit_success_rate
        )
        self.assertIsNone(
            result.summary.non_visit_rate
        )

    def test_mismatched_periods_are_rejected(self):
        visits = self.make_visits(
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
        )

        with self.assertRaisesRegex(
            ValueError,
            "same requested period",
        ):
            self.combine(visits=visits)

    def test_invalid_build_arguments_are_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "period_end cannot be before period_start",
        ):
            build_manager_dashboard(
                period_start=date(2026, 7, 10),
                period_end=date(2026, 7, 1),
            )

        with self.assertRaisesRegex(
            ValueError,
            "product_limit cannot be negative",
        ):
            build_manager_dashboard(
                product_limit=-1,
            )
