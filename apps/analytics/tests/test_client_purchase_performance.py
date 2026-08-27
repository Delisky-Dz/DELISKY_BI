from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from apps.analytics.services.client_purchase_performance import (
    ClientIdentityStatus,
    combine_client_purchase_performance,
)
from apps.analytics.services.items_aggregation import (
    BrandVanClientItemTotal,
    BrandVanClientProductItemTotal,
    ItemMetrics,
    ItemsAggregationResult,
)
from apps.analytics.services.sales_aggregation import (
    BrandVanClientSalesTotal,
    SalesAggregationResult,
    SalesMetrics,
)


class ClientPurchasePerformanceTests(
    SimpleTestCase
):
    period_start = date(2026, 7, 1)
    period_end = date(2026, 7, 7)

    def item_metrics(
        self,
        quantity,
        records=1,
    ):
        quantity = Decimal(quantity)

        return ItemMetrics(
            quantity_sold=quantity,
            item_record_count=records,
            positive_quantity_record_count=(
                records if quantity > 0 else 0
            ),
            zero_quantity_record_count=(
                records if quantity == 0 else 0
            ),
        )

    def sales_metrics(
        self,
        total,
        records=1,
    ):
        total = Decimal(total)

        return SalesMetrics(
            total_sales=total,
            sale_record_count=records,
            positive_sale_record_count=(
                records if total > 0 else 0
            ),
            zero_total_record_count=(
                records if total == 0 else 0
            ),
        )

    def make_items(
        self,
        *,
        clients=(),
        products=(),
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
            source_row_count=2,
            included_row_count=2,
            outside_requested_period_count=0,
            partial_overlap_excluded_count=0,
            overall=self.item_metrics(
                "0",
                0,
            ),
            by_brand=(),
            by_truck=(),
            by_worker=(),
            by_brand_product=(),
            by_brand_truck_product=(),
            by_brand_worker_product=(),
            attribution_issues=(),
            by_brand_client=(),
            by_brand_client_product=(),
            by_brand_van_client=tuple(
                clients
            ),
            by_brand_van_client_product=tuple(
                products
            ),
        )

    def make_sales(
        self,
        *,
        clients=(),
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
            source_row_count=2,
            included_row_count=2,
            outside_requested_period_count=0,
            overall=self.sales_metrics(
                "0",
                0,
            ),
            by_brand=(),
            by_truck=(),
            by_worker=(),
            by_brand_truck=(),
            by_brand_worker=(),
            by_brand_truck_worker=(),
            attribution_issues=(),
            by_date=(),
            by_date_brand_truck_worker=(),
            by_brand_client=(),
            by_brand_van_client=tuple(
                clients
            ),
        )

    def test_combines_sales_code_with_items_name(
        self,
    ):
        items = self.make_items(
            clients=(
                BrandVanClientItemTotal(
                    brand_id=1,
                    van="route 1",
                    van_normalized="route 1",
                    client="Client Alpha",
                    client_normalized=(
                        "client alpha"
                    ),
                    metrics=self.item_metrics(
                        "50",
                        2,
                    ),
                ),
            ),
            products=(
                BrandVanClientProductItemTotal(
                    brand_id=1,
                    van="route 1",
                    van_normalized="route 1",
                    client="Client Alpha",
                    client_normalized=(
                        "client alpha"
                    ),
                    article="Product A",
                    article_normalized=(
                        "product a"
                    ),
                    metrics=self.item_metrics(
                        "20"
                    ),
                ),
                BrandVanClientProductItemTotal(
                    brand_id=1,
                    van="route 1",
                    van_normalized="route 1",
                    client="Client Alpha",
                    client_normalized=(
                        "client alpha"
                    ),
                    article="Product B",
                    article_normalized=(
                        "product b"
                    ),
                    metrics=self.item_metrics(
                        "30"
                    ),
                ),
            ),
        )

        sales = self.make_sales(
            clients=(
                BrandVanClientSalesTotal(
                    brand_id=1,
                    van="route 1",
                    van_normalized="route 1",
                    client="430123 Client Alpha",
                    client_normalized=(
                        "430123 client alpha"
                    ),
                    metrics=self.sales_metrics(
                        "2500",
                        2,
                    ),
                ),
            ),
        )

        result = (
            combine_client_purchase_performance(
                items_result=items,
                sales_result=sales,
            )
        )

        self.assertEqual(
            len(result.clients),
            1,
        )

        client = result.clients[0]

        self.assertEqual(
            client.client_normalized,
            "client alpha",
        )
        self.assertEqual(
            client.van_normalized,
            "route 1",
        )
        self.assertEqual(
            client.customer_code,
            "430123",
        )
        self.assertEqual(
            client.identity_status,
            ClientIdentityStatus.UNAMBIGUOUS,
        )
        self.assertEqual(
            client.metrics.total_sales,
            Decimal("2500"),
        )
        self.assertEqual(
            client.metrics.sale_record_count,
            2,
        )
        self.assertEqual(
            client.metrics.quantity_sold,
            Decimal("50"),
        )
        self.assertEqual(
            client.metrics.distinct_product_count,
            2,
        )
        self.assertEqual(
            client.metrics.average_sale_value,
            Decimal("1250"),
        )
        self.assertEqual(
            client.metrics.average_quantity_per_sale,
            Decimal("25"),
        )
        self.assertFalse(
            result.has_identity_issues
        )

    def test_same_name_on_other_route_is_not_merged(
        self,
    ):
        items = self.make_items(
            clients=(
                BrandVanClientItemTotal(
                    brand_id=1,
                    van="route 1",
                    van_normalized="route 1",
                    client="Same Name",
                    client_normalized="same name",
                    metrics=self.item_metrics("10"),
                ),
            ),
        )

        sales = self.make_sales(
            clients=(
                BrandVanClientSalesTotal(
                    brand_id=1,
                    van="route 2",
                    van_normalized="route 2",
                    client="430001 Same Name",
                    client_normalized=(
                        "430001 same name"
                    ),
                    metrics=self.sales_metrics("500"),
                ),
            ),
        )

        result = (
            combine_client_purchase_performance(
                items_result=items,
                sales_result=sales,
            )
        )

        self.assertEqual(
            len(result.clients),
            2,
        )

    def test_multiple_sales_codes_are_ambiguous(
        self,
    ):
        items = self.make_items(
            clients=(
                BrandVanClientItemTotal(
                    brand_id=1,
                    van="route 3",
                    van_normalized="route 3",
                    client="Salah",
                    client_normalized="salah",
                    metrics=self.item_metrics("10"),
                ),
            ),
        )

        sales = self.make_sales(
            clients=(
                BrandVanClientSalesTotal(
                    brand_id=1,
                    van="route 3",
                    van_normalized="route 3",
                    client="430001 Salah",
                    client_normalized=(
                        "430001 salah"
                    ),
                    metrics=self.sales_metrics("500"),
                ),
                BrandVanClientSalesTotal(
                    brand_id=1,
                    van="route 3",
                    van_normalized="route 3",
                    client="431999 Salah",
                    client_normalized=(
                        "431999 salah"
                    ),
                    metrics=self.sales_metrics("700"),
                ),
            ),
        )

        result = (
            combine_client_purchase_performance(
                items_result=items,
                sales_result=sales,
            )
        )

        self.assertTrue(
            result.has_identity_issues
        )
        self.assertEqual(
            len(result.identity_issues),
            1,
        )
        self.assertEqual(
            result.identity_issues[0]
            .sale_client_codes,
            ("430001", "431999"),
        )

        items_client = next(
            client
            for client in result.clients
            if client.metrics.has_items_data
        )

        self.assertEqual(
            items_client.identity_status,
            ClientIdentityStatus.AMBIGUOUS,
        )
        self.assertFalse(
            items_client.metrics.has_sales_data
        )

        sales_clients = [
            client
            for client in result.clients
            if client.metrics.has_sales_data
        ]

        self.assertEqual(
            len(sales_clients),
            2,
        )
        self.assertTrue(
            all(
                client.identity_status
                == ClientIdentityStatus.AMBIGUOUS
                for client in sales_clients
            )
        )

    def test_products_for_client_is_route_aware(
        self,
    ):
        product = BrandVanClientProductItemTotal(
            brand_id=2,
            van="route x",
            van_normalized="route x",
            client="Lookup Client",
            client_normalized="lookup client",
            article="Lookup Product",
            article_normalized="lookup product",
            metrics=self.item_metrics("12"),
        )

        result = (
            combine_client_purchase_performance(
                items_result=self.make_items(
                    products=(product,),
                ),
                sales_result=self.make_sales(),
            )
        )

        products = result.products_for_client(
            brand_id=2,
            van_normalized="route x",
            client_normalized="lookup client",
        )

        self.assertEqual(
            len(products),
            1,
        )
        self.assertEqual(
            products[0].article_normalized,
            "lookup product",
        )

    def test_period_mismatch_is_rejected(self):
        items = self.make_items()

        sales = self.make_sales(
            period_start=date(2026, 7, 2),
        )

        with self.assertRaisesRegex(
            ValueError,
            "analytical periods must match",
        ):
            combine_client_purchase_performance(
                items_result=items,
                sales_result=sales,
            )
