from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analytics.services.report_rows import parse_item_row
from apps.imports.models import (
    DistributionBrand,
    ImportBatch,
    ImportBatchStatus,
    ImportReportType,
    ImportRow,
    ImportRowStatus,
)


class ItemDetailAnalyticalRowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="item-detail-row-user",
            password="test-password-only",
        )
        cls.brand = DistributionBrand.objects.create(
            code="ITEM_DETAIL_ROW",
            name="Item Detail Row Brand",
        )

    def create_row(self, *, sale_datetime=None):
        batch = ImportBatch.objects.create(
            brand=self.brand,
            report_type=ImportReportType.ITEMS,
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
            original_filename="detail.xlsx",
            worksheet_name="Sheet1",
            file_size_bytes=100,
            file_sha256="1" * 64,
            content_sha256="2" * 64,
            status=ImportBatchStatus.APPROVED,
            total_rows=1,
            accepted_rows=1,
            uploaded_by=self.user,
        )
        cleaned = {
            "van": "BIFA LIV03",
            "van_normalized": "bifa liv03",
            "article": "Product",
            "article_normalized": "product",
            "total_units": "10",
            "client": "Client",
            "client_normalized": "client",
        }
        if sale_datetime is not None:
            cleaned["sale_datetime"] = sale_datetime
        return ImportRow.objects.create(
            batch=batch,
            excel_row_number=2,
            status=ImportRowStatus.ACCEPTED,
            raw_data={},
            cleaned_data=cleaned,
            issues=[],
            row_sha256="3" * 64,
        )

    def test_item_row_exposes_optional_sale_datetime(self):
        expected = datetime(2026, 6, 15, 10, 30)
        item = parse_item_row(self.create_row(sale_datetime=expected))
        self.assertEqual(item.sale_datetime, expected)

    def test_legacy_item_row_without_sale_datetime_remains_supported(self):
        item = parse_item_row(self.create_row())
        self.assertIsNone(item.sale_datetime)
