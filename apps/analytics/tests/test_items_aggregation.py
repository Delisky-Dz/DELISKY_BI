from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analytics.services.items_aggregation import (
    ItemsAttributionStage,
    aggregate_items,
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


class ItemsAggregationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()

        cls.user = user_model.objects.create_user(
            username="items-aggregation-test-user",
            password="test-password-only",
        )

        cls.first_brand = DistributionBrand.objects.create(
            code="ITEMS_TEST_A",
            name="Items Test Brand A",
        )
        cls.second_brand = DistributionBrand.objects.create(
            code="ITEMS_TEST_B",
            name="Items Test Brand B",
        )

    def create_truck(self, sequence, code):
        return Truck.objects.create(
            internal_code=code,
            registration_number=f"ITEMS-REG-{sequence}",
            brand="TEST TRUCK BRAND",
            model="TEST MODEL",
        )

    def create_worker(self, sequence):
        return Worker.objects.create(
            employee_code=f"ITEMS-WORKER-{sequence}",
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
            report_type=ImportReportType.ITEMS,
            period_start=period_start,
            period_end=period_end,
            original_filename=f"ITEMS-TEST-{sequence}.xlsx",
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

    def create_item_row(
        self,
        batch,
        sequence,
        *,
        van,
        article,
        article_normalized,
        quantity_sold,
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
                "article": article,
                "article_normalized": article_normalized,
                "total_units": quantity_sold,
                "client": f"Test Client {sequence}",
                "client_normalized": (
                    f"test client {sequence}"
                ),
            },
            issues=[],
            row_sha256=f"{sequence + 30000:064x}",
        )

    def test_aggregates_by_brand_truck_worker_and_product(self):
        truck = self.create_truck(
            1,
            "ITEMS-VAN-001",
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

        self.create_item_row(
            batch,
            1,
            van="ITEMS-VAN-001",
            article="Test Product",
            article_normalized="test product",
            quantity_sold="5.50",
            excel_row_number=2,
        )
        self.create_item_row(
            batch,
            2,
            van="items-van-001",
            article="TEST PRODUCT",
            article_normalized="test product",
            quantity_sold="7.25",
            excel_row_number=3,
        )

        result = aggregate_items()

        self.assertEqual(
            result.overall.quantity_sold,
            Decimal("12.75"),
        )
        self.assertEqual(
            result.overall.item_record_count,
            2,
        )
        self.assertEqual(
            result.overall.positive_quantity_record_count,
            2,
        )

        self.assertEqual(
            result.by_brand[0].brand_id,
            self.first_brand.pk,
        )
        self.assertEqual(
            result.by_truck[0].truck_id,
            truck.pk,
        )
        self.assertEqual(
            result.by_worker[0].worker_id,
            worker.pk,
        )

        self.assertEqual(
            len(result.by_brand_product),
            1,
        )
        self.assertEqual(
            result.by_brand_product[0].article_normalized,
            "test product",
        )
        self.assertEqual(
            result.by_brand_product[0].metrics.quantity_sold,
            Decimal("12.75"),
        )

        combined = result.by_brand_worker_product[0]

        self.assertEqual(
            combined.brand_id,
            self.first_brand.pk,
        )
        self.assertEqual(
            combined.worker_id,
            worker.pk,
        )
        self.assertEqual(
            combined.metrics.quantity_sold,
            Decimal("12.75"),
        )

        self.assertFalse(
            result.has_attribution_issues
        )

    def test_partial_period_overlap_is_excluded(self):
        batch = self.create_batch(
            2,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
        )

        self.create_item_row(
            batch,
            10,
            van="UNKNOWN-VAN",
            article="Period Product",
            article_normalized="period product",
            quantity_sold="20",
        )

        result = aggregate_items(
            period_start=date(2026, 7, 3),
            period_end=date(2026, 7, 7),
        )

        self.assertEqual(
            result.source_row_count,
            1,
        )
        self.assertEqual(
            result.included_row_count,
            0,
        )
        self.assertEqual(
            result.partial_overlap_excluded_count,
            1,
        )
        self.assertTrue(
            result.has_partial_period_data
        )
        self.assertEqual(
            result.overall.quantity_sold,
            Decimal("0"),
        )

    def test_worker_change_does_not_attribute_period_to_worker(self):
        truck = self.create_truck(
            3,
            "ITEMS-VAN-003",
        )
        first_worker = self.create_worker(3)
        second_worker = self.create_worker(4)

        first_assignment = self.create_assignment(
            truck=truck,
            worker=first_worker,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        second_assignment = self.create_assignment(
            truck=truck,
            worker=second_worker,
            start_date=date(2026, 7, 4),
            end_date=date(2026, 7, 7),
        )

        batch = self.create_batch(3)

        self.create_item_row(
            batch,
            20,
            van="ITEMS-VAN-003",
            article="Changed Worker Product",
            article_normalized="changed worker product",
            quantity_sold="30",
        )

        result = aggregate_items()

        self.assertEqual(
            result.overall.quantity_sold,
            Decimal("30"),
        )
        self.assertEqual(
            result.by_truck[0].metrics.quantity_sold,
            Decimal("30"),
        )
        self.assertEqual(
            result.by_worker,
            (),
        )
        self.assertEqual(
            result.by_brand_worker_product,
            (),
        )

        issue = result.attribution_issues[0]

        self.assertEqual(
            issue.stage,
            ItemsAttributionStage.WORKER,
        )
        self.assertEqual(
            issue.code,
            "MULTIPLE_ASSIGNMENTS",
        )
        self.assertEqual(
            issue.matching_entity_ids,
            tuple(
                sorted(
                    (
                        first_assignment.pk,
                        second_assignment.pk,
                    )
                )
            ),
        )

    def test_unknown_truck_keeps_brand_and_product_totals(self):
        batch = self.create_batch(4)

        row = self.create_item_row(
            batch,
            30,
            van="UNKNOWN-ITEMS-VAN",
            article="Unknown Truck Product",
            article_normalized="unknown truck product",
            quantity_sold="40",
        )

        result = aggregate_items()

        self.assertEqual(
            result.overall.quantity_sold,
            Decimal("40"),
        )
        self.assertEqual(
            result.by_brand[0].metrics.quantity_sold,
            Decimal("40"),
        )
        self.assertEqual(
            result.by_brand_product[0].metrics.quantity_sold,
            Decimal("40"),
        )
        self.assertEqual(
            result.by_truck,
            (),
        )
        self.assertEqual(
            result.by_worker,
            (),
        )

        issue = result.attribution_issues[0]

        self.assertEqual(
            issue.stage,
            ItemsAttributionStage.TRUCK,
        )
        self.assertEqual(
            issue.code,
            "TRUCK_NOT_FOUND",
        )
        self.assertEqual(
            issue.import_row_id,
            row.pk,
        )

    def test_zero_quantity_is_counted_separately(self):
        truck = self.create_truck(
            5,
            "ITEMS-VAN-005",
        )
        worker = self.create_worker(5)

        self.create_assignment(
            truck=truck,
            worker=worker,
        )

        batch = self.create_batch(5)

        self.create_item_row(
            batch,
            40,
            van="ITEMS-VAN-005",
            article="Zero Product",
            article_normalized="zero product",
            quantity_sold="0",
        )

        result = aggregate_items()

        self.assertEqual(
            result.overall.quantity_sold,
            Decimal("0"),
        )
        self.assertEqual(
            result.overall.item_record_count,
            1,
        )
        self.assertEqual(
            result.overall.positive_quantity_record_count,
            0,
        )
        self.assertEqual(
            result.overall.zero_quantity_record_count,
            1,
        )

    def test_brand_filter_excludes_other_brands(self):
        first_truck = self.create_truck(
            6,
            "ITEMS-VAN-006",
        )
        first_worker = self.create_worker(6)

        self.create_assignment(
            truck=first_truck,
            worker=first_worker,
        )

        second_truck = self.create_truck(
            7,
            "ITEMS-VAN-007",
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

        self.create_item_row(
            first_batch,
            50,
            van="ITEMS-VAN-006",
            article="First Product",
            article_normalized="first product",
            quantity_sold="10",
        )
        self.create_item_row(
            second_batch,
            51,
            van="ITEMS-VAN-007",
            article="Second Product",
            article_normalized="second product",
            quantity_sold="90",
        )

        result = aggregate_items(
            brand_id=self.first_brand.pk,
        )

        self.assertEqual(
            result.overall.quantity_sold,
            Decimal("10"),
        )
        self.assertEqual(
            len(result.by_brand),
            1,
        )
        self.assertEqual(
            result.by_brand[0].brand_id,
            self.first_brand.pk,
        )

    def test_outside_period_is_counted_for_explicit_rows(self):
        batch = self.create_batch(
            8,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
        )

        row = self.create_item_row(
            batch,
            60,
            van="UNKNOWN-OUTSIDE-VAN",
            article="Outside Product",
            article_normalized="outside product",
            quantity_sold="15",
        )

        result = aggregate_items(
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 7),
            rows=(row,),
        )

        self.assertEqual(
            result.source_row_count,
            1,
        )
        self.assertEqual(
            result.included_row_count,
            0,
        )
        self.assertEqual(
            result.outside_requested_period_count,
            1,
        )
        self.assertEqual(
            result.partial_overlap_excluded_count,
            0,
        )

    def test_invalid_period_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "period_end cannot be before period_start",
        ):
            aggregate_items(
                period_start=date(2026, 7, 10),
                period_end=date(2026, 7, 1),
            )
