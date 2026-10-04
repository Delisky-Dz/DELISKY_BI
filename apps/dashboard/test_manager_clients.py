from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.analytics.services.pos_visit_aggregation import (
    BrandClientVisitTotal,
    BrandTruckClientVisitTotal,
    VisitMetrics,
)
from apps.analytics.services.sales_aggregation import (
    BrandClientSalesTotal,
    BrandTruckClientSalesTotal,
    SalesMetrics,
)
from apps.dashboard.manager_clients import (
    _client_sales_rows,
    _visited_without_sales,
)


def _sales_metrics(total):
    return SalesMetrics(
        total_sales=total,
        sale_record_count=1,
        positive_sale_record_count=1 if total > 0 else 0,
        zero_total_record_count=0 if total > 0 else 1,
    )


def _visit_metrics(total, visited, not_visited, days):
    return VisitMetrics(
        total_record_count=total,
        visited_record_count=visited,
        not_visited_record_count=not_visited,
        unique_client_day_count=days,
    )


class VisitedWithoutSalesTests(SimpleTestCase):
    @patch(
        "apps.dashboard.manager_clients._brand_names",
        return_value={1: "BIFA"},
    )
    def test_uses_route_aware_client_identity(
        self,
        _brand_names,
    ):
        sales = SimpleNamespace(
            by_brand_client=(
                BrandClientSalesTotal(
                    brand_id=1,
                    client="4300201 Client A",
                    client_normalized="4300201 client a",
                    metrics=_sales_metrics(100),
                ),
                BrandClientSalesTotal(
                    brand_id=1,
                    client="431030 Client C",
                    client_normalized="431030 client c",
                    metrics=_sales_metrics(50),
                ),
                BrandClientSalesTotal(
                    brand_id=1,
                    client="431245 Client C",
                    client_normalized="431245 client c",
                    metrics=_sales_metrics(75),
                ),
            ),
            by_brand_truck_client=(
                BrandTruckClientSalesTotal(
                    brand_id=1,
                    truck_id=10,
                    client="4300201 Client A",
                    client_normalized="4300201 client a",
                    metrics=_sales_metrics(100),
                ),
                BrandTruckClientSalesTotal(
                    brand_id=1,
                    truck_id=30,
                    client="431030 Client C",
                    client_normalized="431030 client c",
                    metrics=_sales_metrics(50),
                ),
                BrandTruckClientSalesTotal(
                    brand_id=1,
                    truck_id=30,
                    client="431245 Client C",
                    client_normalized="431245 client c",
                    metrics=_sales_metrics(75),
                ),
            ),
        )

        visits = SimpleNamespace(
            by_brand_truck_client=(
                BrandTruckClientVisitTotal(
                    brand_id=1,
                    truck_id=10,
                    client="Client A",
                    client_normalized="client a",
                    metrics=_visit_metrics(5, 5, 0, 3),
                ),
                BrandTruckClientVisitTotal(
                    brand_id=1,
                    truck_id=20,
                    client="Client B",
                    client_normalized="client b",
                    metrics=_visit_metrics(8, 7, 1, 4),
                ),
                BrandTruckClientVisitTotal(
                    brand_id=1,
                    truck_id=30,
                    client="Client C",
                    client_normalized="client c",
                    metrics=_visit_metrics(6, 6, 0, 2),
                ),
            ),
            by_brand_client=(
                BrandClientVisitTotal(
                    brand_id=1,
                    client="Client A",
                    client_normalized="client a",
                    metrics=_visit_metrics(5, 5, 0, 3),
                ),
                BrandClientVisitTotal(
                    brand_id=1,
                    client="Client B",
                    client_normalized="client b",
                    metrics=_visit_metrics(8, 7, 1, 4),
                ),
                BrandClientVisitTotal(
                    brand_id=1,
                    client="Client C",
                    client_normalized="client c",
                    metrics=_visit_metrics(6, 6, 0, 2),
                ),
            ),
        )

        rows = _visited_without_sales(
            sales=sales,
            visits=visits,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].client_name, "Client B")
        self.assertEqual(rows[0].visited_record_count, 7)
        self.assertEqual(rows[0].unique_client_day_count, 4)


class ClientSalesVisitEnrichmentTests(SimpleTestCase):
    @patch(
        "apps.dashboard.manager_clients._brand_names",
        return_value={1: "BIFA"},
    )
    def test_matches_pos_name_to_coded_sales_client(
        self,
        _brand_names,
    ):
        from apps.dashboard.manager_clients import (
            _client_sales_rows,
        )

        sales = SimpleNamespace(
            by_brand_client=(
                BrandClientSalesTotal(
                    brand_id=1,
                    client="4300201 الإخوة قريبع",
                    client_normalized="4300201 الإخوة قريبع",
                    metrics=_sales_metrics(563757.62),
                ),
            ),
            by_brand_truck_client=(
                BrandTruckClientSalesTotal(
                    brand_id=1,
                    truck_id=10,
                    client="4300201 الإخوة قريبع",
                    client_normalized="4300201 الإخوة قريبع",
                    metrics=_sales_metrics(563757.62),
                ),
            ),
        )

        visits = SimpleNamespace(
            by_brand_truck_client=(
                BrandTruckClientVisitTotal(
                    brand_id=1,
                    truck_id=10,
                    client="الإخوة قريبع",
                    client_normalized="الإخوة قريبع",
                    metrics=_visit_metrics(
                        316,
                        316,
                        0,
                        100,
                    ),
                ),
            ),
        )

        rows = _client_sales_rows(
            sales,
            visits=visits,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0].client_normalized,
            "4300201 الإخوة قريبع",
        )
        self.assertEqual(
            rows[0].visit_record_count,
            316,
        )
        self.assertEqual(
            rows[0].visited_record_count,
            316,
        )
        self.assertEqual(
            rows[0].not_visited_record_count,
            0,
        )

    @patch(
        "apps.dashboard.manager_clients._brand_names",
        return_value={1: "BIFA"},
    )
    def test_does_not_enrich_ambiguous_sales_identity(
        self,
        _brand_names,
    ):
        sales = SimpleNamespace(
            by_brand_client=(
                BrandClientSalesTotal(
                    brand_id=1,
                    client="431030 فاتح",
                    client_normalized="431030 فاتح",
                    metrics=_sales_metrics(100),
                ),
                BrandClientSalesTotal(
                    brand_id=1,
                    client="431245 فاتح",
                    client_normalized="431245 فاتح",
                    metrics=_sales_metrics(200),
                ),
            ),
            by_brand_truck_client=(
                BrandTruckClientSalesTotal(
                    brand_id=1,
                    truck_id=9,
                    client="431030 فاتح",
                    client_normalized="431030 فاتح",
                    metrics=_sales_metrics(100),
                ),
                BrandTruckClientSalesTotal(
                    brand_id=1,
                    truck_id=9,
                    client="431245 فاتح",
                    client_normalized="431245 فاتح",
                    metrics=_sales_metrics(200),
                ),
            ),
        )

        visits = SimpleNamespace(
            by_brand_truck_client=(
                BrandTruckClientVisitTotal(
                    brand_id=1,
                    truck_id=9,
                    client="فاتح",
                    client_normalized="فاتح",
                    metrics=_visit_metrics(
                        12,
                        10,
                        2,
                        5,
                    ),
                ),
            ),
        )

        rows = _client_sales_rows(
            sales,
            visits=visits,
        )

        self.assertEqual(len(rows), 2)
        self.assertTrue(
            all(
                row.visit_record_count == 0
                and row.visited_record_count == 0
                and row.not_visited_record_count == 0
                for row in rows
            )
        )



