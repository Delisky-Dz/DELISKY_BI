from io import BytesIO

from django.core.files.uploadedfile import (
    SimpleUploadedFile,
)
from django.test import SimpleTestCase
from openpyxl import Workbook

from apps.imports.services.raw_items_detail_file import (
    CANONICAL_ITEMS_DETAIL_HEADERS,
    RawItemsDetailFileError,
    adapt_raw_items_detail_file,
    to_report_row_read_result,
)


class RawItemsDetailFileTests(SimpleTestCase):
    def make_file(
        self,
        rows,
        *,
        headers=None,
        filename="Items_DETAIL.xlsx",
    ):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Classeur"

        worksheet.append(
            headers
            or (
                "Article",
                "Code",
                "Prix",
                "Date de vente",
                "Qté vendue",
                "Utilisateur",
                "Num doc.",
                "Client",
                "Document",
                "Barcode",
                "Total vente",
            )
        )

        for row in rows:
            worksheet.append(row)

        payload = BytesIO()
        workbook.save(payload)
        workbook.close()

        return SimpleUploadedFile(
            filename,
            payload.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            ),
        )

    def test_maps_user_per_row_and_keeps_sale_metadata(self):
        source = self.make_file(
            (
                (
                    "ARTICLE A",
                    "A1",
                    100,
                    "04/04/2026 08:00:00",
                    30,
                    "CV-03",
                    123,
                    "CLIENT A",
                    "VDD-1",
                    "BAR-A",
                    3000,
                ),
                (
                    "ARTICLE B",
                    "B1",
                    200,
                    "05/04/2026 09:00:00",
                    10,
                    "LV-02",
                    124,
                    "CLIENT B",
                    "VDD-2",
                    "BAR-B",
                    2000,
                ),
            )
        )

        result = adapt_raw_items_detail_file(
            source,
            truck_mapping={
                "CV-03": "BIFA LIV03",
                "LV-02": "BIFA PLIV02",
            },
        )

        self.assertEqual(len(result.rows), 2)
        self.assertEqual(
            result.rows[0].values["VAN"],
            "BIFA LIV03",
        )
        self.assertEqual(
            result.rows[1].values["VAN"],
            "BIFA PLIV02",
        )
        self.assertEqual(
            result.rows[0].values["Date de vente"],
            "04/04/2026 08:00:00",
        )
        self.assertEqual(
            result.rows[0].values["Utilisateur"],
            "CV-03",
        )
        self.assertEqual(
            result.rows[0].values["Document"],
            "VDD-1",
        )
        self.assertEqual(
            result.rows[0].values["Num doc."],
            123,
        )

    def test_excluded_program_user_is_audited_not_adapted(self):
        source = self.make_file(
            (
                (
                    "ARTICLE A",
                    "A1",
                    100,
                    "04/04/2026 08:00:00",
                    30,
                    "ADV",
                    123,
                    "CLIENT A",
                    "VDD-1",
                    "BAR-A",
                    3000,
                ),
            )
        )

        result = adapt_raw_items_detail_file(
            source,
            truck_mapping={},
            source_exclusions={
                "ADV": "OUT_OF_SCOPE",
            },
        )

        self.assertEqual(result.rows, ())
        self.assertEqual(
            len(result.excluded_source_rows),
            1,
        )
        excluded = result.excluded_source_rows[0]
        self.assertEqual(excluded.source_code, "ADV")
        self.assertEqual(excluded.reason, "OUT_OF_SCOPE")
        self.assertEqual(excluded.article, "ARTICLE A")
        self.assertEqual(excluded.quantity_raw, 30)
        self.assertEqual(excluded.document, "VDD-1")

    def test_ignores_realistic_aio_summary_footer(self):
        source = self.make_file(
            (
                (
                    "ARTICLE A",
                    None,
                    100,
                    "04/04/2026 08:00:00",
                    10,
                    "NITA-LIVREUR1",
                    123,
                    "CLIENT A",
                    "VDD-1",
                    None,
                    1000,
                ),
                (
                    "ARTICLE B",
                    None,
                    200,
                    "05/04/2026 09:00:00",
                    20,
                    "rachid",
                    124,
                    "CLIENT B",
                    "VDD-2",
                    None,
                    4000,
                ),
                (
                    "2",
                    None,
                    None,
                    None,
                    "30,000",
                    None,
                    None,
                    None,
                    None,
                    None,
                    "5000,00",
                ),
            )
        )

        result = adapt_raw_items_detail_file(
            source,
            truck_mapping={
                "NITA-LIVREUR1": "NITA LIV01",
            },
            source_exclusions={
                "rachid": "OUT_OF_SCOPE",
            },
        )

        self.assertEqual(len(result.rows), 1)
        self.assertEqual(
            len(result.excluded_source_rows),
            1,
        )
        self.assertEqual(
            result.rows[0].excel_row_number,
            2,
        )
        self.assertEqual(
            result.excluded_source_rows[0].excel_row_number,
            3,
        )

    def test_ignores_realistic_bifa_summary_footer(self):
        headers = (
            "Barcode",
            "Code",
            "Article",
            "Prix",
            "Date de vente",
            "Qté vendue",
            "Utilisateur",
            "Num doc.",
            "Client",
            "Document",
            "Total vente",
        )
        source = self.make_file(
            (
                (
                    "BAR-A",
                    "A1",
                    "ARTICLE A",
                    100,
                    "04/04/2026 08:00:00",
                    10,
                    "CV-04",
                    123,
                    "CLIENT A",
                    "VDD-1",
                    1000,
                ),
                (
                    None,
                    None,
                    "1",
                    None,
                    None,
                    "10,000",
                    None,
                    None,
                    None,
                    None,
                    "1000,00",
                ),
            ),
            headers=headers,
        )

        result = adapt_raw_items_detail_file(
            source,
            truck_mapping={
                "CV-04": "BIFA LIV04",
            },
        )

        self.assertEqual(len(result.rows), 1)
        self.assertEqual(
            result.rows[0].values["VAN"],
            "BIFA LIV04",
        )

    def test_unmapped_user_fails_with_excel_row_number(self):
        source = self.make_file(
            (
                (
                    "ARTICLE A",
                    "A1",
                    100,
                    "04/04/2026 08:00:00",
                    10,
                    "UNKNOWN",
                    123,
                    "CLIENT A",
                    "VDD-1",
                    None,
                    1000,
                ),
            )
        )

        with self.assertRaises(
            RawItemsDetailFileError
        ) as captured:
            adapt_raw_items_detail_file(
                source,
                truck_mapping={},
            )

        self.assertEqual(
            captured.exception.code,
            "row_adaptation_failed",
        )
        self.assertEqual(
            captured.exception.details[
                "excel_row_number"
            ],
            2,
        )
        self.assertEqual(
            captured.exception.details[
                "cause_code"
            ],
            "source_truck_not_mapped",
        )

    def test_missing_required_detail_column_reports_row(self):
        source = self.make_file(
            (
                (
                    "ARTICLE A",
                    10,
                    "CV-03",
                ),
            ),
            headers=(
                "Article",
                "Qté vendue",
                "Utilisateur",
            ),
        )

        with self.assertRaises(
            RawItemsDetailFileError
        ) as captured:
            adapt_raw_items_detail_file(
                source,
                truck_mapping={
                    "CV-03": "BIFA LIV03",
                },
            )

        self.assertEqual(
            captured.exception.details[
                "excel_row_number"
            ],
            2,
        )
        self.assertEqual(
            captured.exception.details[
                "cause_code"
            ],
            "missing_required_column",
        )

    def test_converts_to_items_report_rows(self):
        source = self.make_file(
            (
                (
                    "ARTICLE A",
                    "A1",
                    100,
                    "04/04/2026 08:00:00",
                    10,
                    "CV-03",
                    123,
                    "CLIENT A",
                    "VDD-1",
                    "BAR-A",
                    1000,
                ),
            )
        )

        adapted = adapt_raw_items_detail_file(
            source,
            truck_mapping={
                "CV-03": "BIFA LIV03",
            },
        )

        result = to_report_row_read_result(adapted)

        self.assertEqual(result.report_type, "ITEMS")
        self.assertEqual(
            result.headers,
            CANONICAL_ITEMS_DETAIL_HEADERS
            + (
                "Barcode",
                "Prix",
                "Total vente",
            ),
        )
        self.assertEqual(result.rows[0].row_number, 2)
