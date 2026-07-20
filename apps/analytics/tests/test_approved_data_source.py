from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analytics.services.approved_data_source import (
    get_approved_activity_rows,
    get_approved_calculation_rows,
    get_approved_rows,
)
from apps.imports.models import (
    DistributionBrand,
    ImportBatch,
    ImportBatchStatus,
    ImportReportType,
    ImportRow,
    ImportRowStatus,
)


class ApprovedDataSourceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()

        cls.user = user_model.objects.create_user(
            username="analytics-test-user",
            password="test-password-only",
        )

        cls.first_brand = DistributionBrand.objects.create(
            code="TESTA",
            name="Test Brand A",
        )
        cls.second_brand = DistributionBrand.objects.create(
            code="TESTB",
            name="Test Brand B",
        )

    def create_batch(
        self,
        sequence,
        *,
        status=ImportBatchStatus.APPROVED,
        report_type=ImportReportType.SALES,
        brand=None,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 7),
        accepted_rows=1,
        excluded_rows=0,
        stopped_rows=0,
    ):
        brand = brand or self.first_brand
        total_rows = (
            accepted_rows
            + excluded_rows
            + stopped_rows
        )

        return ImportBatch.objects.create(
            brand=brand,
            report_type=report_type,
            period_start=period_start,
            period_end=period_end,
            original_filename=f"TEST-{sequence}.xlsx",
            worksheet_name="Sheet1",
            file_size_bytes=100,
            file_sha256=f"{sequence:064x}",
            content_sha256=f"{sequence + 10000:064x}",
            status=status,
            total_rows=total_rows,
            accepted_rows=accepted_rows,
            excluded_rows=excluded_rows,
            stopped_rows=stopped_rows,
            warning_count=0,
            error_count=0,
            review_summary={},
            uploaded_by=self.user,
        )

    def create_row(
        self,
        batch,
        sequence,
        *,
        status=ImportRowStatus.ACCEPTED,
        excel_row_number=2,
    ):
        return ImportRow.objects.create(
            batch=batch,
            excel_row_number=excel_row_number,
            status=status,
            raw_data={
                "VAN": f"TEST-VAN-{sequence}",
            },
            cleaned_data={
                "van": f"TEST-VAN-{sequence}",
                "van_normalized": f"test-van-{sequence}",
            },
            issues=[],
            row_sha256=f"{sequence + 20000:064x}",
        )

    def test_calculation_rows_include_only_approved_accepted_rows(self):
        approved_batch = self.create_batch(1)
        approved_row = self.create_row(
            approved_batch,
            1,
        )

        for sequence, batch_status in enumerate(
            (
                ImportBatchStatus.PENDING,
                ImportBatchStatus.REVIEWED,
                ImportBatchStatus.BLOCKED,
                ImportBatchStatus.SUPERSEDED,
                ImportBatchStatus.FAILED,
            ),
            start=2,
        ):
            batch = self.create_batch(
                sequence,
                status=batch_status,
            )
            self.create_row(
                batch,
                sequence,
            )

        excluded_batch = self.create_batch(
            20,
            accepted_rows=0,
            excluded_rows=1,
        )
        self.create_row(
            excluded_batch,
            20,
            status=ImportRowStatus.EXCLUDED,
        )

        stopped_batch = self.create_batch(
            21,
            accepted_rows=0,
            stopped_rows=1,
        )
        self.create_row(
            stopped_batch,
            21,
            status=ImportRowStatus.STOPPED,
        )

        result_ids = list(
            get_approved_calculation_rows()
            .values_list("id", flat=True)
        )

        self.assertEqual(
            result_ids,
            [approved_row.pk],
        )

    def test_activity_rows_include_accepted_and_stopped_only(self):
        accepted_batch = self.create_batch(30)
        accepted_row = self.create_row(
            accepted_batch,
            30,
        )

        stopped_batch = self.create_batch(
            31,
            accepted_rows=0,
            stopped_rows=1,
        )
        stopped_row = self.create_row(
            stopped_batch,
            31,
            status=ImportRowStatus.STOPPED,
        )

        excluded_batch = self.create_batch(
            32,
            accepted_rows=0,
            excluded_rows=1,
        )
        self.create_row(
            excluded_batch,
            32,
            status=ImportRowStatus.EXCLUDED,
        )

        pending_batch = self.create_batch(
            33,
            status=ImportBatchStatus.PENDING,
            accepted_rows=0,
            stopped_rows=1,
        )
        self.create_row(
            pending_batch,
            33,
            status=ImportRowStatus.STOPPED,
        )

        result_ids = set(
            get_approved_activity_rows()
            .values_list("id", flat=True)
        )

        self.assertEqual(
            result_ids,
            {
                accepted_row.pk,
                stopped_row.pk,
            },
        )

    def test_filters_by_report_type_and_brand(self):
        matching_batch = self.create_batch(
            40,
            report_type=ImportReportType.ITEMS,
            brand=self.second_brand,
        )
        matching_row = self.create_row(
            matching_batch,
            40,
        )

        other_report_batch = self.create_batch(
            41,
            report_type=ImportReportType.SALES,
            brand=self.second_brand,
        )
        self.create_row(
            other_report_batch,
            41,
        )

        other_brand_batch = self.create_batch(
            42,
            report_type=ImportReportType.ITEMS,
            brand=self.first_brand,
        )
        self.create_row(
            other_brand_batch,
            42,
        )

        result_ids = list(
            get_approved_calculation_rows(
                report_type=ImportReportType.ITEMS,
                brand_id=self.second_brand.pk,
            ).values_list("id", flat=True)
        )

        self.assertEqual(
            result_ids,
            [matching_row.pk],
        )

    def test_period_filter_uses_overlapping_batches(self):
        first_batch = self.create_batch(
            50,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 7),
        )
        first_row = self.create_row(
            first_batch,
            50,
        )

        second_batch = self.create_batch(
            51,
            period_start=date(2026, 1, 8),
            period_end=date(2026, 1, 14),
        )
        second_row = self.create_row(
            second_batch,
            51,
        )

        outside_batch = self.create_batch(
            52,
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 7),
        )
        self.create_row(
            outside_batch,
            52,
        )

        result_ids = set(
            get_approved_calculation_rows(
                period_start=date(2026, 1, 7),
                period_end=date(2026, 1, 8),
            ).values_list("id", flat=True)
        )

        self.assertEqual(
            result_ids,
            {
                first_row.pk,
                second_row.pk,
            },
        )

    def test_empty_row_statuses_return_no_rows(self):
        batch = self.create_batch(60)
        self.create_row(
            batch,
            60,
        )

        queryset = get_approved_rows(
            row_statuses=(),
        )

        self.assertFalse(queryset.exists())

    def test_invalid_report_type_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "Unsupported report type",
        ):
            get_approved_calculation_rows(
                report_type="UNKNOWN_REPORT",
            )

    def test_invalid_period_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "period_end cannot be before period_start",
        ):
            get_approved_calculation_rows(
                period_start=date(2026, 3, 10),
                period_end=date(2026, 3, 1),
            )
