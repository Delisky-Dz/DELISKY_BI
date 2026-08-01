from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from apps.analytics.services.pos_visit_aggregation import (
    BrandWorkerClientVisitTotal,
    PosVisitAggregationResult,
    VisitMetrics,
    WorkerVisitTotal,
)
from apps.analytics.services.product_performance import (
    ProductPerformanceResult,
    ProductQuantityContext,
    WorkerProductPerformance,
)
from apps.analytics.services.sales_aggregation import (
    SalesAggregationResult,
    SalesMetrics,
    WorkerSalesTotal,
)
from apps.analytics.services.truck_operational_status import (
    BrandTruckOperationalState,
    TruckOperationalStatus,
    TruckOperationalStatusResult,
)
from apps.analytics.services.worker_performance import (
    calculate_worker_performance,
    combine_worker_performance,
)


class WorkerPerformanceTests(SimpleTestCase):
    period_start = date(2026, 7, 1)
    period_end = date(2026, 7, 7)

    def sales_metrics(
        self,
        total,
        *,
        records,
        positive,
        zero,
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
        total,
        visited,
        not_visited,
        unique_days,
    ):
        return VisitMetrics(
            total_record_count=total,
            visited_record_count=visited,
            not_visited_record_count=not_visited,
            unique_client_day_count=unique_days,
        )

    def make_sales_result(
        self,
        *,
        workers=(),
        issues=(),
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
            source_row_count=0,
            included_row_count=0,
            outside_requested_period_count=0,
            overall=self.sales_metrics(
                "0",
                records=0,
                positive=0,
                zero=0,
            ),
            by_brand=(),
            by_truck=(),
            by_worker=tuple(workers),
            by_brand_truck=(),
            by_brand_worker=(),
            by_brand_truck_worker=(),
            attribution_issues=tuple(issues),
        )

    def make_pos_result(
        self,
        *,
        workers=(),
        worker_clients=(),
        issues=(),
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
            source_row_count=0,
            included_row_count=0,
            outside_requested_period_count=0,
            numeric_message_warning_count=(
                numeric_warnings
            ),
            duplicate_same_day_warning_count=(
                duplicate_warnings
            ),
            duplicate_same_day_row_ids=(),
            overall=self.visit_metrics(
                total=0,
                visited=0,
                not_visited=0,
                unique_days=0,
            ),
            by_brand=(),
            by_truck=(),
            by_worker=tuple(workers),
            by_brand_truck_worker=(),
            by_brand_client=(),
            by_brand_truck_client=(),
            by_brand_worker_client=tuple(
                worker_clients
            ),
            attribution_issues=tuple(issues),
        )

    def make_product_result(
        self,
        *,
        workers=(),
        items_issues=0,
        opening_issues=0,
        chargement_issues=0,
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
            truck_products=(),
            items_attribution_issue_count=(
                items_issues
            ),
            opening_stock_attribution_issue_count=(
                opening_issues
            ),
            chargement_attribution_issue_count=(
                chargement_issues
            ),
        )

    def make_operational_result(
        self,
        *,
        states=(),
        issues=(),
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
            source_row_count=0,
            included_evidence_row_count=0,
            ignored_accepted_non_sales_count=0,
            outside_requested_period_count=0,
            partial_overlap_excluded_count=0,
            states=tuple(states),
            attribution_issues=tuple(issues),
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
                chargement_quantity=Decimal(
                    chargement
                ),
                sold_quantity=Decimal(sold),
            ),
        )

    def operational_state(
        self,
        *,
        truck_id,
        status,
        brand_id=1,
    ):
        return BrandTruckOperationalState(
            brand_id=brand_id,
            truck_id=truck_id,
            status=status,
            sales_activity_count=0,
            sales_total=Decimal("0"),
            authoritative_stopped_count=(
                1
                if status
                == TruckOperationalStatus
                .CONFIRMED_STOPPED
                else 0
            ),
            possible_stopped_count=(
                1
                if status
                == TruckOperationalStatus
                .POSSIBLE_STOPPED
                else 0
            ),
            activity_row_ids=(),
            authoritative_stopped_row_ids=(),
            possible_stopped_row_ids=(),
        )

    def combine(
        self,
        *,
        sales=None,
        pos=None,
        products=None,
        operational=None,
    ):
        return combine_worker_performance(
            sales_result=(
                sales or self.make_sales_result()
            ),
            pos_result=(
                pos or self.make_pos_result()
            ),
            product_result=(
                products
                or self.make_product_result()
            ),
            operational_result=(
                operational
                or self.make_operational_result()
            ),
        )

    def test_combines_sales_visits_clients_and_products(self):
        sales = self.make_sales_result(
            workers=(
                WorkerSalesTotal(
                    worker_id=10,
                    metrics=self.sales_metrics(
                        "300",
                        records=3,
                        positive=2,
                        zero=1,
                    ),
                ),
            ),
        )

        pos = self.make_pos_result(
            workers=(
                WorkerVisitTotal(
                    worker_id=10,
                    metrics=self.visit_metrics(
                        total=4,
                        visited=3,
                        not_visited=1,
                        unique_days=4,
                    ),
                ),
            ),
            worker_clients=(
                BrandWorkerClientVisitTotal(
                    brand_id=1,
                    worker_id=10,
                    client="Client A",
                    client_normalized="client a",
                    metrics=self.visit_metrics(
                        total=2,
                        visited=2,
                        not_visited=0,
                        unique_days=2,
                    ),
                ),
                BrandWorkerClientVisitTotal(
                    brand_id=1,
                    worker_id=10,
                    client="Client B",
                    client_normalized="client b",
                    metrics=self.visit_metrics(
                        total=2,
                        visited=1,
                        not_visited=1,
                        unique_days=2,
                    ),
                ),
            ),
        )

        products = self.make_product_result(
            workers=(
                self.worker_product(
                    worker_id=10,
                    article="Sold Product",
                    normalized="sold product",
                    opening="10",
                    sold="5",
                ),
                self.worker_product(
                    worker_id=10,
                    article="Not Sold Product",
                    normalized="not sold product",
                    chargement="8",
                    sold="0",
                ),
                self.worker_product(
                    worker_id=10,
                    article="Negative Gap Product",
                    normalized="negative gap product",
                    sold="3",
                ),
            ),
        )

        result = self.combine(
            sales=sales,
            pos=pos,
            products=products,
        )

        worker = result.workers[0]

        self.assertEqual(worker.worker_id, 10)
        self.assertEqual(
            worker.total_sales,
            Decimal("300"),
        )
        self.assertEqual(
            worker.average_sale_value,
            Decimal("100"),
        )
        self.assertEqual(
            worker.average_positive_sale_value,
            Decimal("150"),
        )
        self.assertEqual(
            worker.zero_total_sale_rate,
            Decimal("1") / Decimal("3"),
        )
        self.assertEqual(
            worker.visit_success_rate,
            Decimal("0.75"),
        )
        self.assertEqual(
            worker.non_visit_rate,
            Decimal("0.25"),
        )
        self.assertEqual(
            worker.distinct_brand_client_count,
            2,
        )
        self.assertEqual(
            worker.brand_product_count,
            3,
        )
        self.assertEqual(
            worker.sold_product_count,
            2,
        )
        self.assertEqual(
            worker.not_sold_product_count,
            1,
        )
        self.assertEqual(
            worker.negative_gap_product_count,
            1,
        )
        self.assertEqual(
            worker.sold_without_supply_context_count,
            1,
        )

    def test_workers_from_any_source_are_included(self):
        sales = self.make_sales_result(
            workers=(
                WorkerSalesTotal(
                    worker_id=1,
                    metrics=self.sales_metrics(
                        "100",
                        records=1,
                        positive=1,
                        zero=0,
                    ),
                ),
            ),
        )

        pos = self.make_pos_result(
            workers=(
                WorkerVisitTotal(
                    worker_id=2,
                    metrics=self.visit_metrics(
                        total=1,
                        visited=1,
                        not_visited=0,
                        unique_days=1,
                    ),
                ),
            ),
        )

        products = self.make_product_result(
            workers=(
                self.worker_product(
                    worker_id=3,
                    article="Product",
                    normalized="product",
                    opening="5",
                ),
            ),
        )

        result = self.combine(
            sales=sales,
            pos=pos,
            products=products,
        )

        self.assertEqual(
            [worker.worker_id for worker in result.workers],
            [1, 2, 3],
        )
        self.assertEqual(
            result.worker_count,
            3,
        )
        self.assertEqual(
            result.measured_sales_worker_count,
            1,
        )

    def test_sales_rankings_exclude_unmeasured_workers(self):
        sales = self.make_sales_result(
            workers=(
                WorkerSalesTotal(
                    worker_id=1,
                    metrics=self.sales_metrics(
                        "500",
                        records=2,
                        positive=2,
                        zero=0,
                    ),
                ),
                WorkerSalesTotal(
                    worker_id=2,
                    metrics=self.sales_metrics(
                        "100",
                        records=1,
                        positive=1,
                        zero=0,
                    ),
                ),
            ),
        )

        products = self.make_product_result(
            workers=(
                self.worker_product(
                    worker_id=3,
                    article="No Sales Worker Product",
                    normalized="no sales worker product",
                    opening="5",
                ),
            ),
        )

        result = self.combine(
            sales=sales,
            products=products,
        )

        self.assertEqual(
            [
                worker.worker_id
                for worker in result.top_sales_workers()
            ],
            [1, 2],
        )
        self.assertEqual(
            [
                worker.worker_id
                for worker in result.lowest_sales_workers()
            ],
            [2, 1],
        )
        self.assertEqual(
            [
                worker.worker_id
                for worker
                in result.workers_without_sales_measurement
            ],
            [3],
        )

    def test_visit_ranking_respects_minimum_records_and_limit(
        self,
    ):
        pos = self.make_pos_result(
            workers=(
                WorkerVisitTotal(
                    worker_id=1,
                    metrics=self.visit_metrics(
                        total=10,
                        visited=8,
                        not_visited=2,
                        unique_days=10,
                    ),
                ),
                WorkerVisitTotal(
                    worker_id=2,
                    metrics=self.visit_metrics(
                        total=2,
                        visited=2,
                        not_visited=0,
                        unique_days=2,
                    ),
                ),
                WorkerVisitTotal(
                    worker_id=3,
                    metrics=self.visit_metrics(
                        total=8,
                        visited=6,
                        not_visited=2,
                        unique_days=8,
                    ),
                ),
                WorkerVisitTotal(
                    worker_id=4,
                    metrics=self.visit_metrics(
                        total=5,
                        visited=4,
                        not_visited=1,
                        unique_days=5,
                    ),
                ),
            ),
        )

        result = self.combine(pos=pos)

        ranked = result.highest_visit_rate_workers(
            minimum_pos_records=5,
        )

        self.assertEqual(
            [worker.worker_id for worker in ranked],
            [1, 4, 3],
        )

        limited = result.highest_visit_rate_workers(
            limit=2,
            minimum_pos_records=5,
        )

        self.assertEqual(
            [worker.worker_id for worker in limited],
            [1, 4],
        )

    def test_non_visit_ranking_respects_minimum_records(self):
        pos = self.make_pos_result(
            workers=(
                WorkerVisitTotal(
                    worker_id=1,
                    metrics=self.visit_metrics(
                        total=10,
                        visited=5,
                        not_visited=5,
                        unique_days=10,
                    ),
                ),
                WorkerVisitTotal(
                    worker_id=2,
                    metrics=self.visit_metrics(
                        total=2,
                        visited=0,
                        not_visited=2,
                        unique_days=2,
                    ),
                ),
                WorkerVisitTotal(
                    worker_id=3,
                    metrics=self.visit_metrics(
                        total=8,
                        visited=6,
                        not_visited=2,
                        unique_days=8,
                    ),
                ),
            ),
        )

        result = self.combine(pos=pos)

        ranked = result.highest_non_visit_rate_workers(
            minimum_pos_records=5,
        )

        self.assertEqual(
            [worker.worker_id for worker in ranked],
            [1, 3],
        )

    def test_product_attention_rankings_are_separate(self):
        products = self.make_product_result(
            workers=(
                self.worker_product(
                    worker_id=1,
                    article="Unsold A",
                    normalized="unsold a",
                    opening="10",
                ),
                self.worker_product(
                    worker_id=1,
                    article="Unsold B",
                    normalized="unsold b",
                    chargement="5",
                ),
                self.worker_product(
                    worker_id=2,
                    article="Negative A",
                    normalized="negative a",
                    sold="4",
                ),
            ),
        )

        result = self.combine(products=products)

        self.assertEqual(
            result.most_not_sold_products_workers()[0]
            .worker_id,
            1,
        )
        self.assertEqual(
            result.most_negative_gap_products_workers()[0]
            .worker_id,
            2,
        )

    def test_operational_states_remain_separate(self):
        operational = self.make_operational_result(
            states=(
                self.operational_state(
                    truck_id=10,
                    status=(
                        TruckOperationalStatus
                        .CONFIRMED_STOPPED
                    ),
                ),
                self.operational_state(
                    truck_id=11,
                    status=(
                        TruckOperationalStatus
                        .POSSIBLE_STOPPED
                    ),
                ),
                self.operational_state(
                    truck_id=12,
                    status=(
                        TruckOperationalStatus
                        .CONFLICTING_EVIDENCE
                    ),
                ),
            ),
        )

        result = self.combine(
            operational=operational,
        )

        self.assertEqual(
            [
                state.truck_id
                for state
                in result.confirmed_stopped_trucks
            ],
            [10],
        )
        self.assertEqual(
            [
                state.truck_id
                for state
                in result.possible_stopped_trucks
            ],
            [11],
        )
        self.assertEqual(
            [
                state.truck_id
                for state
                in result.conflicting_truck_states
            ],
            [12],
        )
        self.assertEqual(
            result.workers,
            (),
        )

    def test_data_quality_counts_are_preserved(self):
        result = self.combine(
            sales=self.make_sales_result(
                issues=(object(), object()),
            ),
            pos=self.make_pos_result(
                issues=(object(),),
                numeric_warnings=3,
                duplicate_warnings=2,
            ),
            products=self.make_product_result(
                items_issues=4,
                opening_issues=1,
                chargement_issues=2,
            ),
            operational=self.make_operational_result(
                issues=(object(), object(), object()),
            ),
        )

        quality = result.data_quality

        self.assertEqual(
            quality.attribution_issue_count,
            13,
        )
        self.assertEqual(
            quality.warning_count,
            5,
        )
        self.assertEqual(
            quality.total_issue_and_warning_count,
            18,
        )

    def test_mismatched_periods_are_rejected(self):
        pos = self.make_pos_result(
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
        )

        with self.assertRaisesRegex(
            ValueError,
            "same requested period",
        ):
            self.combine(pos=pos)

    def test_invalid_ranking_arguments_are_rejected(self):
        result = self.combine()

        with self.assertRaisesRegex(
            ValueError,
            "limit cannot be negative",
        ):
            result.top_sales_workers(-1)

        with self.assertRaisesRegex(
            ValueError,
            "limit cannot be negative",
        ):
            result.lowest_sales_workers(-1)

        with self.assertRaisesRegex(
            ValueError,
            "minimum_pos_records must be at least 1",
        ):
            result.highest_non_visit_rate_workers(
                minimum_pos_records=0,
            )

    def test_invalid_calculation_period_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "period_end cannot be before period_start",
        ):
            calculate_worker_performance(
                period_start=date(2026, 7, 10),
                period_end=date(2026, 7, 1),
            )
