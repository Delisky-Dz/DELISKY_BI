from datetime import date
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, SimpleTestCase
from openpyxl import Workbook

from apps.imports.models import ImportBatch, ImportSourceUpload, SourceTruckExclusion
from apps.imports.services.raw_chargement_file import AdaptedChargementRow
from apps.imports.services.raw_chargement_review import (
    RawChargementImportReviewError, _validate_raw_chargement_period,
    create_raw_chargement_import_review,
)
from apps.imports.services.raw_chargement_derived_review import create_raw_chargement_derived_import_reviews
from apps.imports import test_raw_chargement_derived_review as review_fixtures


START = date(2026, 8, 27)
END = date(2026, 10, 22)


def upload(dates, *, excluded=False, footer=False):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Vers l'emplacement", "Qté", "Article", "Date&Heure"])
    for value in dates:
        sheet.append(["VAN1-DELISKY", 10, "ARTICLE DELISKY", value])
    if excluded:
        sheet.append(["VAN_SUPERVISEUR", 20, "OUT OF SCOPE", "2026-08-26 09:00:00"])
    if footer:
        sheet.append([None, 10 * len(dates) + (20 if excluded else 0), len(dates) + int(excluded), None])
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return SimpleUploadedFile("period.xlsx", output.getvalue())


class ChargementPeriodValidationTests(SimpleTestCase):
    def validate(self, dates):
        rows = tuple(AdaptedChargementRow(i + 2, {"Date&Heure": value}) for i, value in enumerate(dates))
        _validate_raw_chargement_period(rows, period_start=START, period_end=END)

    def test_inclusive_boundaries(self):
        self.validate(["2026-08-27 00:00:00", "2026-10-22 23:59:59"])

    def test_before_start(self):
        with self.assertRaises(RawChargementImportReviewError) as ctx:
            self.validate(["2026-08-26 23:59:59"])
        self.assertEqual(ctx.exception.code, "chargement_row_outside_selected_period")
        self.assertEqual(ctx.exception.details["out_of_period_count"], 1)

    def test_after_end(self):
        with self.assertRaises(RawChargementImportReviewError) as ctx:
            self.validate(["2026-10-23 00:00:00"])
        self.assertEqual(ctx.exception.details["latest_offending_date"], "2026-10-23")

    def test_aggregate_details(self):
        with self.assertRaises(RawChargementImportReviewError) as ctx:
            self.validate(["2026-10-23", "2026-09-01", "2026-08-26", "2026-08-25"])
        self.assertEqual(ctx.exception.details, {
            "out_of_period_count": 3,
            "earliest_offending_date": "2026-08-25",
            "latest_offending_date": "2026-10-23",
            "period_start": "2026-08-27", "period_end": "2026-10-22",
            "sample_excel_row_numbers": [2, 4, 5],
        })

    def test_sample_is_bounded_but_count_is_complete(self):
        with self.assertRaises(RawChargementImportReviewError) as ctx:
            self.validate(["2026-08-26"] * 25)
        self.assertEqual(ctx.exception.details["out_of_period_count"], 25)
        self.assertEqual(ctx.exception.details["sample_excel_row_numbers"], list(range(2, 22)))

    def test_accountant_template_displays_period_error_details(self):
        from types import SimpleNamespace
        from django.template.loader import render_to_string
        item = SimpleNamespace(
            succeeded=False, original_filename="period.xlsx",
            error_code="chargement_row_outside_selected_period",
            error_message="Rows outside the selected period.",
            error_details={
                "out_of_period_count": 7,
                "earliest_offending_date": "2026-08-26",
                "latest_offending_date": "2026-10-23",
                "period_start": "2026-08-27",
                "period_end": "2026-10-22",
                "sample_excel_row_numbers": [2, 17],
            },
        )
        html = render_to_string("imports/partials/chargement_upload.html", {
            "raw_upload_result": SimpleNamespace(files=[item], succeeded_count=0, failed_count=1),
        })
        for value in ("2026-08-26", "2026-10-23", "2026-08-27", "2026-10-22", "2, 17", "<dd>7</dd>"):
            self.assertIn(value, html)

    def test_bifa_dcv_and_dlv_use_distinct_data_driven_mappings(self):
        from apps.imports.services.raw_chargement_adapter import adapt_raw_chargement_row
        mapping = {"DCV-03": "BIFA LIV03", "DLV-03": "BIFA PLIV03"}
        for source, expected in mapping.items():
            result = adapt_raw_chargement_row({"Vers l'emplacement": source, "Qté": 1, "Article": "A"}, truck_mapping=mapping)
            self.assertEqual(result["VAN"], expected)


class ChargementPeriodPersistenceTests(TestCase):
    setUp = review_fixtures.RawChargementDerivedReviewTests.setUp

    def create(self, source, *, derived):
        kwargs = dict(uploaded_by=self.user, period_start=START, period_end=END)
        if derived:
            return create_raw_chargement_derived_import_reviews(source, source_system_code="AIO_WEB", **kwargs)
        return create_raw_chargement_import_review(source, brand_code="DELISKY", truck_mapping={"VAN1-DELISKY": "DELISKY LIV01"}, **kwargs)

    def test_both_entry_points_reject_before_any_persistence(self):
        for derived in (False, True):
            with self.subTest(derived=derived):
                with self.assertRaises(RawChargementImportReviewError):
                    self.create(upload(["2026-08-26", "2026-10-23"]), derived=derived)
                self.assertFalse(ImportBatch.objects.exists())
                self.assertFalse(ImportSourceUpload.objects.exists())

    def test_both_entry_points_accept_boundaries_and_footer(self):
        for derived in (False, True):
            with self.subTest(derived=derived):
                result = self.create(upload(["2026-08-27", "2026-10-22 23:59:59"], footer=True), derived=derived)
                batches = result.batches if derived else [result.batch]
                self.assertEqual(batches[0].total_rows, 2)

    def test_excluded_rows_do_not_cause_false_period_errors(self):
        SourceTruckExclusion.objects.create(source_system=self.source_system, source_code="VAN_SUPERVISEUR", reason="OUT_OF_SCOPE", is_active=True)
        result = self.create(upload(["2026-08-27"], excluded=True, footer=True), derived=True)
        self.assertEqual(result.batches[0].total_rows, 1)
        self.assertEqual(result.source_upload.audit_metadata["chargement_source_exclusions"]["count"], 1)

    def approved_previous(self):
        result = create_raw_chargement_derived_import_reviews(upload(["2026-08-26"]), source_system_code="AIO_WEB", uploaded_by=self.user, period_start="2026-04-04", period_end="2026-08-26")
        batch = result.batches[0]
        batch.status = "APPROVED"
        batch.save(update_fields=["status"])
        return batch

    def test_adjacent_period_does_not_overlap_approved_previous_day(self):
        old = self.approved_previous()
        result = self.create(upload(["2026-08-27"]), derived=True)
        self.assertEqual(len(result.batches), 1)
        old.refresh_from_db()
        self.assertEqual(old.status, "APPROVED")
        self.assertEqual(old.rows.count(), 1)

    def test_partial_overlap_still_rejected(self):
        old = self.approved_previous()
        with self.assertRaises(RawChargementImportReviewError) as ctx:
            create_raw_chargement_derived_import_reviews(upload(["2026-08-26"]), source_system_code="AIO_WEB", uploaded_by=self.user, period_start="2026-08-26", period_end=END)
        self.assertEqual(ctx.exception.code, "chargement_period_overlap_conflict")
        self.assertEqual(ImportBatch.objects.count(), 1)
        old.refresh_from_db()
        self.assertEqual(old.status, "APPROVED")
