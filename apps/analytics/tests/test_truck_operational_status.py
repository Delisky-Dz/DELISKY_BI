from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analytics.services.truck_operational_status import (
    TruckOperationalStatus,
    determine_truck_operational_status,
)
from apps.fleet.models import Truck
from apps.imports.models import (
    DistributionBrand,
    ImportBatch,
    ImportBatchStatus,
    ImportReportType,
    ImportRow,
    ImportRowStatus,
)


class TruckOperationalStatusTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()

        cls.user = user_model.objects.create_user(
            username="operational-status-test-user",
            password="test-password-only",
        )

        cls.brand = DistributionBrand.objects.create(
            code="OPS_TEST",
            name="Operational Status Test Brand",
        )

    def create_truck(self, sequence, code):
        return Truck.objects.create(
            internal_code=code,
            registration_number=f"OPS-REG-{sequence}",
            brand="TEST TRUCK BRAND",
            model="TEST MODEL",
        )

    def create_batch(
        self,
        sequence,
        report_type,
        *,
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 7),
        accepted_rows=0,
        stopped_rows=0,
    ):
        return ImportBatch.objects.create(
            brand=self.brand,
            report_type=report_type,
            period_start=period_start,
            period_end=period_end,
            original_filename=f"OPS-{sequence}.xlsx",
            worksheet_name="Sheet1",
            file_size_bytes=100,
            file_sha256=f"{sequence:064x}",
            content_sha256=f"{sequence + 10000:064x}",
            status=ImportBatchStatus.APPROVED,
            total_rows=accepted_rows + stopped_rows,
            accepted_rows=accepted_rows,
            excluded_rows=0,
            stopped_rows=stopped_rows,
            warning_count=stopped_rows,
            error_count=0,
            review_summary={},
            uploaded_by=self.user,
        )

    def create_active_sales_row(
        self,
        batch,
        sequence,
        *,
        van,
        sale_datetime="2026-07-03T10:00:00",
        total="100",
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
                "client": f"Client {sequence}",
                "client_normalized": f"client {sequence}",
                "total": total,
                "region": None,
                "region_normalized": None,
            },
            issues=[],
            row_sha256=f"{sequence + 20000:064x}",
        )

    def create_stopped_row(
        self,
        batch,
        sequence,
        *,
        van,
        authoritative,
        excel_row_number=2,
    ):
        issue_code = (
            "truck_stopped_for_period"
            if authoritative
            else "stopped_indicator"
        )

        return ImportRow.objects.create(
            batch=batch,
            excel_row_number=excel_row_number,
            status=ImportRowStatus.STOPPED,
            raw_data={
                "VAN": van,
            },
            cleaned_data={
                "van": van,
                "van_normalized": van.casefold(),
            },
            issues=[
                {
                    "code": issue_code,
                    "severity": "WARNING",
                    "message": "Synthetic stopped indicator.",
                    "field": "VAN",
                    "raw_value": van,
                    "details": {
                        "authoritative": authoritative,
                    },
                }
            ],
            row_sha256=f"{sequence + 30000:064x}",
        )

    def test_sales_activity_marks_truck_active(self):
        truck = self.create_truck(
            1,
            "OPS-VAN-ACTIVE",
        )
        batch = self.create_batch(
            1,
            ImportReportType.SALES,
            accepted_rows=1,
        )

        row = self.create_active_sales_row(
            batch,
            1,
            van="OPS-VAN-ACTIVE",
            total="250.50",
        )

        result = determine_truck_operational_status()

        self.assertEqual(
            len(result.states),
            1,
        )

        state = result.states[0]

        self.assertEqual(
            state.status,
            TruckOperationalStatus.ACTIVE,
        )
        self.assertEqual(
            state.truck_id,
            truck.pk,
        )
        self.assertEqual(
            state.sales_activity_count,
            1,
        )
        self.assertEqual(
            state.sales_total,
            Decimal("250.50"),
        )
        self.assertEqual(
            state.activity_row_ids,
            (row.pk,),
        )
        self.assertEqual(
            result.active,
            (state,),
        )

    def test_authoritative_sales_stopped_row_marks_confirmed_stop(self):
        truck = self.create_truck(
            2,
            "OPS-VAN-STOPPED",
        )
        batch = self.create_batch(
            2,
            ImportReportType.SALES,
            stopped_rows=1,
        )

        row = self.create_stopped_row(
            batch,
            2,
            van="OPS-VAN-STOPPED",
            authoritative=True,
        )

        result = determine_truck_operational_status()

        state = result.states[0]

        self.assertEqual(
            state.status,
            TruckOperationalStatus.CONFIRMED_STOPPED,
        )
        self.assertTrue(
            state.is_confirmed_stopped,
        )
        self.assertEqual(
            state.truck_id,
            truck.pk,
        )
        self.assertEqual(
            state.authoritative_stopped_count,
            1,
        )
        self.assertEqual(
            state.authoritative_stopped_row_ids,
            (row.pk,),
        )
        self.assertEqual(
            result.confirmed_stopped,
            (state,),
        )

    def test_non_sales_stopped_row_is_only_possible_stop(self):
        truck = self.create_truck(
            3,
            "OPS-VAN-POSSIBLE",
        )
        batch = self.create_batch(
            3,
            ImportReportType.CHARGEMENT,
            stopped_rows=1,
        )

        row = self.create_stopped_row(
            batch,
            3,
            van="OPS-VAN-POSSIBLE",
            authoritative=False,
        )

        result = determine_truck_operational_status()

        state = result.states[0]

        self.assertEqual(
            state.status,
            TruckOperationalStatus.POSSIBLE_STOPPED,
        )
        self.assertEqual(
            state.truck_id,
            truck.pk,
        )
        self.assertEqual(
            state.possible_stopped_count,
            1,
        )
        self.assertEqual(
            state.possible_stopped_row_ids,
            (row.pk,),
        )
        self.assertEqual(
            result.possible_stopped,
            (state,),
        )

    def test_activity_and_authoritative_stop_create_conflict(self):
        truck = self.create_truck(
            4,
            "OPS-VAN-CONFLICT",
        )
        batch = self.create_batch(
            4,
            ImportReportType.SALES,
            accepted_rows=1,
            stopped_rows=1,
        )

        active_row = self.create_active_sales_row(
            batch,
            4,
            van="OPS-VAN-CONFLICT",
            total="300",
            excel_row_number=2,
        )
        stopped_row = self.create_stopped_row(
            batch,
            5,
            van="OPS-VAN-CONFLICT",
            authoritative=True,
            excel_row_number=3,
        )

        result = determine_truck_operational_status()

        state = result.states[0]

        self.assertEqual(
            state.status,
            TruckOperationalStatus.CONFLICTING_EVIDENCE,
        )
        self.assertTrue(
            state.has_conflicting_evidence,
        )
        self.assertEqual(
            state.truck_id,
            truck.pk,
        )
        self.assertEqual(
            state.activity_row_ids,
            (active_row.pk,),
        )
        self.assertEqual(
            state.authoritative_stopped_row_ids,
            (stopped_row.pk,),
        )
        self.assertEqual(
            result.conflicting,
            (state,),
        )

    def test_possible_stop_does_not_override_sales_activity(self):
        truck = self.create_truck(
            5,
            "OPS-VAN-ACTIVE-WARNING",
        )

        sales_batch = self.create_batch(
            5,
            ImportReportType.SALES,
            accepted_rows=1,
        )
        possible_batch = self.create_batch(
            6,
            ImportReportType.POS,
            stopped_rows=1,
        )

        self.create_active_sales_row(
            sales_batch,
            6,
            van="OPS-VAN-ACTIVE-WARNING",
            total="125",
        )
        possible_row = self.create_stopped_row(
            possible_batch,
            7,
            van="OPS-VAN-ACTIVE-WARNING",
            authoritative=False,
        )

        result = determine_truck_operational_status()

        state = result.states[0]

        self.assertEqual(
            state.status,
            TruckOperationalStatus.ACTIVE,
        )
        self.assertEqual(
            state.truck_id,
            truck.pk,
        )
        self.assertEqual(
            state.sales_activity_count,
            1,
        )
        self.assertEqual(
            state.possible_stopped_count,
            1,
        )
        self.assertEqual(
            state.possible_stopped_row_ids,
            (possible_row.pk,),
        )

    def test_unknown_truck_creates_attribution_issue(self):
        batch = self.create_batch(
            7,
            ImportReportType.SALES,
            stopped_rows=1,
        )

        row = self.create_stopped_row(
            batch,
            8,
            van="UNKNOWN-OPS-VAN",
            authoritative=True,
        )

        result = determine_truck_operational_status()

        self.assertEqual(
            result.states,
            (),
        )
        self.assertEqual(
            result.included_evidence_row_count,
            0,
        )
        self.assertEqual(
            len(result.attribution_issues),
            1,
        )

        issue = result.attribution_issues[0]

        self.assertEqual(
            issue.code,
            "TRUCK_NOT_FOUND",
        )
        self.assertEqual(
            issue.import_row_id,
            row.pk,
        )

    def test_partial_stopped_period_is_not_used(self):
        self.create_truck(
            8,
            "OPS-VAN-PARTIAL",
        )
        batch = self.create_batch(
            8,
            ImportReportType.SALES,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
            stopped_rows=1,
        )

        self.create_stopped_row(
            batch,
            9,
            van="OPS-VAN-PARTIAL",
            authoritative=True,
        )

        result = determine_truck_operational_status(
            period_start=date(2026, 7, 3),
            period_end=date(2026, 7, 7),
        )

        self.assertEqual(
            result.states,
            (),
        )
        self.assertEqual(
            result.partial_overlap_excluded_count,
            1,
        )
        self.assertEqual(
            result.included_evidence_row_count,
            0,
        )

    def test_accepted_non_sales_rows_are_ignored(self):
        self.create_truck(
            9,
            "OPS-VAN-NON-SALES",
        )
        batch = self.create_batch(
            9,
            ImportReportType.ITEMS,
            accepted_rows=1,
        )

        ImportRow.objects.create(
            batch=batch,
            excel_row_number=2,
            status=ImportRowStatus.ACCEPTED,
            raw_data={},
            cleaned_data={
                "van": "OPS-VAN-NON-SALES",
                "van_normalized": "ops-van-non-sales",
                "article": "Test Product",
                "article_normalized": "test product",
                "quantity_sold": "5",
                "client": "Test Client",
                "client_normalized": "test client",
            },
            issues=[],
            row_sha256=f"{40000:064x}",
        )

        result = determine_truck_operational_status()

        self.assertEqual(
            result.states,
            (),
        )
        self.assertEqual(
            result.ignored_accepted_non_sales_count,
            1,
        )
        self.assertEqual(
            result.included_evidence_row_count,
            0,
        )

    def test_invalid_period_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "period_end cannot be before period_start",
        ):
            determine_truck_operational_status(
                period_start=date(2026, 7, 10),
                period_end=date(2026, 7, 1),
            )
