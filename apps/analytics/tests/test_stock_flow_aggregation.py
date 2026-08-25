from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analytics.services.stock_flow_aggregation import (
    StockFlowAttributionStage,
    aggregate_chargement,
    aggregate_opening_stock,
    aggregate_stock_flow,
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


class StockFlowAggregationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()

        cls.user = user_model.objects.create_user(
            username="stock-flow-test-user",
            password="test-password-only",
        )

        cls.first_brand = DistributionBrand.objects.create(
            code="STOCK_TEST_A",
            name="Stock Test Brand A",
        )
        cls.second_brand = DistributionBrand.objects.create(
            code="STOCK_TEST_B",
            name="Stock Test Brand B",
        )

    def create_truck(self, sequence, code):
        return Truck.objects.create(
            internal_code=code,
            registration_number=f"STOCK-REG-{sequence}",
            brand="TEST TRUCK BRAND",
            model="TEST MODEL",
        )

    def create_worker(self, sequence):
        return Worker.objects.create(
            employee_code=f"STOCK-WORKER-{sequence}",
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
        report_type,
        *,
        brand=None,
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 7),
        accepted_rows=1,
    ):
        if report_type == ImportReportType.OPENING_STOCK:
            period_end = period_start

        return ImportBatch.objects.create(
            brand=brand or self.first_brand,
            report_type=report_type,
            period_start=period_start,
            period_end=period_end,
            original_filename=f"STOCK-FLOW-{sequence}.xlsx",
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

    def create_quantity_row(
        self,
        batch,
        sequence,
        *,
        van,
        article,
        article_normalized,
        quantity,
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
                "total_units": quantity,
            },
            issues=[],
            row_sha256=f"{sequence + 30000:064x}",
        )

    def test_opening_stock_and_chargement_remain_separate(self):
        truck = self.create_truck(
            1,
            "STOCK-VAN-001",
        )
        worker = self.create_worker(1)

        self.create_assignment(
            truck=truck,
            worker=worker,
        )

        opening_batch = self.create_batch(
            1,
            ImportReportType.OPENING_STOCK,
        )
        chargement_batch = self.create_batch(
            2,
            ImportReportType.CHARGEMENT,
        )

        self.create_quantity_row(
            opening_batch,
            1,
            van="STOCK-VAN-001",
            article="Test Product",
            article_normalized="test product",
            quantity="100",
        )
        self.create_quantity_row(
            chargement_batch,
            2,
            van="STOCK-VAN-001",
            article="Test Product",
            article_normalized="test product",
            quantity="30",
        )

        opening_result = aggregate_opening_stock()
        chargement_result = aggregate_chargement()

        self.assertEqual(
            opening_result.report_type,
            ImportReportType.OPENING_STOCK,
        )
        self.assertEqual(
            chargement_result.report_type,
            ImportReportType.CHARGEMENT,
        )
        self.assertEqual(
            opening_result.overall.total_quantity,
            Decimal("100"),
        )
        self.assertEqual(
            chargement_result.overall.total_quantity,
            Decimal("30"),
        )
        self.assertEqual(
            opening_result.by_worker[0].worker_id,
            worker.pk,
        )
        self.assertEqual(
            chargement_result.by_truck[0].truck_id,
            truck.pk,
        )

    def test_multiple_chargement_batches_are_summed(self):
        truck = self.create_truck(
            2,
            "STOCK-VAN-002",
        )
        worker = self.create_worker(2)

        self.create_assignment(
            truck=truck,
            worker=worker,
        )

        first_batch = self.create_batch(
            10,
            ImportReportType.CHARGEMENT,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 1),
        )
        second_batch = self.create_batch(
            11,
            ImportReportType.CHARGEMENT,
            period_start=date(2026, 7, 2),
            period_end=date(2026, 7, 2),
        )

        self.create_quantity_row(
            first_batch,
            10,
            van="STOCK-VAN-002",
            article="Loaded Product",
            article_normalized="loaded product",
            quantity="20.50",
        )
        self.create_quantity_row(
            second_batch,
            11,
            van="STOCK-VAN-002",
            article="Loaded Product",
            article_normalized="loaded product",
            quantity="14.25",
        )

        result = aggregate_chargement()

        self.assertEqual(
            result.overall.total_quantity,
            Decimal("34.75"),
        )
        self.assertEqual(
            result.overall.record_count,
            2,
        )
        self.assertEqual(
            result.by_brand_product[0].metrics.total_quantity,
            Decimal("34.75"),
        )

    def test_chargement_returns_reduce_net_quantity(self):
        truck = self.create_truck(
            202,
            "STOCK-VAN-202",
        )

        worker = self.create_worker(202)

        self.create_assignment(
            truck=truck,
            worker=worker,
        )

        batch = self.create_batch(
            202,
            ImportReportType.CHARGEMENT,
            accepted_rows=2,
        )

        self.create_quantity_row(
            batch,
            202,
            van="STOCK-VAN-202",
            article="Return Test Product",
            article_normalized="return test product",
            quantity="100",
            excel_row_number=2,
        )

        self.create_quantity_row(
            batch,
            203,
            van="STOCK-VAN-202",
            article="Return Test Product",
            article_normalized="return test product",
            quantity="-20",
            excel_row_number=3,
        )

        result = aggregate_chargement()

        self.assertEqual(
            result.overall.total_quantity,
            Decimal("80"),
        )

        self.assertEqual(
            result.overall.record_count,
            2,
        )

        self.assertEqual(
            result.overall.positive_quantity_record_count,
            1,
        )

        self.assertEqual(
            result.overall.negative_quantity_record_count,
            1,
        )

        self.assertEqual(
            result.overall.zero_quantity_record_count,
            0,
        )

        self.assertEqual(
            result.by_brand_product[0]
            .metrics.total_quantity,
            Decimal("80"),
        )

    def test_normalized_product_names_are_grouped(self):
        truck = self.create_truck(
            3,
            "STOCK-VAN-003",
        )
        worker = self.create_worker(3)

        self.create_assignment(
            truck=truck,
            worker=worker,
        )

        batch = self.create_batch(
            20,
            ImportReportType.CHARGEMENT,
            accepted_rows=2,
        )

        self.create_quantity_row(
            batch,
            20,
            van="STOCK-VAN-003",
            article="Product One",
            article_normalized="product one",
            quantity="5",
            excel_row_number=2,
        )
        self.create_quantity_row(
            batch,
            21,
            van="STOCK-VAN-003",
            article="PRODUCT ONE",
            article_normalized="product one",
            quantity="7",
            excel_row_number=3,
        )

        result = aggregate_chargement()

        self.assertEqual(
            len(result.by_brand_product),
            1,
        )
        self.assertEqual(
            result.by_brand_product[0].metrics.total_quantity,
            Decimal("12"),
        )
        self.assertEqual(
            result.by_brand_truck_product[0].truck_id,
            truck.pk,
        )
        self.assertEqual(
            result.by_brand_worker_product[0].worker_id,
            worker.pk,
        )

    def test_unknown_truck_keeps_brand_and_product_totals(self):
        batch = self.create_batch(
            30,
            ImportReportType.CHARGEMENT,
        )

        row = self.create_quantity_row(
            batch,
            30,
            van="UNKNOWN-STOCK-VAN",
            article="Unknown Truck Product",
            article_normalized="unknown truck product",
            quantity="40",
        )

        result = aggregate_chargement()

        self.assertEqual(
            result.overall.total_quantity,
            Decimal("40"),
        )
        self.assertEqual(
            result.by_brand_product[0].metrics.total_quantity,
            Decimal("40"),
        )
        self.assertEqual(result.by_truck, ())
        self.assertEqual(result.by_worker, ())

        issue = result.attribution_issues[0]

        self.assertEqual(
            issue.stage,
            StockFlowAttributionStage.TRUCK,
        )
        self.assertEqual(
            issue.code,
            "TRUCK_NOT_FOUND",
        )
        self.assertEqual(
            issue.import_row_id,
            row.pk,
        )

    def test_worker_change_does_not_attribute_whole_period(self):
        truck = self.create_truck(
            4,
            "STOCK-VAN-004",
        )
        first_worker = self.create_worker(4)
        second_worker = self.create_worker(5)

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

        batch = self.create_batch(
            40,
            ImportReportType.CHARGEMENT,
        )

        self.create_quantity_row(
            batch,
            40,
            van="STOCK-VAN-004",
            article="Changed Worker Product",
            article_normalized="changed worker product",
            quantity="50",
        )

        result = aggregate_chargement()

        self.assertEqual(
            result.by_truck[0].metrics.total_quantity,
            Decimal("50"),
        )
        self.assertEqual(result.by_worker, ())
        self.assertEqual(
            result.by_brand_worker_product,
            (),
        )

        issue = result.attribution_issues[0]

        self.assertEqual(
            issue.stage,
            StockFlowAttributionStage.WORKER,
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

    def test_dated_chargement_uses_worker_assignment_for_row_date(self):
        truck = self.create_truck(
            405,
            "STOCK-VAN-405",
        )
        first_worker = self.create_worker(405)
        second_worker = self.create_worker(406)

        self.create_assignment(
            truck=truck,
            worker=first_worker,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
        self.create_assignment(
            truck=truck,
            worker=second_worker,
            start_date=date(2026, 7, 4),
            end_date=date(2026, 7, 7),
        )

        batch = self.create_batch(
            405,
            ImportReportType.CHARGEMENT,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
        )

        row = self.create_quantity_row(
            batch,
            405,
            van="STOCK-VAN-405",
            article="Dated Chargement Product",
            article_normalized="dated chargement product",
            quantity="50",
        )

        cleaned_data = dict(row.cleaned_data)
        cleaned_data["chargement_datetime"] = (
            "2026-07-05T10:30:00"
        )
        row.cleaned_data = cleaned_data
        row.save(update_fields=["cleaned_data"])

        result = aggregate_chargement()

        self.assertEqual(
            len(result.by_worker),
            1,
        )
        self.assertEqual(
            result.by_worker[0].worker_id,
            second_worker.pk,
        )
        self.assertEqual(
            result.by_worker[0].metrics.total_quantity,
            Decimal("50"),
        )
        self.assertEqual(
            result.attribution_issues,
            (),
        )


    def test_partial_period_overlap_is_excluded(self):
        batch = self.create_batch(
            50,
            ImportReportType.CHARGEMENT,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
        )

        self.create_quantity_row(
            batch,
            50,
            van="UNKNOWN-PARTIAL-VAN",
            article="Partial Product",
            article_normalized="partial product",
            quantity="60",
        )

        result = aggregate_chargement(
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
            result.overall.total_quantity,
            Decimal("0"),
        )

    def test_zero_quantity_is_counted_separately(self):
        truck = self.create_truck(
            6,
            "STOCK-VAN-006",
        )
        worker = self.create_worker(6)

        self.create_assignment(
            truck=truck,
            worker=worker,
        )

        batch = self.create_batch(
            60,
            ImportReportType.CHARGEMENT,
        )

        self.create_quantity_row(
            batch,
            60,
            van="STOCK-VAN-006",
            article="Zero Product",
            article_normalized="zero product",
            quantity="0",
        )

        result = aggregate_chargement()

        self.assertEqual(
            result.overall.total_quantity,
            Decimal("0"),
        )
        self.assertEqual(
            result.overall.record_count,
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

    def test_brand_filter_excludes_other_brand(self):
        first_batch = self.create_batch(
            70,
            ImportReportType.CHARGEMENT,
            brand=self.first_brand,
        )
        second_batch = self.create_batch(
            71,
            ImportReportType.CHARGEMENT,
            brand=self.second_brand,
        )

        self.create_quantity_row(
            first_batch,
            70,
            van="UNKNOWN-FIRST-VAN",
            article="First Product",
            article_normalized="first product",
            quantity="10",
        )
        self.create_quantity_row(
            second_batch,
            71,
            van="UNKNOWN-SECOND-VAN",
            article="Second Product",
            article_normalized="second product",
            quantity="90",
        )

        result = aggregate_chargement(
            brand_id=self.first_brand.pk,
        )

        self.assertEqual(
            result.overall.total_quantity,
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

    def test_unsupported_report_type_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "Unsupported stock-flow report type",
        ):
            aggregate_stock_flow(
                ImportReportType.ITEMS,
            )

    def test_invalid_period_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "period_end cannot be before period_start",
        ):
            aggregate_chargement(
                period_start=date(2026, 7, 10),
                period_end=date(2026, 7, 1),
            )
