"""Filename compatibility at the Raw adapters and accountant upload boundary."""
from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from openpyxl import Workbook

from apps.fleet.models import Truck
from apps.imports.models import (
    DistributionBrand, ImportBatch, ImportSourceSystem,
    SourceProductPackaging, SourceTruckMapping,
)
from apps.imports.services.filename_parser import parse_import_filename
from apps.imports.services.raw_sales_file import adapt_raw_sales_file
from apps.imports.services.raw_items_file import adapt_raw_items_file
from apps.imports.services.raw_chargement_file import adapt_raw_chargement_file
from apps.imports.services.raw_opening_stock_file import (
    RawOpeningStockFileError, adapt_raw_opening_stock_file,
)


def workbook_upload(filename, headers, rows):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(headers)
    for row in rows:
        worksheet.append(row)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return SimpleUploadedFile(filename, output.getvalue(), content_type=(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ))


class RawFilenameAdapterCompatibilityTests(SimpleTestCase):
    def test_sales_old_and_new_names_preserve_mapped_source_and_row_date(self):
        for brand in ("DELISKY", "NITA"):
            for number in (1, 2, 3):
                source = f"VAN{number}-{brand}"
                truck = f"{brand} LIV{number:02d}"
                for suffix in ("", " sales", " Sales_2026-04-04_to_2026-08-26",
                               " sales_2026-08-27_to_2026-10-08"):
                    with self.subTest(source=source, suffix=suffix):
                        result = adapt_raw_sales_file(workbook_upload(
                            f"{source}{suffix}.xlsx",
                            ["Date&Heure", "Nom du client", "Total", "Region"],
                            [["27/08/2026 10:00:00", "CLIENT A", 100, "MILA"]],
                        ), truck_mapping={source: truck})
                        self.assertEqual(result.source_truck_code, source)
                        self.assertEqual(result.rows[0].values["VAN"], truck)
                        self.assertEqual(result.rows[0].values["Date&Heure"],
                                         "27/08/2026 10:00:00")

    def test_items_old_and_dated_names_preserve_mapped_source(self):
        for filename in ("DCV-03.xlsx", "DCV-03 items.xlsx",
                         "DCV-03 items_2026-08-27_to_2026-10-08.xlsx"):
            with self.subTest(filename=filename):
                result = adapt_raw_items_file(workbook_upload(
                    filename, ["Article", "Qt\u00e9", "Client"],
                    [["ARTICLE A", 10, "CLIENT A"]],
                ), truck_mapping={"DCV-03": "BIFA LIV03"})
                self.assertEqual(result.source_truck_code, "DCV-03")
                self.assertEqual(result.rows[0].values["VAN"], "BIFA LIV03")
                self.assertEqual(result.rows[0].values["Qt\u00e9 vendue"], 10)

    def test_chargement_names_do_not_override_workbook_sources(self):
        for filename in ("chargement_raw.xlsx",
                         "Chargement_BIFA_2026-03-07_2026-03-11.xlsx",
                         "BIFA_Chargement_2026-08-27_to_2026-10-08.xlsx"):
            with self.subTest(filename=filename):
                result = adapt_raw_chargement_file(workbook_upload(
                    filename, ["Vers l'emplacement", "Qt\u00e9", "Article"],
                    [["SOURCE A", 10, "ARTICLE A"], ["SOURCE B", 20, "ARTICLE B"]],
                ), truck_mapping={"SOURCE A": "DELISKY LIV01", "SOURCE B": "NITA LIV01"})
                self.assertEqual([row.values["VAN"] for row in result.rows],
                                 ["DELISKY LIV01", "NITA LIV01"])

    def test_opening_legacy_export_still_requires_an_explicit_mapping(self):
        headers = ["D\u00e9signation", "Qt\u00e9", "Colisage", "\u0627\u0644\u0639\u0644\u0628\u0629"]
        rows = [["ARTICLE A", 10, 1, 10]]
        result = adapt_raw_opening_stock_file(workbook_upload(
            "VAN1-NITA opning stock.xlsx", headers, rows,
        ), truck_mapping={"VAN1-NITA": "NITA LIV01"})
        self.assertEqual(result.rows[0].values["VAN"], "NITA LIV01")
        with self.assertRaises(RawOpeningStockFileError) as caught:
            adapt_raw_opening_stock_file(workbook_upload(
                "OpeningStock_NITA_01_2026-08-10.xlsx", headers, rows,
            ), truck_mapping={"VAN1-NITA": "NITA LIV01"})
        self.assertEqual(caught.exception.code, "row_adaptation_failed")
        self.assertEqual(caught.exception.details["cause_code"], "source_truck_not_mapped")

    def test_standard_parser_retains_literal_brand_suffix(self):
        parsed = parse_import_filename("OpeningStock_NITA_01_2026-08-10.xlsx")
        self.assertEqual(parsed.brand_code, "NITA_01")
        self.assertEqual(parsed.period_start.isoformat(), "2026-08-10")


class RawFilenameUploadCompatibilityTests(TestCase):
    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        settings = self.settings(MEDIA_ROOT=media.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.user = get_user_model().objects.create_user(username="filename-audit")
        self.user.groups.add(Group.objects.create(name="Accountant"))
        self.client.force_login(self.user)
        self.sources = {}
        for brand_code, source_code, alias in (
            ("NITA", "AIO_WEB", "VAN1-NITA"),
            ("BIFA", "BIFA_MILA", "CV-03"),
        ):
            brand = DistributionBrand.objects.create(code=brand_code, name=brand_code)
            truck = Truck.objects.create(
                internal_code=f"{brand_code} LIV01", distribution_brand=brand,
                registration_number=f"TEST-{brand_code}", brand="TEST", model="TEST",
            )
            source = ImportSourceSystem.objects.create(code=source_code, name=source_code)
            self.sources[brand_code] = source
            SourceTruckMapping.objects.create(source_system=source, source_code=alias,
                                              truck=truck, is_active=True)
            SourceProductPackaging.objects.create(
                source_system=source, source_product_code="TEST-A", barcode="BAR-A",
                designation="ARTICLE A", units_per_carton=1,
                needs_review=False, is_active=True,
            )

    def assert_preview_and_approval(self, batch, brand, start, end):
        self.assertEqual(batch.brand.code, brand)
        self.assertEqual(batch.period_start.isoformat(), start)
        self.assertEqual(batch.period_end.isoformat(), end)
        self.assertEqual(batch.accepted_rows, 1, batch.review_summary)
        self.assertEqual(batch.stopped_rows, 0, batch.review_summary)
        self.assertEqual(batch.rows.get().raw_data["VAN"], f"{brand} LIV01")
        preview = self.client.get(reverse("imports:batch_detail", args=[batch.pk]))
        self.assertEqual(preview.status_code, 200)
        response = self.client.post(reverse("imports:approve_batch", args=[batch.pk]))
        self.assertEqual(response.status_code, 302)
        batch.refresh_from_db()
        self.assertEqual(batch.status, "APPROVED")

    def test_opening_canonical_new_name_uploads_and_approves_using_van_and_ui_date(self):
        # Neither a filename brand nor its date is authoritative in this Raw flow.
        for index, filename in enumerate((
            "OpeningStock_NITA_2026-08-10.xlsx",
            "OpeningStock_NITA_01_2026-08-10.xlsx",
            "OpeningStock_OTHER_99_2026-08-10.xlsx",
        ), start=1):
            with self.subTest(filename=filename):
                stock_date = f"2026-08-{index:02d}"
                response = self.client.post(reverse("imports:raw_opening_stock_upload"), {
                    "stock_date": stock_date,
                    "aio_files": [workbook_upload(filename,
                        ["VAN", "Qt\u00e9", "Article", "Barcode"],
                        [["NITA LIV01", 10 + index, "ARTICLE A", "BAR-A"]])],
                })
                self.assertEqual(response.status_code, 200)
                result = response.context["opening_stock_upload_result"]
                self.assertEqual(result.failed_count, 0, result.files)
                batch = result.files[0].batches[0]
                self.assertEqual(batch.original_filename, filename)
                self.assertEqual(batch.source_upload.source_system_id, self.sources["NITA"].pk)
                self.assert_preview_and_approval(batch, "NITA", stock_date, stock_date)

    def test_items_detail_old_and_new_names_upload_preview_and_approve(self):
        for start, end in (("2026-04-04", "2026-08-26"), ("2026-08-27", "2026-10-08")):
            with self.subTest(start=start):
                filename = f"BIFA_Items_DETAIL_{start}_to_{end}.xlsx"
                response = self.client.post(reverse("imports:raw_items_detail_upload"), {
                    "period_start": start, "period_end": end,
                    "bifa_file": workbook_upload(filename,
                        ["Article", "Code", "Prix", "Date de vente", "Qt\u00e9 vendue",
                         "Utilisateur", "Num doc.", "Client", "Document", "Barcode", "Total vente"],
                        [["ARTICLE A", "TEST-A", 100, f"{start} 10:00:00", 10,
                          "CV-03", 123, "CLIENT A", f"VDD-{start}", "BAR-A", 1000]]),
                })
                self.assertEqual(response.status_code, 200)
                result = response.context["items_detail_upload_result"]
                self.assertEqual(result.failed_count, 0, result.files)
                batch = result.files[0].batches[0]
                self.assertEqual(batch.original_filename, filename)
                self.assertEqual(batch.source_upload.source_system_id, self.sources["BIFA"].pk)
                self.assert_preview_and_approval(batch, "BIFA", start, end)
        self.assertEqual(ImportBatch.objects.filter(status="APPROVED").count(), 2)
