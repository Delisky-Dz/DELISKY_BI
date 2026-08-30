from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook

from apps.fleet.models import Truck
from apps.imports.models import (
    DistributionBrand,
    ImportBatch,
    ImportBatchStatus,
    ImportSourceSystem,
    ImportSourceUpload,
    SourceTruckMapping,
)
from apps.imports.services.batch_approval import (
    approve_import_batch,
)
from apps.imports.services.raw_sales_derived_review import (
    RawSalesDerivedReviewError,
    create_raw_sales_derived_import_review,
)
from apps.imports.services.raw_sales_review import (
    RawSalesImportReviewError,
)


CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument."
    "spreadsheetml.sheet"
)


class RawSalesDerivedReviewTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.addCleanup(
            self.media_directory.cleanup
        )

        self.media_settings = self.settings(
            MEDIA_ROOT=self.media_directory.name,
        )
        self.media_settings.enable()
        self.addCleanup(
            self.media_settings.disable
        )

        self.user = (
            get_user_model().objects.create_user(
                username="raw-sales-reviewer",
                password="test-password",
            )
        )

        self.bifa = (
            DistributionBrand.objects.create(
                code="BIFA",
                name="BIFA",
                is_active=True,
            )
        )

        self.delisky = (
            DistributionBrand.objects.create(
                code="DELISKY",
                name="DELISKY",
                is_active=True,
            )
        )

        self.bifa_truck = Truck.objects.create(
            internal_code="BIFA LIV03",
            distribution_brand=self.bifa,
            registration_number="SALES-BIFA-03",
            brand="TEST",
            model="TEST",
        )

        self.delisky_truck = Truck.objects.create(
            internal_code="DELISKY LIV02",
            distribution_brand=self.delisky,
            registration_number="SALES-DELISKY-02",
            brand="TEST",
            model="TEST",
        )

        self.bifa_source = (
            ImportSourceSystem.objects.create(
                code="BIFA_MILA",
                name="BIFA MILA",
                is_active=True,
            )
        )

        self.aio_source = (
            ImportSourceSystem.objects.create(
                code="AIO_WEB",
                name="AIO WEB",
                is_active=True,
            )
        )

        SourceTruckMapping.objects.create(
            source_system=self.bifa_source,
            source_code="DCV-03",
            truck=self.bifa_truck,
            is_active=True,
        )

        SourceTruckMapping.objects.create(
            source_system=self.aio_source,
            source_code="VAN2-DELISKY",
            truck=self.delisky_truck,
            is_active=True,
        )

    def make_payload(
        self,
        *,
        filename,
        rows,
    ):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Classeur"

        worksheet.append(
            [
                "Cl\u00e9",
                "Date&Heure",
                "Nom du client",
                "Total",
                "Versement",
                "Region",
                "NET",
            ]
        )

        for row in rows:
            worksheet.append(row)

        output = BytesIO()
        workbook.save(output)
        workbook.close()

        return output.getvalue()

    def make_upload(
        self,
        filename,
        payload,
    ):
        return SimpleUploadedFile(
            filename,
            payload,
            content_type=CONTENT_TYPE,
        )

    def test_creates_reviewed_sales_batch(self):
        payload = self.make_payload(
            filename="DCV-03.xlsx",
            rows=[
                [
                    "VDD-1",
                    "18/08/2026 10:00:00",
                    "Client A",
                    100,
                    100,
                    "MILA",
                    100,
                ],
                [
                    "1",
                    None,
                    None,
                    "100,00",
                    "100,00",
                    None,
                    "100,00",
                ],
            ],
        )

        result = (
            create_raw_sales_derived_import_review(
                self.make_upload(
                    "DCV-03.xlsx",
                    payload,
                ),
                source_system_code="BIFA_MILA",
                uploaded_by=self.user,
                period_start="2026-08-18",
                period_end="2026-08-18",
            )
        )

        batch = result.batch

        self.assertEqual(
            batch.status,
            ImportBatchStatus.REVIEWED,
        )
        self.assertEqual(
            batch.report_type,
            "SALES",
        )
        self.assertEqual(
            batch.brand_id,
            self.bifa.pk,
        )
        self.assertEqual(
            batch.total_rows,
            1,
        )
        self.assertEqual(
            batch.accepted_rows,
            1,
        )
        self.assertEqual(
            batch.rows.count(),
            1,
        )
        self.assertEqual(
            ImportSourceUpload.objects.count(),
            1,
        )

    def test_missing_client_is_persisted_as_excluded(self):
        payload = self.make_payload(
            filename="VAN2-DELISKY.xlsx",
            rows=[
                [
                    "VDD-2",
                    "16/08/2026 15:34:54",
                    None,
                    1850,
                    1850,
                    None,
                    1850,
                ],
            ],
        )

        result = (
            create_raw_sales_derived_import_review(
                self.make_upload(
                    "VAN2-DELISKY.xlsx",
                    payload,
                ),
                source_system_code="AIO_WEB",
                uploaded_by=self.user,
                period_start="2026-08-01",
                period_end="2026-08-18",
            )
        )

        batch = result.batch

        self.assertEqual(
            batch.total_rows,
            1,
        )
        self.assertEqual(
            batch.accepted_rows,
            0,
        )
        self.assertEqual(
            batch.excluded_rows,
            1,
        )
        self.assertGreater(
            batch.error_count,
            0,
        )

        row = batch.rows.get()

        self.assertEqual(
            row.status,
            "EXCLUDED",
        )

    def test_wrong_period_fails_before_persistence(self):
        payload = self.make_payload(
            filename="VAN2-DELISKY.xlsx",
            rows=[
                [
                    "VDD-3",
                    "31/07/2026 10:00:00",
                    "Client A",
                    100,
                    100,
                    "MILA",
                    100,
                ],
            ],
        )

        with self.assertRaises(
            RawSalesImportReviewError
        ) as context:
            create_raw_sales_derived_import_review(
                self.make_upload(
                    "VAN2-DELISKY.xlsx",
                    payload,
                ),
                source_system_code="AIO_WEB",
                uploaded_by=self.user,
                period_start="2026-08-01",
                period_end="2026-08-18",
            )

        self.assertEqual(
            context.exception.code,
            "sale_outside_period",
        )
        self.assertEqual(
            ImportSourceUpload.objects.count(),
            0,
        )
        self.assertEqual(
            ImportBatch.objects.count(),
            0,
        )

    def test_reuses_mutable_batch_for_same_source(self):
        payload = self.make_payload(
            filename="DCV-03.xlsx",
            rows=[
                [
                    "VDD-4",
                    "18/08/2026 10:00:00",
                    "Client A",
                    100,
                    100,
                    "MILA",
                    100,
                ],
            ],
        )

        first = (
            create_raw_sales_derived_import_review(
                self.make_upload(
                    "DCV-03.xlsx",
                    payload,
                ),
                source_system_code="BIFA_MILA",
                uploaded_by=self.user,
                period_start="2026-08-18",
                period_end="2026-08-18",
            )
        )

        second = (
            create_raw_sales_derived_import_review(
                self.make_upload(
                    "DCV-03.xlsx",
                    payload,
                ),
                source_system_code="BIFA_MILA",
                uploaded_by=self.user,
                period_start="2026-08-18",
                period_end="2026-08-18",
            )
        )

        self.assertEqual(
            first.batch.pk,
            second.batch.pk,
        )
        self.assertEqual(
            ImportSourceUpload.objects.count(),
            1,
        )
        self.assertEqual(
            ImportBatch.objects.count(),
            1,
        )

    def test_reuses_identical_approved_batch(self):
        payload = self.make_payload(
            filename="DCV-03.xlsx",
            rows=[
                [
                    "VDD-5",
                    "18/08/2026 10:00:00",
                    "Client A",
                    100,
                    100,
                    "MILA",
                    100,
                ],
            ],
        )

        first = (
            create_raw_sales_derived_import_review(
                self.make_upload(
                    "DCV-03.xlsx",
                    payload,
                ),
                source_system_code="BIFA_MILA",
                uploaded_by=self.user,
                period_start="2026-08-18",
                period_end="2026-08-18",
            )
        )

        approve_import_batch(
            first.batch.pk,
            approved_by=self.user,
        )

        second = (
            create_raw_sales_derived_import_review(
                self.make_upload(
                    "DCV-03.xlsx",
                    payload,
                ),
                source_system_code="BIFA_MILA",
                uploaded_by=self.user,
                period_start="2026-08-18",
                period_end="2026-08-18",
            )
        )

        self.assertEqual(
            first.batch.pk,
            second.batch.pk,
        )
        self.assertEqual(
            second.batch.status,
            ImportBatchStatus.APPROVED,
        )
        self.assertEqual(
            ImportBatch.objects.count(),
            1,
        )

    def test_changed_content_creates_replacement_review(self):
        payload = self.make_payload(
            filename="DCV-03.xlsx",
            rows=[
                [
                    "VDD-6",
                    "18/08/2026 10:00:00",
                    "Client A",
                    100,
                    100,
                    "MILA",
                    100,
                ],
            ],
        )

        first = (
            create_raw_sales_derived_import_review(
                self.make_upload(
                    "DCV-03.xlsx",
                    payload,
                ),
                source_system_code="BIFA_MILA",
                uploaded_by=self.user,
                period_start="2026-08-18",
                period_end="2026-08-18",
            )
        )

        approve_import_batch(
            first.batch.pk,
            approved_by=self.user,
        )

        ImportBatch.objects.filter(
            pk=first.batch.pk
        ).update(
            content_sha256="0" * 64
        )

        second = (
            create_raw_sales_derived_import_review(
                self.make_upload(
                    "DCV-03.xlsx",
                    payload,
                ),
                source_system_code="BIFA_MILA",
                uploaded_by=self.user,
                period_start="2026-08-18",
                period_end="2026-08-18",
            )
        )

        self.assertNotEqual(
            first.batch.pk,
            second.batch.pk,
        )
        self.assertEqual(
            second.batch.status,
            ImportBatchStatus.REVIEWED,
        )
        self.assertEqual(
            second.batch.replaces_batch_id,
            first.batch.pk,
        )
        self.assertEqual(
            ImportBatch.objects.count(),
            2,
        )

        old_batch = ImportBatch.objects.get(
            pk=first.batch.pk
        )

        self.assertEqual(
            old_batch.status,
            ImportBatchStatus.APPROVED,
        )

    def test_wider_period_creates_safe_sales_replacement(
        self,
    ):
        old_payload = self.make_payload(
            filename="DCV-03.xlsx",
            rows=[
                [
                    "VDD-OLD",
                    "18/08/2026 10:00:00",
                    "Client Old",
                    100,
                    100,
                    "MILA",
                    100,
                ],
            ],
        )

        old = create_raw_sales_derived_import_review(
            self.make_upload(
                "DCV-03.xlsx",
                old_payload,
            ),
            source_system_code="BIFA_MILA",
            uploaded_by=self.user,
            period_start="2026-08-01",
            period_end="2026-08-18",
        )

        approve_import_batch(
            old.batch.pk,
            approved_by=self.user,
        )

        historical_payload = self.make_payload(
            filename=(
                "DCV-03 "
                "sales_2026-04-04_to_2026-08-26.xlsx"
            ),
            rows=[
                [
                    "VDD-EARLY",
                    "04/04/2026 09:00:00",
                    "Client Early",
                    50,
                    50,
                    "MILA",
                    50,
                ],
                [
                    "VDD-OLD",
                    "18/08/2026 10:00:00",
                    "Client Old",
                    100,
                    100,
                    "MILA",
                    100,
                ],
            ],
        )

        historical = (
            create_raw_sales_derived_import_review(
                self.make_upload(
                    (
                        "DCV-03 "
                        "sales_2026-04-04_to_2026-08-26.xlsx"
                    ),
                    historical_payload,
                ),
                source_system_code="BIFA_MILA",
                uploaded_by=self.user,
                period_start="2026-04-04",
                period_end="2026-08-26",
            )
        )

        self.assertNotEqual(
            historical.batch.pk,
            old.batch.pk,
        )
        self.assertEqual(
            historical.batch.status,
            ImportBatchStatus.REVIEWED,
        )
        self.assertEqual(
            historical.batch.replaces_batch_id,
            old.batch.pk,
        )

        approve_import_batch(
            historical.batch.pk,
            approved_by=self.user,
        )

        old.batch.refresh_from_db()
        historical.batch.refresh_from_db()

        self.assertEqual(
            old.batch.status,
            ImportBatchStatus.SUPERSEDED,
        )
        self.assertEqual(
            historical.batch.status,
            ImportBatchStatus.APPROVED,
        )

    def test_partial_sales_overlap_is_blocked(
        self,
    ):
        old_payload = self.make_payload(
            filename="DCV-03.xlsx",
            rows=[
                [
                    "VDD-OLD",
                    "18/08/2026 10:00:00",
                    "Client Old",
                    100,
                    100,
                    "MILA",
                    100,
                ],
            ],
        )

        old = create_raw_sales_derived_import_review(
            self.make_upload(
                "DCV-03.xlsx",
                old_payload,
            ),
            source_system_code="BIFA_MILA",
            uploaded_by=self.user,
            period_start="2026-08-10",
            period_end="2026-08-18",
        )

        approve_import_batch(
            old.batch.pk,
            approved_by=self.user,
        )

        new_payload = self.make_payload(
            filename=(
                "DCV-03 "
                "sales_2026-08-15_to_2026-08-26.xlsx"
            ),
            rows=[
                [
                    "VDD-OLD",
                    "18/08/2026 10:00:00",
                    "Client Old",
                    100,
                    100,
                    "MILA",
                    100,
                ],
            ],
        )

        with self.assertRaises(
            RawSalesDerivedReviewError
        ) as context:
            create_raw_sales_derived_import_review(
                self.make_upload(
                    (
                        "DCV-03 "
                        "sales_2026-08-15_to_2026-08-26.xlsx"
                    ),
                    new_payload,
                ),
                source_system_code="BIFA_MILA",
                uploaded_by=self.user,
                period_start="2026-08-15",
                period_end="2026-08-26",
            )

        self.assertEqual(
            context.exception.code,
            "sales_approved_period_overlap_conflict",
        )

    def test_non_exact_mutable_sales_overlap_is_blocked(
        self,
    ):
        first_payload = self.make_payload(
            filename="DCV-03.xlsx",
            rows=[
                [
                    "VDD-FIRST",
                    "10/08/2026 10:00:00",
                    "Client First",
                    100,
                    100,
                    "MILA",
                    100,
                ],
            ],
        )

        create_raw_sales_derived_import_review(
            self.make_upload(
                "DCV-03.xlsx",
                first_payload,
            ),
            source_system_code="BIFA_MILA",
            uploaded_by=self.user,
            period_start="2026-08-01",
            period_end="2026-08-10",
        )

        second_payload = self.make_payload(
            filename=(
                "DCV-03 "
                "sales_2026-08-05_to_2026-08-15.xlsx"
            ),
            rows=[
                [
                    "VDD-SECOND",
                    "12/08/2026 10:00:00",
                    "Client Second",
                    200,
                    200,
                    "MILA",
                    200,
                ],
            ],
        )

        with self.assertRaises(
            RawSalesDerivedReviewError
        ) as context:
            create_raw_sales_derived_import_review(
                self.make_upload(
                    (
                        "DCV-03 "
                        "sales_2026-08-05_to_2026-08-15.xlsx"
                    ),
                    second_payload,
                ),
                source_system_code="BIFA_MILA",
                uploaded_by=self.user,
                period_start="2026-08-05",
                period_end="2026-08-15",
            )

        self.assertEqual(
            context.exception.code,
            "sales_mutable_period_overlap_conflict",
        )

    def test_multiple_approved_sales_overlaps_are_blocked(
        self,
    ):
        first_payload = self.make_payload(
            filename="DCV-03.xlsx",
            rows=[
                [
                    "VDD-FIRST",
                    "05/08/2026 10:00:00",
                    "Client First",
                    100,
                    100,
                    "MILA",
                    100,
                ],
            ],
        )

        first = create_raw_sales_derived_import_review(
            self.make_upload(
                "DCV-03.xlsx",
                first_payload,
            ),
            source_system_code="BIFA_MILA",
            uploaded_by=self.user,
            period_start="2026-08-01",
            period_end="2026-08-10",
        )

        approve_import_batch(
            first.batch.pk,
            approved_by=self.user,
        )

        second_payload = self.make_payload(
            filename="DCV-03.xlsx",
            rows=[
                [
                    "VDD-SECOND",
                    "15/08/2026 10:00:00",
                    "Client Second",
                    200,
                    200,
                    "MILA",
                    200,
                ],
            ],
        )

        second = create_raw_sales_derived_import_review(
            self.make_upload(
                "DCV-03-second.xlsx",
                second_payload,
            ),
            source_system_code="BIFA_MILA",
            uploaded_by=self.user,
            period_start="2026-08-11",
            period_end="2026-08-20",
            original_filename="DCV-03.xlsx",
        )

        approve_import_batch(
            second.batch.pk,
            approved_by=self.user,
        )

        wider_payload = self.make_payload(
            filename=(
                "DCV-03 "
                "sales_2026-08-01_to_2026-08-20.xlsx"
            ),
            rows=[
                [
                    "VDD-FIRST",
                    "05/08/2026 10:00:00",
                    "Client First",
                    100,
                    100,
                    "MILA",
                    100,
                ],
                [
                    "VDD-SECOND",
                    "15/08/2026 10:00:00",
                    "Client Second",
                    200,
                    200,
                    "MILA",
                    200,
                ],
            ],
        )

        with self.assertRaises(
            RawSalesDerivedReviewError
        ) as context:
            create_raw_sales_derived_import_review(
                self.make_upload(
                    (
                        "DCV-03 "
                        "sales_2026-08-01_to_2026-08-20.xlsx"
                    ),
                    wider_payload,
                ),
                source_system_code="BIFA_MILA",
                uploaded_by=self.user,
                period_start="2026-08-01",
                period_end="2026-08-20",
            )

        self.assertEqual(
            context.exception.code,
            "sales_multiple_approved_period_overlap",
        )
