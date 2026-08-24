from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import (
    SimpleUploadedFile,
)
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
from apps.imports.services.raw_items_derived_review import (
    create_raw_items_derived_import_review,
)


CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument."
    "spreadsheetml.sheet"
)


class RawItemsDerivedReviewTests(TestCase):
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
                username="raw-items-reviewer",
                password="test-password",
            )
        )

        self.bifa = DistributionBrand.objects.create(
            code="BIFA",
            name="BIFA",
            is_active=True,
        )

        self.delisky = DistributionBrand.objects.create(
            code="DELISKY",
            name="DELISKY",
            is_active=True,
        )

        self.bifa_truck = Truck.objects.create(
            internal_code="BIFA LIV03",
            distribution_brand=self.bifa,
            registration_number="ITEMS-BIFA-03",
            brand="TEST",
            model="TEST",
        )

        self.delisky_truck = Truck.objects.create(
            internal_code="DELISKY LIV02",
            distribution_brand=self.delisky,
            registration_number="ITEMS-DELISKY-02",
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

    def make_payload(self, rows):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Classeur"

        worksheet.append(
            [
                "Article",
                "Qt\u00e9",
                "Total",
                "Barcode",
                "Client",
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

    def create_review(
        self,
        *,
        filename,
        payload,
        source_system_code,
    ):
        return (
            create_raw_items_derived_import_review(
                self.make_upload(
                    filename,
                    payload,
                ),
                source_system_code=(
                    source_system_code
                ),
                uploaded_by=self.user,
                period_start="2026-08-01",
                period_end="2026-08-18",
            )
        )

    def test_creates_reviewed_bifa_items_batch(self):
        payload = self.make_payload(
            [
                [
                    "ARTICLE A",
                    10,
                    1000,
                    "ABC",
                    "CLIENT A",
                ],
            ]
        )

        result = self.create_review(
            filename="DCV-03 items.xlsx",
            payload=payload,
            source_system_code="BIFA_MILA",
        )

        batch = result.batch

        self.assertEqual(
            batch.status,
            ImportBatchStatus.REVIEWED,
        )
        self.assertEqual(
            batch.report_type,
            "ITEMS",
        )
        self.assertEqual(
            batch.brand_id,
            self.bifa.pk,
        )
        self.assertEqual(batch.total_rows, 1)
        self.assertEqual(batch.accepted_rows, 1)
        self.assertEqual(batch.rows.count(), 1)

    def test_creates_reviewed_aio_items_batch(self):
        payload = self.make_payload(
            [
                [
                    "ARTICLE A",
                    10,
                    1000,
                    "ABC",
                    "CLIENT A",
                ],
            ]
        )

        result = self.create_review(
            filename="VAN2-DELISKY items.xlsx",
            payload=payload,
            source_system_code="AIO_WEB",
        )

        self.assertEqual(
            result.batch.brand_id,
            self.delisky.pk,
        )
        self.assertEqual(
            result.batch.report_type,
            "ITEMS",
        )

    def test_missing_client_is_persisted_as_excluded(self):
        payload = self.make_payload(
            [
                [
                    "ARTICLE A",
                    10,
                    1000,
                    "ABC",
                    None,
                ],
            ]
        )

        result = self.create_review(
            filename="DCV-03 items.xlsx",
            payload=payload,
            source_system_code="BIFA_MILA",
        )

        self.assertEqual(
            result.batch.accepted_rows,
            0,
        )
        self.assertEqual(
            result.batch.excluded_rows,
            1,
        )
        self.assertGreater(
            result.batch.error_count,
            0,
        )

    def test_reuses_mutable_batch(self):
        payload = self.make_payload(
            [
                [
                    "ARTICLE A",
                    10,
                    1000,
                    "ABC",
                    "CLIENT A",
                ],
            ]
        )

        first = self.create_review(
            filename="DCV-03 items.xlsx",
            payload=payload,
            source_system_code="BIFA_MILA",
        )

        second = self.create_review(
            filename="DCV-03 items.xlsx",
            payload=payload,
            source_system_code="BIFA_MILA",
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
            [
                [
                    "ARTICLE A",
                    10,
                    1000,
                    "ABC",
                    "CLIENT A",
                ],
            ]
        )

        first = self.create_review(
            filename="DCV-03 items.xlsx",
            payload=payload,
            source_system_code="BIFA_MILA",
        )

        approve_import_batch(
            first.batch.pk,
            approved_by=self.user,
        )

        second = self.create_review(
            filename="DCV-03 items.xlsx",
            payload=payload,
            source_system_code="BIFA_MILA",
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

    def test_changed_content_creates_replacement(self):
        first_payload = self.make_payload(
            [
                [
                    "ARTICLE A",
                    10,
                    1000,
                    "ABC",
                    "CLIENT A",
                ],
            ]
        )

        second_payload = self.make_payload(
            [
                [
                    "ARTICLE A",
                    11,
                    1100,
                    "ABC",
                    "CLIENT A",
                ],
            ]
        )

        first = self.create_review(
            filename="DCV-03 items.xlsx",
            payload=first_payload,
            source_system_code="BIFA_MILA",
        )

        approve_import_batch(
            first.batch.pk,
            approved_by=self.user,
        )

        second = self.create_review(
            filename="DCV-03 items.xlsx",
            payload=second_payload,
            source_system_code="BIFA_MILA",
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
