from copy import deepcopy
from datetime import date
from decimal import Decimal
from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from openpyxl import Workbook

from apps.analytics.services.items_aggregation import aggregate_items
from apps.analytics.services.report_rows import parse_item_row, AnalyticalRowError
from apps.fleet.models import Truck
from apps.imports.models import DistributionBrand, ImportRow, ImportSourceSystem, SourceProductPackaging, SourceTruckMapping, SourceTruckExclusion
from apps.imports.services.approval_dispatch import approve_reviewed_batch
from apps.imports.services.batch_approval import ImportBatchApprovalError
from apps.imports.services.items_detail_unassigned import METADATA_KEY, rules_for_source
from apps.imports.services.raw_items_detail_file import RawItemsDetailFileError
from apps.imports.services.raw_items_detail_import_review import create_raw_items_detail_import_review
from apps.imports.services.raw_items_detail_review import prepare_raw_items_detail_review
from apps.imports.services.source_upload_store import create_import_source_upload


class UnassignedItemsDocumentTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        setting = override_settings(MEDIA_ROOT=temporary.name)
        setting.enable()
        self.addCleanup(setting.disable)
        self.user = get_user_model().objects.create_user(username="unassigned-reviewer")
        self.brand = DistributionBrand.objects.create(code="BIFA", name="BIFA")
        self.source = ImportSourceSystem.objects.create(code="BIFA_MILA", name="BIFA")
        self.truck = Truck.objects.create(internal_code="BIFA PLIV01", distribution_brand=self.brand, registration_number="UNASSIGNED-TEST")
        SourceTruckMapping.objects.create(source_system=self.source, source_code="LV-01", truck=self.truck)
        SourceProductPackaging.objects.create(source_system=self.source, designation="ARTICLE A", units_per_carton=1, needs_review=False)
        self.rule = {"source_user": "ADMIN", "document": "VDD-2", "document_number": "200", "sale_date": "2026-09-09", "brand_code": "BIFA", "authorization": "Explicit brand-only financial decision"}
        self.payload = self.make_payload()

    def make_payload(self, *, document="VDD-2", sale_date="09/09/2026 15:40:18"):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["Article", "Qté vendue", "Date de vente", "Utilisateur", "Document", "Num doc.", "Client", "Total vente"])
        sheet.append(["ARTICLE A", 10, "09/09/2026 09:00:00", "LV-01", "VDD-1", 100, "CLIENT A", 100])
        sheet.append(["ARTICLE A", 40, sale_date, "ADMIN", document, 200, "CLIENT B", 335])
        sheet.append(["ARTICLE A", 24, sale_date, "ADMIN", document, 200, "CLIENT B", 470.4])
        sheet.append(["3", "74,000", None, None, None, None, None, "905,40"])
        stream = BytesIO()
        workbook.save(stream)
        workbook.close()
        return stream.getvalue()

    def file(self, payload=None):
        return SimpleUploadedFile("BIFA_Items_DETAIL_2026-08-27_to_2026-10-22.xlsx", payload or self.payload)

    def authorize(self, payload=None):
        upload = create_import_source_upload(self.file(payload), source_system_code="BIFA_MILA", uploaded_by=self.user).source_upload
        upload.audit_metadata = {METADATA_KEY: [deepcopy(self.rule)]}
        upload.save(update_fields=["audit_metadata"])
        return upload

    def review(self):
        return create_raw_items_detail_import_review(self.file(), source_system_code="BIFA_MILA", uploaded_by=self.user, period_start=date(2026, 8, 27), period_end=date(2026, 10, 22)).batches[0]

    def test_brand_totals_keep_unassigned_rows_but_truck_rankings_do_not(self):
        self.authorize()
        batch = self.review()
        self.assertEqual((batch.total_rows, batch.accepted_rows, batch.error_count), (3, 3, 0))
        self.assertEqual(batch.review_summary["items_detail"]["covered_trucks"], ["BIFA PLIV01"])
        self.assertEqual(batch.review_summary["items_detail"]["unassigned"], {"row_count": 2, "total_units": 64, "sale_total": "805.4"})
        approve_reviewed_batch(batch.pk, approved_by=self.user)
        rows = list(ImportRow.objects.filter(batch=batch).select_related("batch__brand"))
        unassigned = [row for row in rows if row.cleaned_data.get("truck_attribution") == "UNASSIGNED"]
        self.assertEqual(len(unassigned), 2)
        self.assertEqual(sum(Decimal(str(row.raw_data["Total vente"])) for row in unassigned), Decimal("805.4"))
        self.assertTrue(all(row.cleaned_data["van"] is None for row in unassigned))
        result = aggregate_items(rows=rows)
        self.assertEqual(result.overall.quantity_sold, 74)
        self.assertEqual(result.by_brand[0].metrics.quantity_sold, 74)
        self.assertEqual(result.unassigned_row_count, 2)
        self.assertEqual(sum(x.metrics.quantity_sold for x in result.by_truck), 10)
        self.assertEqual(sum(x.metrics.quantity_sold for x in result.by_brand_van_client), 10)
        self.assertEqual(sum(x.metrics.quantity_sold for x in result.by_brand_client), 74)
        self.assertFalse(any(issue.import_row_id in [x.pk for x in unassigned] for issue in result.attribution_issues))

    def test_unknown_user_still_fails_without_document_decision(self):
        with self.assertRaises(RawItemsDetailFileError) as captured:
            self.review()
        self.assertEqual(captured.exception.details["excel_row_number"], 3)
        self.assertEqual(captured.exception.details["cause_code"], "source_truck_not_mapped")

    def test_rule_is_scoped_to_exact_file_and_document(self):
        self.authorize()
        self.assertEqual(rules_for_source(self.file(self.make_payload(document="VDD-OTHER")), self.source), {})
        changed = self.make_payload(document="VDD-OTHER")
        self.authorize(changed)
        with self.assertRaises(RawItemsDetailFileError):
            prepare_raw_items_detail_review(self.file(changed), source_system_code="BIFA_MILA", period_start="2026-08-27", period_end="2026-10-22")

    def test_unassigned_date_does_not_bypass_period_boundary(self):
        self.rule["sale_date"] = "2026-10-23"
        changed = self.make_payload(sale_date="23/10/2026 15:40:18")
        self.authorize(changed)
        result = prepare_raw_items_detail_review(self.file(changed), source_system_code="BIFA_MILA", period_start="2026-08-27", period_end="2026-10-22")
        self.assertEqual(result.brand_reviews[0].cleaning_result.error_count, 2)

    def test_rule_change_after_review_blocks_approval(self):
        upload = self.authorize()
        batch = self.review()
        upload.audit_metadata = {}
        upload.save(update_fields=["audit_metadata"])
        with self.assertRaises(ImportBatchApprovalError) as captured:
            approve_reviewed_batch(batch.pk, approved_by=self.user)
        self.assertEqual(captured.exception.code, "source_truck_scope_changed")

    def test_conflicting_exclusion_cannot_silently_remove_authorized_rows(self):
        self.authorize()
        SourceTruckExclusion.objects.create(source_system=self.source, source_code="ADMIN", reason="OUT_OF_SCOPE")
        with self.assertRaises(RawItemsDetailFileError) as captured:
            self.review()
        self.assertEqual(captured.exception.code, "unassigned_document_scope_conflict")

    def test_conflicting_truck_mapping_cannot_attribute_authorized_rows(self):
        self.authorize()
        SourceTruckMapping.objects.create(source_system=self.source, source_code="ADMIN", truck=self.truck)
        with self.assertRaises(RawItemsDetailFileError) as captured:
            self.review()
        self.assertEqual(captured.exception.code, "unassigned_document_scope_conflict")

    def test_analytics_rejects_unassigned_marker_for_unreviewed_document(self):
        self.authorize()
        batch = self.review()
        approve_reviewed_batch(batch.pk, approved_by=self.user)
        row = ImportRow.objects.filter(batch=batch, excel_row_number=3).select_related("batch__brand").get()
        row.cleaned_data["document"] = "VDD-OTHER"
        with self.assertRaises(AnalyticalRowError):
            parse_item_row(row)
