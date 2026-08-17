from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.imports.models import (
    DistributionBrand,
    ImportBatch,
    ImportRowStatus,
    ImportSourceSystem,
    ImportSourceUpload,
)
from apps.imports.services.derived_batch_review import (
    _persist_derived_import_review,
)
from apps.imports.services.review_summary import (
    ImportReviewSummary,
)
from apps.imports.services.row_staging import (
    PreparedImportRow,
    PreparedImportRows,
)


class DerivedImportReviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="derived-reviewer",
            password="test-password",
        )

        self.brand = DistributionBrand.objects.create(
            code="DELISKY",
            name="DELISKY",
            is_active=True,
        )

        self.source_system = (
            ImportSourceSystem.objects.create(
                code="AIO_WEB",
                name="AIO-WEB",
                is_active=True,
            )
        )

        self.source_upload = (
            ImportSourceUpload.objects.create(
                source_system=self.source_system,
                original_filename="mixed_raw.xlsx",
                worksheet_name="Transferts",
                file_size_bytes=1234,
                file_sha256="a" * 64,
                uploaded_by=self.user,
            )
        )

    def test_persists_derived_batch_without_copying_raw_file(self):
        prepared_rows = PreparedImportRows(
            report_type="CHARGEMENT",
            rows=(
                PreparedImportRow(
                    excel_row_number=2,
                    status=ImportRowStatus.ACCEPTED,
                    raw_data={
                        "VAN": "DELISKY LIV01",
                        "Qt\u00e9": 10,
                        "Article": "ARTICLE A",
                    },
                    cleaned_data={
                        "VAN": "DELISKY LIV01",
                        "Qt\u00e9": 10,
                        "Article": "ARTICLE A",
                    },
                    issues=[],
                    row_sha256="b" * 64,
                ),
            ),
            content_sha256="c" * 64,
        )

        summary = ImportReviewSummary(
            filename="mixed_raw.xlsx",
            report_type="CHARGEMENT",
            brand_code="DELISKY",
            period_start="2026-03-07",
            period_end="2026-03-11",
            total_rows=1,
            accepted_rows=1,
            excluded_rows=0,
            stopped_rows=0,
            retained_rows=1,
            warning_count=0,
            error_count=0,
            blocking_row_count=0,
            can_approve=True,
            recommended_status="REVIEWED",
            issue_groups=(),
        )

        result = _persist_derived_import_review(
            source_upload=self.source_upload,
            uploaded_by=self.user,
            reviewer=self.user,
            batch=None,
            brand_code="DELISKY",
            report_type="CHARGEMENT",
            period_start=date(2026, 3, 7),
            period_end=date(2026, 3, 11),
            worksheet_name="Transferts",
            summary=summary,
            prepared_rows=prepared_rows,
        )

        self.assertTrue(result.created)

        batch = result.batch

        self.assertEqual(
            ImportBatch.objects.count(),
            1,
        )

        self.assertEqual(
            batch.source_upload_id,
            self.source_upload.pk,
        )

        self.assertEqual(
            batch.brand.code,
            "DELISKY",
        )

        self.assertEqual(
            batch.file_sha256,
            "",
        )

        self.assertFalse(
            batch.source_file
        )

        self.assertEqual(
            batch.file_size_bytes,
            self.source_upload.file_size_bytes,
        )

        self.assertEqual(
            batch.content_sha256,
            prepared_rows.content_sha256,
        )

        self.assertEqual(
            batch.rows.count(),
            1,
        )

        row = batch.rows.get()

        self.assertEqual(
            row.excel_row_number,
            2,
        )

        self.assertEqual(
            row.raw_data["VAN"],
            "DELISKY LIV01",
        )
