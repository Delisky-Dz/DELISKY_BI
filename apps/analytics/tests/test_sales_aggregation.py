from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analytics.services.sales_aggregation import (
    SalesAttributionStage,
    aggregate_sales,
)
from apps.fleet.models import Truck, TruckCrewAssignment
from apps.imports.models import (
    DistributionBrand,
    ImportBatch,
    ImportBatchStatus,
    ImportReportType,
    ImportRow,
    ImportRowStatus,
)
from apps.workforce.models import Worker


class SalesAggregationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()

        cls.user = user_model.objects.create_user(
            username="sales-aggregation-test-user",
            password="test-password-only",
        )

        cls.first_brand = DistributionBrand.objects.create(
            code="SALES_TEST_A",
            name="Sales Test Brand A",
        )
        cls.second_brand = DistributionBrand.objects.create(
            code="SALES_TEST_B",
            name="Sales Test Brand B",
        )

    def create_truck(self, sequence, code):
        return Truck.objects.create(
            internal_code=code,
            registration_number=f"SALES-REG-{sequence}",
            brand="TEST TRUCK BRAND",
            model="TEST MODEL",
        )

    def create_worker(self, sequence):
        return Worker.objects.create(
            employee_code=f"SALES-WORKER-{sequence}",
            first_name="Test",
            last_name=f"Worker {sequence}",
        )

    def create_assignment(
        self,
        *,
        truck,
        worker,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
    ):
        return TruckCrewAssignment.objects.create(
            truck=truck,
            worker=worker,
            crew_role=(
                TruckCrewAssignment.CrewRole.SELLER
            ),
            is_primary_seller=True,
            start_date=start_date,
            end_date=end_date,
        )

    def create_batch(
        self,
        sequence,
        *,
        brand=None,
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 7),
        accepted_rows=1,
    ):
        return ImportBatch.objects.create(
            brand=brand or self.first_brand,
            report_type=ImportReportType.SALES,
            period_start=period_start,
            period_end=period_end,
            original_filename=f"SALES-TEST-{sequence}.xlsx",
            worksheet_name="Sheet1",
            file_size_bytes=100,
            file_sha256=f"{sequence:064x}",
            content_sha256=f"{sequence + 10000:064x}",
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

    def create_sales_row(
        self,
        batch,
        sequence,
        *,
        van,
        sale_datetime,
        total,
        excel_row_number=2,
    ):
        return ImportRow.objects.create(
            batch=batch,
            excel_row_number=excel_row_number,
            status=ImportRowStatus.ACCEPTED,
            raw_data={},
            cleaned_data={
                "van": van,
                "van_normalized": van.casefold(),
                "sale_datetime": sale_datetime,
                "client": f"Test Client {sequence}",
                "client_normalized": (
                    f"test client {sequence}"
                ),
                "total": total,
                "region": "Test Region",
                "region_normalized": "test region",
            },
            issues=[],
            row_sha256=f"{sequence + 30000:064x}",
        )

    def test_aggregates_sales_by_all_supported_dimensions(self):
        truck = self.create_truck(
            1,
            "SALES-VAN-001",
        )
        worker = self.create_worker(1)

        self.create_assignment(
            truck=truck,
            worker=worker,
        )

        batch = self.create_batch(
            1,
            accepted_rows=2,
        )

        self.create_sales_row(
            batch,
            1,
            van="SALES-VAN-001",
            sale_datetime="2026-07-03T09:00:00",
            total="100.10",
            excel_row_number=2,
        )
        self.create_sales_row(
            batch,
            2,
            van="sales-van-001",
            sale_datetime="2026-07-04T10:30:00",
            total="200.20",
            excel_row_number=3,
        )

        result = aggregate_sales()

        self.assertEqual(
            result.overall.total_sales,
            Decimal("300.30"),
        )
        self.assertEqual(
            result.overall.sale_record_count,
            2,
        )
        self.assertEqual(
            result.overall.positive_sale_record_count,
            2,
        )
        self.assertEqual(
            result.overall.zero_total_record_count,
            0,
        )

        self.assertEqual(
            result.by_brand[0].brand_id,
            self.first_brand.pk,
        )
        self.assertEqual(
            result.by_brand[0].metrics.total_sales,
            Decimal("300.30"),
        )

        self.assertEqual(
            result.by_truck[0].truck_id,
            truck.pk,
        )
        self.assertEqual(
            result.by_worker[0].worker_id,
            worker.pk,
        )

        combined = result.by_brand_truck_worker[0]

        self.assertEqual(
            combined.brand_id,
            self.first_brand.pk,
        )
        self.assertEqual(
            combined.truck_id,
            truck.pk,
        )
        self.assertEqual(
            combined.worker_id,
            worker.pk,
        )
        self.assertEqual(
            combined.metrics.total_sales,
            Decimal("300.30"),
        )

        self.assertFalse(
            result.has_attribution_issues
        )

    def test_exact_sale_date_filters_rows_inside_batch(self):
        truck = self.create_truck(
            2,
            "SALES-VAN-002",
        )
        worker = self.create_worker(2)

        self.create_assignment(
            truck=truck,
            worker=worker,
        )

        batch = self.create_batch(
            2,
            accepted_rows=3,
        )

        self.create_sales_row(
            batch,
            10,
            van="SALES-VAN-002",
            sale_datetime="2026-07-01T08:00:00",
            total="10",
            excel_row_number=2,
        )
        self.create_sales_row(
            batch,
            11,
            van="SALES-VAN-002",
            sale_datetime="2026-07-03T08:00:00",
            total="20",
            excel_row_number=3,
        )
        self.create_sales_row(
            batch,
            12,
            van="SALES-VAN-002",
            sale_datetime="2026-07-07T08:00:00",
            total="30",
            excel_row_number=4,
        )

        result = aggregate_sales(
            period_start=date(2026, 7, 3),
            period_end=date(2026, 7, 3),
        )

        self.assertEqual(
            result.source_row_count,
            3,
        )
        self.assertEqual(
            result.included_row_count,
            1,
        )
        self.assertEqual(
            result.outside_requested_period_count,
            2,
        )
        self.assertEqual(
            result.overall.total_sales,
            Decimal("20"),
        )

    def test_daily_sales_groups_same_day_and_orders_dates(
        self,
    ):
        batch = self.create_batch(
            90,
            accepted_rows=3,
        )

        self.create_sales_row(
            batch,
            900,
            van="UNKNOWN-DAILY-VAN",
            sale_datetime="2026-07-04T09:00:00",
            total="50",
            excel_row_number=2,
        )
        self.create_sales_row(
            batch,
            901,
            van="UNKNOWN-DAILY-VAN",
            sale_datetime="2026-07-03T10:00:00",
            total="100",
            excel_row_number=3,
        )
        self.create_sales_row(
            batch,
            902,
            van="UNKNOWN-DAILY-VAN",
            sale_datetime="2026-07-03T11:00:00",
            total="0",
            excel_row_number=4,
        )

        result = aggregate_sales()

        self.assertEqual(
            [
                item.sale_date
                for item in result.by_date
            ],
            [
                date(2026, 7, 3),
                date(2026, 7, 4),
            ],
        )

        first_day = result.by_date[0]

        self.assertEqual(
            first_day.metrics.total_sales,
            Decimal("100"),
        )
        self.assertEqual(
            first_day.metrics.sale_record_count,
            2,
        )
        self.assertEqual(
            first_day.metrics.positive_sale_record_count,
            1,
        )
        self.assertEqual(
            first_day.metrics.zero_total_record_count,
            1,
        )

        self.assertEqual(
            result.by_date[1].metrics.total_sales,
            Decimal("50"),
        )

    def test_daily_sales_respects_requested_period(
        self,
    ):
        batch = self.create_batch(
            91,
            accepted_rows=3,
        )

        self.create_sales_row(
            batch,
            910,
            van="UNKNOWN-PERIOD-VAN",
            sale_datetime="2026-07-01T08:00:00",
            total="10",
            excel_row_number=2,
        )
        self.create_sales_row(
            batch,
            911,
            van="UNKNOWN-PERIOD-VAN",
            sale_datetime="2026-07-03T08:00:00",
            total="20",
            excel_row_number=3,
        )
        self.create_sales_row(
            batch,
            912,
            van="UNKNOWN-PERIOD-VAN",
            sale_datetime="2026-07-07T08:00:00",
            total="30",
            excel_row_number=4,
        )

        result = aggregate_sales(
            period_start=date(2026, 7, 3),
            period_end=date(2026, 7, 3),
        )

        self.assertEqual(
            len(result.by_date),
            1,
        )
        self.assertEqual(
            result.by_date[0].sale_date,
            date(2026, 7, 3),
        )
        self.assertEqual(
            result.by_date[0].metrics.total_sales,
            Decimal("20"),
        )

    def test_unknown_truck_keeps_brand_and_overall_sales(self):
        batch = self.create_batch(3)

        row = self.create_sales_row(
            batch,
            20,
            van="UNKNOWN-SALES-VAN",
            sale_datetime="2026-07-04T11:00:00",
            total="500",
        )

        result = aggregate_sales()

        self.assertEqual(
            result.overall.total_sales,
            Decimal("500"),
        )
        self.assertEqual(
            result.by_brand[0].metrics.total_sales,
            Decimal("500"),
        )
        self.assertEqual(
            result.by_truck,
            (),
        )
        self.assertEqual(
            result.by_worker,
            (),
        )

        self.assertEqual(
            len(result.attribution_issues),
            1,
        )

        issue = result.attribution_issues[0]

        self.assertEqual(
            issue.stage,
            SalesAttributionStage.TRUCK,
        )
        self.assertEqual(
            issue.code,
            "TRUCK_NOT_FOUND",
        )
        self.assertEqual(
            issue.import_row_id,
            row.pk,
        )

    def test_truck_without_assignment_keeps_truck_sales(self):
        truck = self.create_truck(
            4,
            "SALES-VAN-004",
        )
        batch = self.create_batch(4)

        self.create_sales_row(
            batch,
            30,
            van="SALES-VAN-004",
            sale_datetime="2026-07-05T09:00:00",
            total="700",
        )

        result = aggregate_sales()

        self.assertEqual(
            result.overall.total_sales,
            Decimal("700"),
        )
        self.assertEqual(
            result.by_truck[0].truck_id,
            truck.pk,
        )
        self.assertEqual(
            result.by_truck[0].metrics.total_sales,
            Decimal("700"),
        )
        self.assertEqual(
            result.by_worker,
            (),
        )

        issue = result.attribution_issues[0]

        self.assertEqual(
            issue.stage,
            SalesAttributionStage.WORKER,
        )
        self.assertEqual(
            issue.code,
            "NO_ASSIGNMENT",
        )

    def test_negative_sale_is_not_counted_as_zero(
        self,
    ):
        from apps.analytics.services.sales_aggregation import (
            _SalesAccumulator,
        )

        accumulator = _SalesAccumulator()

        accumulator.add(
            Decimal("-1946.67")
        )

        metrics = accumulator.freeze()

        self.assertEqual(
            metrics.total_sales,
            Decimal("-1946.67"),
        )

        self.assertEqual(
            metrics.sale_record_count,
            1,
        )

        self.assertEqual(
            metrics.positive_sale_record_count,
            0,
        )

        self.assertEqual(
            metrics.zero_total_record_count,
            0,
        )

    def test_zero_total_sale_is_counted_separately(self):
        truck = self.create_truck(
            5,
            "SALES-VAN-005",
        )
        worker = self.create_worker(5)

        self.create_assignment(
            truck=truck,
            worker=worker,
        )

        batch = self.create_batch(5)

        self.create_sales_row(
            batch,
            40,
            van="SALES-VAN-005",
            sale_datetime="2026-07-06T12:00:00",
            total="0",
        )

        result = aggregate_sales()

        self.assertEqual(
            result.overall.total_sales,
            Decimal("0"),
        )
        self.assertEqual(
            result.overall.sale_record_count,
            1,
        )
        self.assertEqual(
            result.overall.positive_sale_record_count,
            0,
        )
        self.assertEqual(
            result.overall.zero_total_record_count,
            1,
        )

    def test_brand_filter_excludes_other_brands(self):
        first_truck = self.create_truck(
            6,
            "SALES-VAN-006",
        )
        first_worker = self.create_worker(6)

        self.create_assignment(
            truck=first_truck,
            worker=first_worker,
        )

        second_truck = self.create_truck(
            7,
            "SALES-VAN-007",
        )
        second_worker = self.create_worker(7)

        self.create_assignment(
            truck=second_truck,
            worker=second_worker,
        )

        first_batch = self.create_batch(
            6,
            brand=self.first_brand,
        )
        second_batch = self.create_batch(
            7,
            brand=self.second_brand,
        )

        self.create_sales_row(
            first_batch,
            50,
            van="SALES-VAN-006",
            sale_datetime="2026-07-03T10:00:00",
            total="100",
        )
        self.create_sales_row(
            second_batch,
            51,
            van="SALES-VAN-007",
            sale_datetime="2026-07-03T11:00:00",
            total="900",
        )

        result = aggregate_sales(
            brand_id=self.first_brand.pk,
        )

        self.assertEqual(
            result.overall.total_sales,
            Decimal("100"),
        )
        self.assertEqual(
            len(result.by_brand),
            1,
        )
        self.assertEqual(
            result.by_brand[0].brand_id,
            self.first_brand.pk,
        )

    def test_invalid_period_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "period_end cannot be before period_start",
        ):
            aggregate_sales(
                period_start=date(2026, 7, 10),
                period_end=date(2026, 7, 1),
            )

    def test_daily_brand_truck_worker_preserves_worker_mobility(
        self,
    ):
        first_truck = self.create_truck(
            80,
            "SALES-MOBILITY-080",
        )
        second_truck = self.create_truck(
            81,
            "SALES-MOBILITY-081",
        )
        worker = self.create_worker(80)

        self.create_assignment(
            truck=first_truck,
            worker=worker,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        self.create_assignment(
            truck=second_truck,
            worker=worker,
            start_date=date(2026, 7, 4),
            end_date=date(2026, 7, 7),
        )

        batch = self.create_batch(
            80,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
            accepted_rows=2,
        )

        self.create_sales_row(
            batch,
            800,
            van="SALES-MOBILITY-080",
            sale_datetime="2026-07-03T10:00:00",
            total="100",
            excel_row_number=2,
        )
        self.create_sales_row(
            batch,
            801,
            van="SALES-MOBILITY-081",
            sale_datetime="2026-07-04T10:00:00",
            total="200",
            excel_row_number=3,
        )

        result = aggregate_sales()

        self.assertEqual(
            len(result.by_date_brand_truck_worker),
            2,
        )

        before_move = (
            result.by_date_brand_truck_worker[0]
        )
        after_move = (
            result.by_date_brand_truck_worker[1]
        )

        self.assertEqual(
            before_move.sale_date,
            date(2026, 7, 3),
        )
        self.assertEqual(
            before_move.brand_id,
            self.first_brand.pk,
        )
        self.assertEqual(
            before_move.truck_id,
            first_truck.pk,
        )
        self.assertEqual(
            before_move.worker_id,
            worker.pk,
        )
        self.assertEqual(
            before_move.metrics.total_sales,
            Decimal("100"),
        )
        self.assertEqual(
            before_move.metrics.sale_record_count,
            1,
        )
        self.assertEqual(
            before_move.metrics.positive_sale_record_count,
            1,
        )

        self.assertEqual(
            after_move.sale_date,
            date(2026, 7, 4),
        )
        self.assertEqual(
            after_move.brand_id,
            self.first_brand.pk,
        )
        self.assertEqual(
            after_move.truck_id,
            second_truck.pk,
        )
        self.assertEqual(
            after_move.worker_id,
            worker.pk,
        )
        self.assertEqual(
            after_move.metrics.total_sales,
            Decimal("200"),
        )
        self.assertEqual(
            after_move.metrics.sale_record_count,
            1,
        )
        self.assertEqual(
            after_move.metrics.positive_sale_record_count,
            1,
        )

        self.assertFalse(
            result.has_attribution_issues
        )
