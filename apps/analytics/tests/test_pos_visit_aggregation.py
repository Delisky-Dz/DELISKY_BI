from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analytics.services.pos_visit_aggregation import (
    PosAttributionStage,
    PosVisitOutcome,
    aggregate_pos_visits,
)
from apps.fleet.models import (
    Truck,
    TruckCrewAssignment,
)
from apps.imports.models import (
    DistributionBrand,
    ImportBatch,
    ImportBatchStatus,
    ImportReportType,
    ImportRow,
    ImportRowStatus,
)
from apps.workforce.models import Worker


class PosVisitAggregationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()

        cls.user = user_model.objects.create_user(
            username="pos-aggregation-test-user",
            password="test-password-only",
        )

        cls.brand = DistributionBrand.objects.create(
            code="POS_TEST",
            name="PoS Test Brand",
        )

    def create_truck(self, sequence, code):
        return Truck.objects.create(
            internal_code=code,
            registration_number=f"POS-REG-{sequence}",
            brand="TEST TRUCK BRAND",
            model="TEST MODEL",
        )

    def create_worker(self, sequence):
        return Worker.objects.create(
            employee_code=f"POS-WORKER-{sequence}",
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
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 7),
        accepted_rows=1,
    ):
        return ImportBatch.objects.create(
            brand=self.brand,
            report_type=ImportReportType.POS,
            period_start=period_start,
            period_end=period_end,
            original_filename=f"POS-TEST-{sequence}.xlsx",
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

    def create_pos_row(
        self,
        batch,
        sequence,
        *,
        van,
        client,
        client_normalized,
        visit_date,
        ignoration_message=None,
        ignoration_cause=None,
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
                "client": client,
                "client_normalized": client_normalized,
                "visit_date": visit_date,
                "ignoration_message": ignoration_message,
                "ignoration_cause": ignoration_cause,
            },
            issues=[],
            row_sha256=f"{sequence + 30000:064x}",
        )

    def test_empty_ignoration_fields_mean_visited(self):
        truck = self.create_truck(
            1,
            "POS-VAN-001",
        )
        worker = self.create_worker(1)

        self.create_assignment(
            truck=truck,
            worker=worker,
        )

        batch = self.create_batch(1)

        self.create_pos_row(
            batch,
            1,
            van="POS-VAN-001",
            client="Client One",
            client_normalized="client one",
            visit_date="2026-07-03",
        )

        result = aggregate_pos_visits()

        self.assertEqual(
            result.overall.total_record_count,
            1,
        )
        self.assertEqual(
            result.overall.visited_record_count,
            1,
        )
        self.assertEqual(
            result.overall.not_visited_record_count,
            0,
        )
        self.assertEqual(
            result.by_truck[0].truck_id,
            truck.pk,
        )
        self.assertEqual(
            result.by_worker[0].worker_id,
            worker.pk,
        )
        self.assertFalse(
            result.has_attribution_issues
        )

    def test_text_message_means_not_visited(self):
        batch = self.create_batch(2)

        self.create_pos_row(
            batch,
            2,
            van="UNKNOWN-POS-VAN",
            client="Closed Client",
            client_normalized="closed client",
            visit_date="2026-07-03",
            ignoration_message="Magasin fermé",
        )

        result = aggregate_pos_visits()

        self.assertEqual(
            result.overall.visited_record_count,
            0,
        )
        self.assertEqual(
            result.overall.not_visited_record_count,
            1,
        )
        self.assertEqual(
            result.by_brand_client[0]
            .metrics.not_visited_record_count,
            1,
        )

    def test_numeric_message_is_warning_not_non_visit(self):
        batch = self.create_batch(3)

        self.create_pos_row(
            batch,
            3,
            van="UNKNOWN-NUMERIC-VAN",
            client="Numeric Client",
            client_normalized="numeric client",
            visit_date="2026-07-03",
            ignoration_message="0",
        )

        result = aggregate_pos_visits()

        self.assertEqual(
            result.numeric_message_warning_count,
            1,
        )
        self.assertEqual(
            result.overall.visited_record_count,
            1,
        )
        self.assertEqual(
            result.overall.not_visited_record_count,
            0,
        )

    def test_cause_proves_non_visit_even_with_numeric_message(self):
        batch = self.create_batch(4)

        self.create_pos_row(
            batch,
            4,
            van="UNKNOWN-CAUSE-VAN",
            client="Cause Client",
            client_normalized="cause client",
            visit_date="2026-07-03",
            ignoration_message="0",
            ignoration_cause="Client absent",
        )

        result = aggregate_pos_visits()

        self.assertEqual(
            result.numeric_message_warning_count,
            1,
        )
        self.assertEqual(
            result.overall.visited_record_count,
            0,
        )
        self.assertEqual(
            result.overall.not_visited_record_count,
            1,
        )

    def test_duplicate_same_client_day_is_warned_not_deleted(self):
        batch = self.create_batch(
            5,
            accepted_rows=2,
        )

        self.create_pos_row(
            batch,
            5,
            van="UNKNOWN-DUPLICATE-VAN",
            client="Duplicate Client",
            client_normalized="duplicate client",
            visit_date="2026-07-03",
            excel_row_number=2,
        )
        duplicate_row = self.create_pos_row(
            batch,
            6,
            van="UNKNOWN-DUPLICATE-VAN",
            client="DUPLICATE CLIENT",
            client_normalized="duplicate client",
            visit_date="2026-07-03",
            excel_row_number=3,
        )

        result = aggregate_pos_visits()

        self.assertEqual(
            result.included_row_count,
            2,
        )
        self.assertEqual(
            result.overall.visited_record_count,
            2,
        )
        self.assertEqual(
            result.overall.unique_client_day_count,
            1,
        )
        self.assertEqual(
            result.duplicate_same_day_warning_count,
            1,
        )
        self.assertEqual(
            result.duplicate_same_day_row_ids,
            (duplicate_row.pk,),
        )
        self.assertTrue(
            result.has_duplicate_warnings
        )

    def test_client_rankings_and_never_visited_clients(self):
        truck = self.create_truck(
            6,
            "POS-VAN-RANKING",
        )
        worker = self.create_worker(6)

        self.create_assignment(
            truck=truck,
            worker=worker,
        )

        batch = self.create_batch(
            6,
            accepted_rows=6,
        )

        rows = (
            (
                10,
                "Alpha",
                "alpha",
                "2026-07-01",
                None,
            ),
            (
                11,
                "Alpha",
                "alpha",
                "2026-07-02",
                None,
            ),
            (
                12,
                "Beta",
                "beta",
                "2026-07-03",
                None,
            ),
            (
                13,
                "Gamma",
                "gamma",
                "2026-07-01",
                "Closed",
            ),
            (
                14,
                "Gamma",
                "gamma",
                "2026-07-02",
                "Absent",
            ),
            (
                15,
                "Delta",
                "delta",
                "2026-07-03",
                "Closed",
            ),
        )

        for index, (
            sequence,
            client,
            normalized,
            visit_date,
            message,
        ) in enumerate(rows, start=2):
            self.create_pos_row(
                batch,
                sequence,
                van="POS-VAN-RANKING",
                client=client,
                client_normalized=normalized,
                visit_date=visit_date,
                ignoration_message=message,
                excel_row_number=index,
            )

        result = aggregate_pos_visits()

        self.assertEqual(
            result.top_visited_clients(1)[0]
            .client_normalized,
            "alpha",
        )
        self.assertEqual(
            result.top_not_visited_clients(1)[0]
            .client_normalized,
            "gamma",
        )

        never_visited = {
            item.client_normalized
            for item in result.never_visited_clients()
        }

        self.assertEqual(
            never_visited,
            {"gamma", "delta"},
        )

    def test_worker_is_resolved_using_exact_visit_date(self):
        truck = self.create_truck(
            7,
            "POS-VAN-WORKERS",
        )
        first_worker = self.create_worker(7)
        second_worker = self.create_worker(8)

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
            7,
            accepted_rows=2,
        )

        self.create_pos_row(
            batch,
            20,
            van="POS-VAN-WORKERS",
            client="First Client",
            client_normalized="first client",
            visit_date="2026-07-03",
            excel_row_number=2,
        )
        self.create_pos_row(
            batch,
            21,
            van="POS-VAN-WORKERS",
            client="Second Client",
            client_normalized="second client",
            visit_date="2026-07-05",
            excel_row_number=3,
        )

        result = aggregate_pos_visits()

        totals_by_worker = {
            item.worker_id: item.metrics.total_record_count
            for item in result.by_worker
        }

        self.assertEqual(
            totals_by_worker,
            {
                first_worker.pk: 1,
                second_worker.pk: 1,
            },
        )

        totals_by_brand_truck_worker = {
            (
                item.brand_id,
                item.truck_id,
                item.worker_id,
            ): item.metrics.total_record_count
            for item in result.by_brand_truck_worker
        }

        self.assertEqual(
            totals_by_brand_truck_worker,
            {
                (
                    self.brand.pk,
                    truck.pk,
                    first_worker.pk,
                ): 1,
                (
                    self.brand.pk,
                    truck.pk,
                    second_worker.pk,
                ): 1,
            },
        )

    def test_unknown_truck_keeps_brand_and_client_totals(self):
        batch = self.create_batch(8)

        row = self.create_pos_row(
            batch,
            30,
            van="UNKNOWN-POS-TRUCK",
            client="Unknown Truck Client",
            client_normalized="unknown truck client",
            visit_date="2026-07-03",
        )

        result = aggregate_pos_visits()

        self.assertEqual(
            result.overall.total_record_count,
            1,
        )
        self.assertEqual(
            result.by_brand_client[0]
            .metrics.total_record_count,
            1,
        )
        self.assertEqual(result.by_truck, ())
        self.assertEqual(result.by_worker, ())

        issue = result.attribution_issues[0]

        self.assertEqual(
            issue.stage,
            PosAttributionStage.TRUCK,
        )
        self.assertEqual(
            issue.code,
            "TRUCK_NOT_FOUND",
        )
        self.assertEqual(
            issue.import_row_id,
            row.pk,
        )
        self.assertEqual(
            issue.outcome,
            PosVisitOutcome.VISITED,
        )

    def test_exact_visit_date_filtering_inside_batch(self):
        batch = self.create_batch(
            9,
            accepted_rows=2,
        )

        self.create_pos_row(
            batch,
            40,
            van="UNKNOWN-OUTSIDE-POS",
            client="Outside Client",
            client_normalized="outside client",
            visit_date="2026-07-02",
            excel_row_number=2,
        )
        self.create_pos_row(
            batch,
            41,
            van="UNKNOWN-INCLUDED-POS",
            client="Included Client",
            client_normalized="included client",
            visit_date="2026-07-05",
            excel_row_number=3,
        )

        result = aggregate_pos_visits(
            period_start=date(2026, 7, 5),
            period_end=date(2026, 7, 5),
        )

        self.assertEqual(
            result.source_row_count,
            2,
        )
        self.assertEqual(
            result.included_row_count,
            1,
        )
        self.assertEqual(
            result.outside_requested_period_count,
            1,
        )
        self.assertEqual(
            result.by_brand_client[0].client_normalized,
            "included client",
        )

    def test_negative_ranking_limit_is_rejected(self):
        result = aggregate_pos_visits(
            rows=(),
        )

        with self.assertRaisesRegex(
            ValueError,
            "limit cannot be negative",
        ):
            result.top_visited_clients(-1)

        with self.assertRaisesRegex(
            ValueError,
            "limit cannot be negative",
        ):
            result.top_not_visited_clients(-1)

    def test_invalid_period_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "period_end cannot be before period_start",
        ):
            aggregate_pos_visits(
                period_start=date(2026, 7, 10),
                period_end=date(2026, 7, 1),
            )

    def test_daily_brand_truck_worker_preserves_visit_dates(
        self,
    ):
        truck = self.create_truck(
            90,
            "POS-MOBILITY-090",
        )
        first_worker = self.create_worker(90)
        second_worker = self.create_worker(91)

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
            90,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
            accepted_rows=2,
        )

        self.create_pos_row(
            batch,
            900,
            van="POS-MOBILITY-090",
            client="Before Change",
            client_normalized="before change",
            visit_date="2026-07-03",
            excel_row_number=2,
        )
        self.create_pos_row(
            batch,
            901,
            van="POS-MOBILITY-090",
            client="After Change",
            client_normalized="after change",
            visit_date="2026-07-04",
            ignoration_cause="Client absent",
            excel_row_number=3,
        )

        result = aggregate_pos_visits()

        self.assertEqual(
            len(result.by_date_brand_truck_worker),
            2,
        )

        before_change = (
            result.by_date_brand_truck_worker[0]
        )
        after_change = (
            result.by_date_brand_truck_worker[1]
        )

        self.assertEqual(
            before_change.visit_date,
            date(2026, 7, 3),
        )
        self.assertEqual(
            before_change.brand_id,
            self.brand.pk,
        )
        self.assertEqual(
            before_change.truck_id,
            truck.pk,
        )
        self.assertEqual(
            before_change.worker_id,
            first_worker.pk,
        )
        self.assertEqual(
            before_change.metrics.total_record_count,
            1,
        )
        self.assertEqual(
            before_change.metrics.visited_record_count,
            1,
        )
        self.assertEqual(
            before_change.metrics.not_visited_record_count,
            0,
        )

        self.assertEqual(
            after_change.visit_date,
            date(2026, 7, 4),
        )
        self.assertEqual(
            after_change.brand_id,
            self.brand.pk,
        )
        self.assertEqual(
            after_change.truck_id,
            truck.pk,
        )
        self.assertEqual(
            after_change.worker_id,
            second_worker.pk,
        )
        self.assertEqual(
            after_change.metrics.total_record_count,
            1,
        )
        self.assertEqual(
            after_change.metrics.visited_record_count,
            0,
        )
        self.assertEqual(
            after_change.metrics.not_visited_record_count,
            1,
        )

        self.assertFalse(
            result.has_attribution_issues
        )
