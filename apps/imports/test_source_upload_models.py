from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.imports.models import (
    DistributionBrand,
    ImportBatch,
    ImportBatchStatus,
    ImportReportType,
    ImportSourceSystem,
    ImportSourceUpload,
)


class ImportSourceUploadModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="source-upload-test-user",
            password="Temporary-Test-Password-2026",
        )

        cls.source_system = ImportSourceSystem.objects.create(
            code="AIO_WEB",
            name="AIO-WEB",
        )

        cls.delisky = DistributionBrand.objects.create(
            code="DELISKY",
            name="DELISKY",
        )

        cls.nita = DistributionBrand.objects.create(
            code="NITA",
            name="NITA",
        )

    def build_source_upload(self, **overrides):
        data = {
            "source_system": self.source_system,
            "original_filename": "Chargement Delisky.xlsx",
            "worksheet_name": "Classeur",
            "file_size_bytes": 12345,
            "file_sha256": "a" * 64,
            "uploaded_by": self.user,
        }
        data.update(overrides)
        return ImportSourceUpload(**data)

    def build_batch(self, **overrides):
        data = {
            "brand": self.delisky,
            "report_type": ImportReportType.CHARGEMENT,
            "period_start": date(2026, 8, 1),
            "period_end": date(2026, 8, 17),
            "original_filename": "Chargement Delisky.xlsx",
            "worksheet_name": "Classeur",
            "file_size_bytes": 12345,
            "file_sha256": "b" * 64,
            "content_sha256": "c" * 64,
            "uploaded_by": self.user,
        }
        data.update(overrides)
        return ImportBatch(**data)

    def test_source_upload_normalizes_filename_and_hash(self):
        upload = self.build_source_upload(
            original_filename="  Chargement Delisky.xlsx  ",
            worksheet_name="  Classeur  ",
            file_sha256="A" * 64,
        )

        upload.save()

        self.assertEqual(
            upload.original_filename,
            "Chargement Delisky.xlsx",
        )
        self.assertEqual(
            upload.worksheet_name,
            "Classeur",
        )
        self.assertEqual(
            upload.file_sha256,
            "a" * 64,
        )

    def test_duplicate_source_file_hash_is_rejected(self):
        self.build_source_upload().save()

        duplicate = self.build_source_upload()

        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_canonical_batch_keeps_file_hash_identity(self):
        batch = self.build_batch()

        batch.full_clean()

        self.assertIsNone(batch.source_upload_id)
        self.assertEqual(
            batch.file_sha256,
            "b" * 64,
        )

    def test_derived_batch_uses_source_upload_without_file_hash(self):
        source_upload = self.build_source_upload()
        source_upload.save()

        batch = self.build_batch(
            source_upload=source_upload,
            file_sha256="",
        )

        batch.full_clean()

        self.assertEqual(
            batch.source_upload_id,
            source_upload.pk,
        )
        self.assertEqual(batch.file_sha256, "")

    def test_batch_cannot_have_both_source_identities(self):
        source_upload = self.build_source_upload()
        source_upload.save()

        batch = self.build_batch(
            source_upload=source_upload,
            file_sha256="b" * 64,
        )

        with self.assertRaises(ValidationError):
            batch.full_clean()

    def test_batch_requires_one_source_identity(self):
        batch = self.build_batch(
            source_upload=None,
            file_sha256="",
        )

        with self.assertRaises(ValidationError):
            batch.full_clean()

    def test_same_raw_upload_can_create_different_brand_batches(self):
        source_upload = self.build_source_upload()
        source_upload.save()

        first = self.build_batch(
            source_upload=source_upload,
            file_sha256="",
            brand=self.delisky,
            content_sha256="d" * 64,
            status=ImportBatchStatus.APPROVED,
        )
        first.full_clean()
        first.save()

        second = self.build_batch(
            source_upload=source_upload,
            file_sha256="",
            brand=self.nita,
            content_sha256="e" * 64,
            status=ImportBatchStatus.APPROVED,
        )

        second.full_clean()
        second.save()

        self.assertEqual(
            ImportBatch.objects.filter(
                source_upload=source_upload,
                status=ImportBatchStatus.APPROVED,
            ).count(),
            2,
        )

    def test_same_source_scope_cannot_be_derived_twice(self):
        source_upload = self.build_source_upload()
        source_upload.save()

        first = self.build_batch(
            source_upload=source_upload,
            file_sha256="",
            content_sha256="d" * 64,
        )
        first.save()

        duplicate = self.build_batch(
            source_upload=source_upload,
            file_sha256="",
            content_sha256="e" * 64,
        )

        with self.assertRaises(ValidationError):
            duplicate.full_clean()
