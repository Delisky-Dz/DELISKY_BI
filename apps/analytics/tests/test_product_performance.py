from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from apps.analytics.services.items_aggregation import (
    BrandTruckProductItemTotal,
    BrandWorkerProductItemTotal,
    ItemMetrics,
    ItemsAggregationResult,
)
from apps.analytics.services.product_performance import (
    calculate_product_performance,
    combine_product_performance,
)
from apps.analytics.services.stock_flow_aggregation import (
    BrandTruckProductQuantityTotal,
    BrandWorkerProductQuantityTotal,
    QuantityMetrics,
    StockFlowAggregationResult,
)
from apps.imports.models import ImportReportType


class ProductPerformanceTests(SimpleTestCase):
    period_start = date(2026, 7, 1)
    period_end = date(2026, 7, 7)

    def item_metrics(self, quantity):
        quantity = Decimal(str(quantity))

        return ItemMetrics(
            quantity_sold=quantity,
            item_record_count=1,
            positive_quantity_record_count=(
                1 if quantity > 0 else 0
            ),
            zero_quantity_record_count=(
                1 if quantity == 0 else 0
            ),
        )

    def quantity_metrics(self, quantity):
        quantity = Decimal(str(quantity))

        return QuantityMetrics(
            total_quantity=quantity,
            record_count=1,
            positive_quantity_record_count=(
                1 if quantity > 0 else 0
            ),
            negative_quantity_record_count=(
                1 if quantity < 0 else 0
            ),
            zero_quantity_record_count=(
                1 if quantity == 0 else 0
            ),
        )

    def make_items_result(
        self,
        *,
        worker_products=(),
        truck_products=(),
        issues=(),
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
            source_row_count=len(worker_products),
            included_row_count=len(worker_products),
            outside_requested_period_count=0,
            partial_overlap_excluded_count=0,
            overall=ItemMetrics(
                quantity_sold=Decimal("0"),
                item_record_count=0,
                positive_quantity_record_count=0,
                zero_quantity_record_count=0,
            ),
            by_brand=(),
            by_truck=(),
            by_worker=(),
            by_brand_product=(),
            by_brand_truck_product=tuple(
                truck_products
            ),
            by_brand_worker_product=tuple(
                worker_products
            ),
            attribution_issues=tuple(issues),
        )

    def make_stock_result(
        self,
        report_type,
        *,
        worker_products=(),
        truck_products=(),
        issues=(),
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
            source_row_count=len(worker_products),
            included_row_count=len(worker_products),
            outside_requested_period_count=0,
            partial_overlap_excluded_count=0,
            overall=QuantityMetrics(
                total_quantity=Decimal("0"),
                record_count=0,
                positive_quantity_record_count=0,
                negative_quantity_record_count=0,
                zero_quantity_record_count=0,
            ),
            by_brand=(),
            by_truck=(),
            by_worker=(),
            by_brand_product=(),
            by_brand_truck_product=tuple(
                truck_products
            ),
            by_brand_worker_product=tuple(
                worker_products
            ),
            attribution_issues=tuple(issues),
        )

    def worker_item(
        self,
        article,
        normalized,
        quantity,
        *,
        brand_id=1,
        worker_id=10,
    ):
        return BrandWorkerProductItemTotal(
            brand_id=brand_id,
            worker_id=worker_id,
            article=article,
            article_normalized=normalized,
            metrics=self.item_metrics(quantity),
        )

    def truck_item(
        self,
        article,
        normalized,
        quantity,
        *,
        brand_id=1,
        truck_id=20,
    ):
        return BrandTruckProductItemTotal(
            brand_id=brand_id,
            truck_id=truck_id,
            article=article,
            article_normalized=normalized,
            metrics=self.item_metrics(quantity),
        )

    def worker_stock(
        self,
        article,
        normalized,
        quantity,
        *,
        brand_id=1,
        worker_id=10,
    ):
        return BrandWorkerProductQuantityTotal(
            brand_id=brand_id,
            worker_id=worker_id,
            article=article,
            article_normalized=normalized,
            metrics=self.quantity_metrics(quantity),
        )

    def truck_stock(
        self,
        article,
        normalized,
        quantity,
        *,
        brand_id=1,
        truck_id=20,
    ):
        return BrandTruckProductQuantityTotal(
            brand_id=brand_id,
            truck_id=truck_id,
            article=article,
            article_normalized=normalized,
            metrics=self.quantity_metrics(quantity),
        )

    def combine(
        self,
        *,
        items=None,
        opening=None,
        chargement=None,
    ):
        return combine_product_performance(
            items_result=(
                items or self.make_items_result()
            ),
            opening_stock_result=(
                opening
                or self.make_stock_result(
                    ImportReportType.OPENING_STOCK
                )
            ),
            chargement_result=(
                chargement
                or self.make_stock_result(
                    ImportReportType.CHARGEMENT
                )
            ),
        )

    def test_combines_opening_loading_and_sales(self):
        items = self.make_items_result(
            worker_products=(
                self.worker_item(
                    "Product A",
                    "product a",
                    "30",
                ),
            ),
            truck_products=(
                self.truck_item(
                    "Product A",
                    "product a",
                    "30",
                ),
            ),
        )

        opening = self.make_stock_result(
            ImportReportType.OPENING_STOCK,
            worker_products=(
                self.worker_stock(
                    "Product A",
                    "product a",
                    "100",
                ),
            ),
            truck_products=(
                self.truck_stock(
                    "Product A",
                    "product a",
                    "100",
                ),
            ),
        )

        chargement = self.make_stock_result(
            ImportReportType.CHARGEMENT,
            worker_products=(
                self.worker_stock(
                    "Product A",
                    "product a",
                    "50",
                ),
            ),
            truck_products=(
                self.truck_stock(
                    "Product A",
                    "product a",
                    "50",
                ),
            ),
        )

        result = self.combine(
            items=items,
            opening=opening,
            chargement=chargement,
        )

        worker_product = result.worker_products[0]
        truck_product = result.truck_products[0]

        self.assertEqual(
            worker_product.quantities.opening_quantity,
            Decimal("100"),
        )
        self.assertEqual(
            worker_product.quantities.chargement_quantity,
            Decimal("50"),
        )
        self.assertEqual(
            worker_product.quantities.sold_quantity,
            Decimal("30"),
        )
        self.assertEqual(
            worker_product.quantities.supplied_quantity,
            Decimal("150"),
        )
        self.assertEqual(
            worker_product.quantities.analytical_quantity_gap,
            Decimal("120"),
        )
        self.assertEqual(
            worker_product.quantities.sold_to_supplied_ratio,
            Decimal("0.2"),
        )
        self.assertEqual(
            truck_product.quantities.sold_quantity,
            Decimal("30"),
        )

    def test_chargement_returns_reduce_supply_and_gap(self):
        items = self.make_items_result(
            worker_products=(
                self.worker_item(
                    "Return Test Product",
                    "return test product",
                    "70",
                ),
            ),
            truck_products=(
                self.truck_item(
                    "Return Test Product",
                    "return test product",
                    "70",
                ),
            ),
        )

        chargement = self.make_stock_result(
            ImportReportType.CHARGEMENT,
            worker_products=(
                self.worker_stock(
                    "Return Test Product",
                    "return test product",
                    "100",
                ),
                self.worker_stock(
                    "Return Test Product",
                    "return test product",
                    "-20",
                ),
            ),
            truck_products=(
                self.truck_stock(
                    "Return Test Product",
                    "return test product",
                    "100",
                ),
                self.truck_stock(
                    "Return Test Product",
                    "return test product",
                    "-20",
                ),
            ),
        )

        result = self.combine(
            items=items,
            chargement=chargement,
        )

        worker_product = result.worker_products[0]
        truck_product = result.truck_products[0]

        self.assertEqual(
            worker_product.quantities.chargement_quantity,
            Decimal("80"),
        )
        self.assertEqual(
            worker_product.quantities.supplied_quantity,
            Decimal("80"),
        )
        self.assertEqual(
            worker_product.quantities.sold_quantity,
            Decimal("70"),
        )
        self.assertEqual(
            worker_product.quantities.analytical_quantity_gap,
            Decimal("10"),
        )
        self.assertEqual(
            worker_product.quantities.sold_to_supplied_ratio,
            Decimal("0.875"),
        )

        self.assertEqual(
            truck_product.quantities.chargement_quantity,
            Decimal("80"),
        )
        self.assertEqual(
            truck_product.quantities.analytical_quantity_gap,
            Decimal("10"),
        )
        self.assertFalse(
            worker_product.quantities.has_negative_quantity_gap
        )

    def test_not_sold_products_are_ranked_by_supply(self):
        opening = self.make_stock_result(
            ImportReportType.OPENING_STOCK,
            worker_products=(
                self.worker_stock(
                    "Product Small",
                    "product small",
                    "10",
                ),
            ),
        )

        chargement = self.make_stock_result(
            ImportReportType.CHARGEMENT,
            worker_products=(
                self.worker_stock(
                    "Product Large",
                    "product large",
                    "25",
                ),
            ),
        )

        result = self.combine(
            opening=opening,
            chargement=chargement,
        )

        ranked = result.not_sold_for_worker(
            worker_id=10,
        )

        self.assertEqual(
            [item.article_normalized for item in ranked],
            [
                "product large",
                "product small",
            ],
        )
        self.assertEqual(
            result.worker_not_sold_count,
            2,
        )

    def test_least_sold_excludes_zero_sales(self):
        items = self.make_items_result(
            worker_products=(
                self.worker_item(
                    "Product Five",
                    "product five",
                    "5",
                ),
                self.worker_item(
                    "Product Two",
                    "product two",
                    "2",
                ),
                self.worker_item(
                    "Product Zero",
                    "product zero",
                    "0",
                ),
            ),
        )

        result = self.combine(
            items=items,
        )

        ranked = result.least_sold_for_worker(
            worker_id=10,
        )

        self.assertEqual(
            [item.article_normalized for item in ranked],
            [
                "product two",
                "product five",
            ],
        )

    def test_sold_without_supply_creates_negative_gap(self):
        items = self.make_items_result(
            worker_products=(
                self.worker_item(
                    "Unmatched Supply Product",
                    "unmatched supply product",
                    "7",
                ),
            ),
            truck_products=(
                self.truck_item(
                    "Unmatched Supply Product",
                    "unmatched supply product",
                    "7",
                ),
            ),
        )

        result = self.combine(
            items=items,
        )

        worker_product = result.worker_products[0]

        self.assertTrue(
            worker_product.quantities
            .is_sold_without_supply_context
        )
        self.assertTrue(
            worker_product.quantities
            .has_negative_quantity_gap
        )
        self.assertEqual(
            worker_product.quantities
            .analytical_quantity_gap,
            Decimal("-7"),
        )
        self.assertIsNone(
            worker_product.quantities
            .sold_to_supplied_ratio
        )
        self.assertEqual(
            result.worker_negative_gap_count,
            1,
        )
        self.assertEqual(
            result.truck_negative_gap_count,
            1,
        )

    def test_product_name_prefers_items_name(self):
        opening = self.make_stock_result(
            ImportReportType.OPENING_STOCK,
            worker_products=(
                self.worker_stock(
                    "Opening Name",
                    "same product",
                    "10",
                ),
            ),
        )

        chargement = self.make_stock_result(
            ImportReportType.CHARGEMENT,
            worker_products=(
                self.worker_stock(
                    "Chargement Name",
                    "same product",
                    "5",
                ),
            ),
        )

        items = self.make_items_result(
            worker_products=(
                self.worker_item(
                    "Items Name",
                    "same product",
                    "2",
                ),
            ),
        )

        result = self.combine(
            items=items,
            opening=opening,
            chargement=chargement,
        )

        self.assertEqual(
            result.worker_products[0].article,
            "Items Name",
        )

    def test_truck_rankings_are_calculated_separately(self):
        opening = self.make_stock_result(
            ImportReportType.OPENING_STOCK,
            truck_products=(
                self.truck_stock(
                    "Truck Product A",
                    "truck product a",
                    "20",
                    truck_id=30,
                ),
                self.truck_stock(
                    "Truck Product B",
                    "truck product b",
                    "10",
                    truck_id=30,
                ),
            ),
        )

        result = self.combine(
            opening=opening,
        )

        ranked = result.not_sold_for_truck(
            truck_id=30,
        )

        self.assertEqual(
            [item.article_normalized for item in ranked],
            [
                "truck product a",
                "truck product b",
            ],
        )
        self.assertEqual(
            result.truck_not_sold_count,
            2,
        )

    def test_attribution_issue_counts_are_preserved(self):
        result = self.combine(
            items=self.make_items_result(
                issues=(object(), object()),
            ),
            opening=self.make_stock_result(
                ImportReportType.OPENING_STOCK,
                issues=(object(),),
            ),
            chargement=self.make_stock_result(
                ImportReportType.CHARGEMENT,
                issues=(object(), object(), object()),
            ),
        )

        self.assertEqual(
            result.items_attribution_issue_count,
            2,
        )
        self.assertEqual(
            result.opening_stock_attribution_issue_count,
            1,
        )
        self.assertEqual(
            result.chargement_attribution_issue_count,
            3,
        )

    def test_mismatched_periods_are_rejected(self):
        items = self.make_items_result()

        opening = self.make_stock_result(
            ImportReportType.OPENING_STOCK,
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
        )

        with self.assertRaisesRegex(
            ValueError,
            "same requested period",
        ):
            self.combine(
                items=items,
                opening=opening,
            )

    def test_wrong_stock_report_types_are_rejected(self):
        wrong_opening = self.make_stock_result(
            ImportReportType.CHARGEMENT,
        )

        with self.assertRaisesRegex(
            ValueError,
            "OPENING_STOCK aggregation",
        ):
            self.combine(
                opening=wrong_opening,
            )

        wrong_chargement = self.make_stock_result(
            ImportReportType.OPENING_STOCK,
        )

        with self.assertRaisesRegex(
            ValueError,
            "CHARGEMENT aggregation",
        ):
            self.combine(
                chargement=wrong_chargement,
            )

    def test_negative_limits_and_invalid_period_are_rejected(self):
        result = self.combine()

        with self.assertRaisesRegex(
            ValueError,
            "limit cannot be negative",
        ):
            result.not_sold_for_worker(
                worker_id=10,
                limit=-1,
            )

        with self.assertRaisesRegex(
            ValueError,
            "limit cannot be negative",
        ):
            result.least_sold_for_truck(
                truck_id=20,
                limit=-1,
            )

        with self.assertRaisesRegex(
            ValueError,
            "period_end cannot be before period_start",
        ):
            calculate_product_performance(
                period_start=date(2026, 7, 10),
                period_end=date(2026, 7, 1),
            )
