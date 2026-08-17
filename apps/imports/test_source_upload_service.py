from hashlib import sha256
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.imports.models import (
    ImportSourceSystem,
    ImportSourceUpload,
)
from apps.imports.services.source_upload_store import (
    create_import_source_upload,
)


class ImportSourceUploadServiceTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.addCleanup(self.media_directory.cleanup)

        self.media_settings = self.settings(
            MEDIA_ROOT=self.media_directory.name,
        )
        self.media_settings.enable()
        self.addCleanup(self.media_settings.disable)

        self.user = get_user_model().objects.create_user(
            username="source-upload-user",
            password="test-password",
        )

        self.source_system = (
            ImportSourceSystem.objects.create(
                code="AIO_WEB",
                name="AIO-WEB",
                is_active=True,
            )
        )

    def test_creates_source_upload_with_file_identity(self):
        file_bytes = b"raw-file-content"

        upload = SimpleUploadedFile(
            "mixed_raw.xlsx",
            file_bytes,
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        result = create_import_source_upload(
            upload,
            source_system_code="AIO_WEB",
            uploaded_by=self.user,
            worksheet_name="Transferts",
            original_filename="mixed_raw.xlsx",
        )

        self.assertTrue(result.created)

        self.assertEqual(
            ImportSourceUpload.objects.count(),
            1,
        )

        source_upload = result.source_upload

        self.assertEqual(
            source_upload.source_system,
            self.source_system,
        )

        self.assertEqual(
            source_upload.original_filename,
            "mixed_raw.xlsx",
        )

        self.assertEqual(
            source_upload.worksheet_name,
            "Transferts",
        )

        self.assertEqual(
            source_upload.file_size_bytes,
            len(file_bytes),
        )

        self.assertEqual(
            source_upload.file_sha256,
            sha256(file_bytes).hexdigest(),
        )

        self.assertTrue(
            source_upload.source_file
        )

        with source_upload.source_file.open("rb") as stored:
            self.assertEqual(
                stored.read(),
                file_bytes,
            )


    def test_reuses_existing_source_upload_for_same_file(self):
        file_bytes = b"same-raw-file-content"

        first_upload = SimpleUploadedFile(
            "first_name.xlsx",
            file_bytes,
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        second_upload = SimpleUploadedFile(
            "second_name.xlsx",
            file_bytes,
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        first = create_import_source_upload(
            first_upload,
            source_system_code="AIO_WEB",
            uploaded_by=self.user,
            worksheet_name="Transferts",
            original_filename="first_name.xlsx",
        )

        second = create_import_source_upload(
            second_upload,
            source_system_code="AIO_WEB",
            uploaded_by=self.user,
            worksheet_name="Transferts",
            original_filename="second_name.xlsx",
        )

        self.assertTrue(first.created)
        self.assertFalse(second.created)

        self.assertEqual(
            first.source_upload.pk,
            second.source_upload.pk,
        )

        self.assertEqual(
            ImportSourceUpload.objects.count(),
            1,
        )

        self.assertEqual(
            second.source_upload.original_filename,
            "first_name.xlsx",
        )


    def test_rejects_same_file_for_different_source_system(self):
        from apps.imports.services.source_upload_store import (
            ImportSourceUploadStoreError,
        )

        ImportSourceSystem.objects.create(
            code="BIFA_MILA",
            name="BIFA MILA",
            is_active=True,
        )

        file_bytes = b"shared-raw-file-content"

        first_upload = SimpleUploadedFile(
            "aio_raw.xlsx",
            file_bytes,
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        second_upload = SimpleUploadedFile(
            "bifa_raw.xlsx",
            file_bytes,
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        first = create_import_source_upload(
            first_upload,
            source_system_code="AIO_WEB",
            uploaded_by=self.user,
            worksheet_name="Transferts",
            original_filename="aio_raw.xlsx",
        )

        with self.assertRaises(
            ImportSourceUploadStoreError
        ) as captured:
            create_import_source_upload(
                second_upload,
                source_system_code="BIFA_MILA",
                uploaded_by=self.user,
                worksheet_name="Transferts",
                original_filename="bifa_raw.xlsx",
            )

        self.assertEqual(
            captured.exception.code,
            "source_upload_system_mismatch",
        )

        self.assertEqual(
            ImportSourceUpload.objects.count(),
            1,
        )

        self.assertEqual(
            ImportSourceUpload.objects.get().pk,
            first.source_upload.pk,
        )
