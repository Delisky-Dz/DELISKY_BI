from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analytics.services.items_aggregation import (
    aggregate_items,
)
from apps.analytics.services.sales_aggregation import (
    aggregate_sales,
)
from apps.imports.models import (
    DistributionBrand,
    ImportBatch,
    ImportBatchStatus,
    ImportReportType,
    ImportRow,
    ImportRowStatus,
)


class ClientPurchaseAggregationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="client-purchase-aggregation-test",
            password="test-password-only",
        )

        cls.brand = DistributionBrand.objects.create(
            code="CLIENT_PURCHASE_TEST",
            name="Client Purchase Test",
        )

    def create_batch(
        self,
        sequence,
        report_type,
        *,
        accepted_rows=2,
    ):
        return ImportBatch.objects.create(
            brand=self.brand,
            report_type=report_type,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
            original_filename=(
                f"CLIENT-PURCHASE-{sequence}.xlsx"
            ),
            worksheet_name="Sheet1",
            file_size_bytes=100,
            file_sha256=f"{sequence:064x}",
            content_sha256=(
                f"{sequence + 10000:064x}"
            ),
            status=ImportBatchStatus.APPROVED,
            total_rows=accepted_rows,
            accepted_rows=accepted_rows,
            excluded_rows=0,
            stopped_rows=0,
            warning_count=0,
            error_count=0,
            review_summary={},
            uploaded_by=self.user,
        )

    def create_row(
        self,
        batch,
        sequence,
        cleaned_data,
        *,
        excel_row_number,
    ):
        return ImportRow.objects.create(
            batch=batch,
            excel_row_number=excel_row_number,
            status=ImportRowStatus.ACCEPTED,
            raw_data={},
            cleaned_data=cleaned_data,
            issues=[],
            row_sha256=(
                f"{sequence + 30000:064x}"
            ),
        )

    def test_items_aggregate_by_client_and_product(self):
        batch = self.create_batch(
            1,
            ImportReportType.ITEMS,
        )

        self.create_row(
            batch,
            1,
            {
                "van": "UNKNOWN-VAN",
                "van_normalized": "unknown-van",
                "article": "Product A",
                "article_normalized": "product a",
                "total_units": "20",
                "client": "Client Alpha",
                "client_normalized": "client alpha",
            },
            excel_row_number=2,
        )

        self.create_row(
            batch,
            2,
            {
                "van": "UNKNOWN-VAN",
                "van_normalized": "unknown-van",
                "article": "Product B",
                "article_normalized": "product b",
                "total_units": "30",
                "client": "CLIENT ALPHA",
                "client_normalized": "client alpha",
            },
            excel_row_number=3,
        )

        result = aggregate_items()

        self.assertEqual(
            len(result.by_brand_client),
            1,
        )

        client = result.by_brand_client[0]

        self.assertEqual(
            client.client_normalized,
            "client alpha",
        )
        self.assertEqual(
            client.metrics.quantity_sold,
            Decimal("50"),
        )
        self.assertEqual(
            client.metrics.item_record_count,
            2,
        )

        self.assertEqual(
            len(result.by_brand_client_product),
            2,
        )

        quantities = {
            item.article_normalized:
            item.metrics.quantity_sold
            for item
            in result.by_brand_client_product
        }

        self.assertEqual(
            quantities,
            {
                "product a": Decimal("20"),
                "product b": Decimal("30"),
            },
        )

    def test_sales_aggregate_by_client(self):
        batch = self.create_batch(
            2,
            ImportReportType.SALES,
        )

        self.create_row(
            batch,
            10,
            {
                "van": "UNKNOWN-VAN",
                "van_normalized": "unknown-van",
                "sale_datetime": (
                    "2026-07-02T09:30:00"
                ),
                "client": "Client Alpha",
                "client_normalized": "client alpha",
                "total": "1000",
                "region": None,
                "region_normalized": None,
            },
            excel_row_number=2,
        )

        self.create_row(
            batch,
            11,
            {
                "van": "UNKNOWN-VAN",
                "van_normalized": "unknown-van",
                "sale_datetime": (
                    "2026-07-05T11:00:00"
                ),
                "client": "CLIENT ALPHA",
                "client_normalized": "client alpha",
                "total": "1500",
                "region": None,
                "region_normalized": None,
            },
            excel_row_number=3,
        )

        result = aggregate_sales()

        self.assertEqual(
            len(result.by_brand_client),
            1,
        )

        client = result.by_brand_client[0]

        self.assertEqual(
            client.client_normalized,
            "client alpha",
        )
        self.assertEqual(
            client.metrics.total_sales,
            Decimal("2500"),
        )
        self.assertEqual(
            client.metrics.sale_record_count,
            2,
        )
