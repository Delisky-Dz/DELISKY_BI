from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analytics.services.report_rows import (
    AnalyticalRowError,
    ChargementAnalyticalRow,
    ItemAnalyticalRow,
    OpeningStockAnalyticalRow,
    PosAnalyticalRow,
    SalesAnalyticalRow,
    parse_accepted_row,
    parse_chargement_row,
    parse_item_row,
    parse_opening_stock_row,
    parse_pos_row,
    parse_sales_row,
)
from apps.imports.models import (
    DistributionBrand,
    ImportBatch,
    ImportBatchStatus,
    ImportReportType,
    ImportRow,
    ImportRowStatus,
)


class ReportRowsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()

        cls.user = user_model.objects.create_user(
            username="report-rows-test-user",
            password="test-password-only",
        )

        cls.brand = DistributionBrand.objects.create(
            code="ANALYTICS_TEST",
            name="Analytics Test Brand",
        )

    def create_batch(
        self,
        sequence,
        report_type,
        *,
        status=ImportBatchStatus.APPROVED,
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 7),
        accepted_rows=1,
        excluded_rows=0,
    ):
        if report_type == ImportReportType.OPENING_STOCK:
            period_end = period_start

        return ImportBatch.objects.create(
            brand=self.brand,
            report_type=report_type,
            period_start=period_start,
            period_end=period_end,
            original_filename=f"TEST-{sequence}.xlsx",
            worksheet_name="Sheet1",
            file_size_bytes=100,
            file_sha256=f"{sequence:064x}",
            content_sha256=f"{sequence + 1000:064x}",
            status=status,
            total_rows=accepted_rows + excluded_rows,
            accepted_rows=accepted_rows,
            excluded_rows=excluded_rows,
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
        status=ImportRowStatus.ACCEPTED,
    ):
        return ImportRow.objects.create(
            batch=batch,
            excel_row_number=2,
            status=status,
            raw_data={},
            cleaned_data=cleaned_data,
            issues=[],
            row_sha256=f"{sequence + 5000:064x}",
        )

    def base_cleaned_data(self):
        return {
            "van": "TEST-VAN-001",
            "van_normalized": "test-van-001",
        }

    def test_parses_opening_stock_row(self):
        batch = self.create_batch(
            1,
            ImportReportType.OPENING_STOCK,
        )
        row = self.create_row(
            batch,
            1,
            {
                **self.base_cleaned_data(),
                "article": "Test Product",
                "article_normalized": "test product",
                "quantity": "999",
                "total_units": "125",
            },
        )

        result = parse_opening_stock_row(row)

        self.assertIsInstance(
            result,
            OpeningStockAnalyticalRow,
        )
        self.assertEqual(
            result.quantity,
            Decimal("125"),
        )
        self.assertEqual(
            result.article_normalized,
            "test product",
        )
        self.assertEqual(
            result.brand_id,
            self.brand.pk,
        )

    def test_parses_chargement_row(self):
        batch = self.create_batch(
            2,
            ImportReportType.CHARGEMENT,
        )
        row = self.create_row(
            batch,
            2,
            {
                **self.base_cleaned_data(),
                "article": "Loaded Product",
                "article_normalized": "loaded product",
                "quantity": "999",
                "total_units": "80",
            },
        )

        result = parse_chargement_row(row)

        self.assertIsInstance(
            result,
            ChargementAnalyticalRow,
        )
        self.assertEqual(
            result.quantity,
            Decimal("80"),
        )

    def test_parses_chargement_datetime_when_available(self):
        batch = self.create_batch(
            101,
            ImportReportType.CHARGEMENT,
        )

        row = self.create_row(
            batch,
            101,
            {
                **self.base_cleaned_data(),
                "article": "Loaded Product",
                "article_normalized": "loaded product",
                "total_units": "20",
                "chargement_datetime": (
                    "2026-07-04T10:30:45"
                ),
            },
        )

        result = parse_chargement_row(row)

        self.assertEqual(
            result.chargement_datetime,
            datetime(2026, 7, 4, 10, 30, 45),
        )


    def test_parses_negative_chargement_return_row(self):
        batch = self.create_batch(
            102,
            ImportReportType.CHARGEMENT,
        )

        row = self.create_row(
            batch,
            102,
            {
                **self.base_cleaned_data(),
                "article": "Returned Product",
                "article_normalized": "returned product",
                "total_units": "-20",
            },
        )

        result = parse_chargement_row(row)

        self.assertIsInstance(
            result,
            ChargementAnalyticalRow,
        )
        self.assertEqual(
            result.quantity,
            Decimal("-20"),
        )

    def test_parses_sales_row(self):
        batch = self.create_batch(
            3,
            ImportReportType.SALES,
        )
        row = self.create_row(
            batch,
            3,
            {
                **self.base_cleaned_data(),
                "sale_datetime": "2026-07-04T10:30:45",
                "client": "Test Client",
                "client_normalized": "test client",
                "total": "1250.75",
                "region": "Test Region",
                "region_normalized": "test region",
            },
        )

        result = parse_sales_row(row)

        self.assertIsInstance(
            result,
            SalesAnalyticalRow,
        )
        self.assertEqual(
            result.sale_datetime,
            datetime(2026, 7, 4, 10, 30, 45),
        )
        self.assertEqual(
            result.total,
            Decimal("1250.75"),
        )
        self.assertEqual(
            result.client_normalized,
            "test client",
        )
        self.assertEqual(
            result.region_normalized,
            "test region",
        )

    def test_parses_negative_sales_return_row(self):
        batch = self.create_batch(
            103,
            ImportReportType.SALES,
        )

        row = self.create_row(
            batch,
            103,
            {
                **self.base_cleaned_data(),
                "sale_datetime": "2026-07-04T10:30:45",
                "client": "Return Client",
                "client_normalized": "return client",
                "total": "-1946.67",
                "region": "Test Region",
                "region_normalized": "test region",
            },
        )

        result = parse_sales_row(row)

        self.assertIsInstance(
            result,
            SalesAnalyticalRow,
        )

        self.assertEqual(
            result.total,
            Decimal("-1946.67"),
        )

    def test_parses_item_row_at_period_level(self):
        batch = self.create_batch(
            4,
            ImportReportType.ITEMS,
        )
        row = self.create_row(
            batch,
            4,
            {
                **self.base_cleaned_data(),
                "article": "Sold Product",
                "article_normalized": "sold product",
                "quantity_sold": "999",
                "total_units": "12",
                "client": "Item Client",
                "client_normalized": "item client",
            },
        )

        result = parse_item_row(row)

        self.assertIsInstance(
            result,
            ItemAnalyticalRow,
        )
        self.assertEqual(
            result.quantity_sold,
            Decimal("12"),
        )
        self.assertEqual(
            result.period_start,
            date(2026, 7, 1),
        )
        self.assertEqual(
            result.period_end,
            date(2026, 7, 7),
        )

    def test_parses_pos_row(self):
        batch = self.create_batch(
            5,
            ImportReportType.POS,
        )
        row = self.create_row(
            batch,
            5,
            {
                **self.base_cleaned_data(),
                "client": "Visited Client",
                "client_normalized": "visited client",
                "visit_date": "2026-07-05",
                "ignoration_message": None,
                "ignoration_cause": "Closed",
            },
        )

        result = parse_pos_row(row)

        self.assertIsInstance(
            result,
            PosAnalyticalRow,
        )
        self.assertEqual(
            result.visit_date,
            date(2026, 7, 5),
        )
        self.assertIsNone(
            result.ignoration_message,
        )
        self.assertEqual(
            result.ignoration_cause,
            "Closed",
        )

    def test_generic_parser_dispatches_by_report_type(self):
        batch = self.create_batch(
            6,
            ImportReportType.ITEMS,
        )
        row = self.create_row(
            batch,
            6,
            {
                **self.base_cleaned_data(),
                "article": "Dispatch Product",
                "article_normalized": "dispatch product",
                "total_units": "3",
                "client": "Dispatch Client",
                "client_normalized": "dispatch client",
            },
        )

        result = parse_accepted_row(row)

        self.assertIsInstance(
            result,
            ItemAnalyticalRow,
        )

    def test_rejects_row_from_non_approved_batch(self):
        batch = self.create_batch(
            7,
            ImportReportType.SALES,
            status=ImportBatchStatus.REVIEWED,
        )
        row = self.create_row(
            batch,
            7,
            {
                **self.base_cleaned_data(),
                "sale_datetime": "2026-07-03T09:00:00",
                "client": "Test Client",
                "client_normalized": "test client",
                "total": "100",
                "region": None,
                "region_normalized": None,
            },
        )

        with self.assertRaises(
            AnalyticalRowError
        ) as context:
            parse_sales_row(row)

        self.assertEqual(
            context.exception.code,
            "batch_not_approved",
        )

    def test_rejects_non_accepted_row(self):
        batch = self.create_batch(
            8,
            ImportReportType.ITEMS,
            accepted_rows=0,
            excluded_rows=1,
        )
        row = self.create_row(
            batch,
            8,
            {
                **self.base_cleaned_data(),
                "article": "Excluded Product",
                "article_normalized": "excluded product",
                "total_units": "-2",
                "client": "Test Client",
                "client_normalized": "test client",
            },
            status=ImportRowStatus.EXCLUDED,
        )

        with self.assertRaises(
            AnalyticalRowError
        ) as context:
            parse_item_row(row)

        self.assertEqual(
            context.exception.code,
            "row_not_accepted",
        )

    def test_rejects_report_type_mismatch(self):
        batch = self.create_batch(
            9,
            ImportReportType.ITEMS,
        )
        row = self.create_row(
            batch,
            9,
            {
                **self.base_cleaned_data(),
                "article": "Test Product",
                "article_normalized": "test product",
                "total_units": "2",
                "client": "Test Client",
                "client_normalized": "test client",
            },
        )

        with self.assertRaises(
            AnalyticalRowError
        ) as context:
            parse_sales_row(row)

        self.assertEqual(
            context.exception.code,
            "report_type_mismatch",
        )

    def test_rejects_negative_value_in_accepted_row(self):
        batch = self.create_batch(
            10,
            ImportReportType.ITEMS,
        )
        row = self.create_row(
            batch,
            10,
            {
                **self.base_cleaned_data(),
                "article": "Invalid Product",
                "article_normalized": "invalid product",
                "total_units": "-1",
                "client": "Test Client",
                "client_normalized": "test client",
            },
        )

        with self.assertRaises(
            AnalyticalRowError
        ) as context:
            parse_item_row(row)

        error = context.exception

        self.assertEqual(
            error.code,
            "negative_analytical_value",
        )
        self.assertEqual(
            error.field_name,
            "total_units",
        )

    def test_rejects_date_outside_batch_period(self):
        batch = self.create_batch(
            11,
            ImportReportType.SALES,
        )
        row = self.create_row(
            batch,
            11,
            {
                **self.base_cleaned_data(),
                "sale_datetime": "2026-07-15T10:00:00",
                "client": "Test Client",
                "client_normalized": "test client",
                "total": "200",
                "region": None,
                "region_normalized": None,
            },
        )

        with self.assertRaises(
            AnalyticalRowError
        ) as context:
            parse_sales_row(row)

        self.assertEqual(
            context.exception.code,
            "date_outside_batch_period",
        )
        self.assertEqual(
            context.exception.field_name,
            "sale_datetime",
        )

    def test_missing_required_value_has_row_context(self):
        batch = self.create_batch(
            12,
            ImportReportType.POS,
        )
        row = self.create_row(
            batch,
            12,
            {
                **self.base_cleaned_data(),
                "client": None,
                "client_normalized": None,
                "visit_date": "2026-07-04",
                "ignoration_message": None,
                "ignoration_cause": None,
            },
        )

        with self.assertRaises(
            AnalyticalRowError
        ) as context:
            parse_pos_row(row)

        error = context.exception

        self.assertEqual(
            error.code,
            "missing_text",
        )
        self.assertEqual(
            error.field_name,
            "client",
        )
        self.assertEqual(
            error.row_id,
            row.pk,
        )
        self.assertEqual(
            error.batch_id,
            batch.pk,
        )
        self.assertEqual(
            error.excel_row_number,
            2,
        )
