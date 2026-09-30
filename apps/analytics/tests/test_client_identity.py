from decimal import Decimal

from django.test import SimpleTestCase

from apps.analytics.services.client_identity import (
    build_sales_client_identity_index,
    split_sales_client_identity,
)
from apps.analytics.services.sales_aggregation import (
    BrandTruckClientSalesTotal,
    SalesMetrics,
)


class ClientIdentityTests(SimpleTestCase):
    def test_splits_numeric_sales_client_code(self):
        result = split_sales_client_identity(
            client="4300201 الإخوة قريبع",
            client_normalized="4300201 الإخوة قريبع",
        )

        self.assertEqual(
            result,
            (
                "4300201",
                "الإخوة قريبع",
                "الإخوة قريبع",
            ),
        )

    def test_keeps_client_without_numeric_code(self):
        result = split_sales_client_identity(
            client="الإخوة قريبع",
            client_normalized="الإخوة قريبع",
        )

        self.assertEqual(
            result,
            (
                None,
                "الإخوة قريبع",
                "الإخوة قريبع",
            ),
        )



    def test_builds_safe_route_identity_for_coded_sales_client(self):
        sales_rows = (
            BrandTruckClientSalesTotal(
                brand_id=1,
                truck_id=9,
                client="4300201 الإخوة قريبع",
                client_normalized="4300201 الإخوة قريبع",
                metrics=SalesMetrics(
                    total_sales=Decimal("563757.62"),
                    sale_record_count=10,
                    positive_sale_record_count=10,
                    zero_total_record_count=0,
                ),
            ),
        )

        result = build_sales_client_identity_index(
            sales_rows
        )

        self.assertEqual(
            result.safe_matches[
                (1, 9, "الإخوة قريبع")
            ],
            "4300201 الإخوة قريبع",
        )
        self.assertEqual(
            result.ambiguous_keys,
            frozenset(),
        )

    def test_marks_multiple_sales_identities_on_same_route_as_ambiguous(self):
        sales_rows = (
            BrandTruckClientSalesTotal(
                brand_id=1,
                truck_id=9,
                client="431030 فاتح",
                client_normalized="431030 فاتح",
                metrics=SalesMetrics(
                    total_sales=Decimal("100"),
                    sale_record_count=1,
                    positive_sale_record_count=1,
                    zero_total_record_count=0,
                ),
            ),
            BrandTruckClientSalesTotal(
                brand_id=1,
                truck_id=9,
                client="431245 فاتح",
                client_normalized="431245 فاتح",
                metrics=SalesMetrics(
                    total_sales=Decimal("200"),
                    sale_record_count=1,
                    positive_sale_record_count=1,
                    zero_total_record_count=0,
                ),
            ),
        )

        result = build_sales_client_identity_index(
            sales_rows
        )
        key = (1, 9, "فاتح")

        self.assertNotIn(
            key,
            result.safe_matches,
        )
        self.assertIn(
            key,
            result.ambiguous_keys,
        )

    def test_resolves_pos_client_to_safe_sales_identity(self):
        sales_rows = (
            BrandTruckClientSalesTotal(
                brand_id=1,
                truck_id=9,
                client="4300201 الإخوة قريبع",
                client_normalized="4300201 الإخوة قريبع",
                metrics=SalesMetrics(
                    total_sales=Decimal("563757.62"),
                    sale_record_count=10,
                    positive_sale_record_count=10,
                    zero_total_record_count=0,
                ),
            ),
        )

        index = build_sales_client_identity_index(
            sales_rows
        )

        self.assertEqual(
            index.resolve(
                brand_id=1,
                truck_id=9,
                client_normalized="الإخوة قريبع",
            ),
            "4300201 الإخوة قريبع",
        )

    def test_does_not_resolve_ambiguous_pos_client(self):
        sales_rows = (
            BrandTruckClientSalesTotal(
                brand_id=1,
                truck_id=9,
                client="431030 فاتح",
                client_normalized="431030 فاتح",
                metrics=SalesMetrics(
                    total_sales=Decimal("100"),
                    sale_record_count=1,
                    positive_sale_record_count=1,
                    zero_total_record_count=0,
                ),
            ),
            BrandTruckClientSalesTotal(
                brand_id=1,
                truck_id=9,
                client="431245 فاتح",
                client_normalized="431245 فاتح",
                metrics=SalesMetrics(
                    total_sales=Decimal("200"),
                    sale_record_count=1,
                    positive_sale_record_count=1,
                    zero_total_record_count=0,
                ),
            ),
        )

        index = build_sales_client_identity_index(
            sales_rows
        )

        self.assertIsNone(
            index.resolve(
                brand_id=1,
                truck_id=9,
                client_normalized="فاتح",
            )
        )
