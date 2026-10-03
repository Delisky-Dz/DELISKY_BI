from datetime import date, datetime

from django.test import SimpleTestCase

from apps.imports.services.raw_items_detail_cleaning import (
    RawItemsDetailCleaningError,
    clean_raw_items_detail_rows,
)
from apps.imports.services.report_row_cleaner import (
    SEVERITY_WARNING,
    STATUS_ACCEPTED,
    STATUS_EXCLUDED,
    STATUS_STOPPED,
)
from apps.imports.services.report_row_reader import (
    RawReportRow,
    ReportRowReadResult,
)


class RawItemsDetailCleaningTests(SimpleTestCase):
    def make_result(self, values):
        headers = tuple(values.keys())
        return ReportRowReadResult(
            filename="items-detail.xlsx",
            report_type="ITEMS",
            worksheet_name="Classeur",
            headers=headers,
            rows=(
                RawReportRow(
                    row_number=2,
                    values=tuple(values.items()),
                ),
            ),
        )

    def base_values(self):
        return {
            "VAN": "BIFA LIV03",
            "Article": "ARTICLE A",
            "Qté vendue": 30,
            "Client": "CLIENT A",
            "Date de vente": "04/07/2026 10:15:30",
            "Utilisateur": "CV-03",
            "Document": "VDD-100",
            "Num doc.": 123,
        }

    def test_parses_sale_datetime_and_keeps_metadata(self):
        result = clean_raw_items_detail_rows(
            self.make_result(self.base_values()),
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
        )

        row = result.rows[0]
        cleaned = row.cleaned_dict()

        self.assertEqual(row.status, STATUS_ACCEPTED)
        self.assertEqual(
            cleaned["sale_datetime"],
            datetime(2026, 7, 4, 10, 15, 30),
        )
        self.assertEqual(cleaned["source_user"], "CV-03")
        self.assertEqual(cleaned["document"], "VDD-100")
        self.assertEqual(cleaned["document_number"], "123")

    def test_missing_client_is_warning_and_transaction_stays_accepted(self):
        values = self.base_values()
        values["Client"] = None

        result = clean_raw_items_detail_rows(
            self.make_result(values),
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
        )

        row = result.rows[0]
        cleaned = row.cleaned_dict()
        missing_client = [
            issue
            for issue in row.issues
            if issue.code == "missing_client"
        ]

        self.assertEqual(row.status, STATUS_ACCEPTED)
        self.assertIsNone(cleaned["client"])
        self.assertIsNone(cleaned["client_normalized"])
        self.assertEqual(len(missing_client), 1)
        self.assertEqual(
            missing_client[0].severity,
            SEVERITY_WARNING,
        )
        self.assertFalse(
            missing_client[0].details[
                "client_analytics_eligible"
            ]
        )

    def test_stopped_indicator_remains_stopped_after_detail_enrichment(self):
        values = self.base_values()
        values["Article"] = None
        values["Qté vendue"] = None
        values["Client"] = None

        result = clean_raw_items_detail_rows(
            self.make_result(values),
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
        )

        row = result.rows[0]

        self.assertEqual(row.status, STATUS_STOPPED)
        self.assertIn(
            "stopped_indicator",
            {issue.code for issue in row.issues},
        )

    def test_invalid_sale_datetime_is_excluded(self):
        values = self.base_values()
        values["Date de vente"] = "not-a-date"

        result = clean_raw_items_detail_rows(
            self.make_result(values),
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
        )

        row = result.rows[0]
        self.assertEqual(row.status, STATUS_EXCLUDED)
        self.assertIn(
            "invalid_datetime",
            {issue.code for issue in row.issues},
        )

    def test_missing_sale_datetime_is_excluded(self):
        values = self.base_values()
        values["Date de vente"] = None

        result = clean_raw_items_detail_rows(
            self.make_result(values),
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
        )

        row = result.rows[0]
        self.assertEqual(row.status, STATUS_EXCLUDED)
        self.assertIn(
            "missing_datetime",
            {issue.code for issue in row.issues},
        )

    def test_sale_datetime_outside_period_is_excluded(self):
        values = self.base_values()
        values["Date de vente"] = "03/04/2026 23:59:59"

        result = clean_raw_items_detail_rows(
            self.make_result(values),
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
        )

        row = result.rows[0]
        self.assertEqual(row.status, STATUS_EXCLUDED)
        self.assertIn(
            "date_outside_period",
            {issue.code for issue in row.issues},
        )

    def test_negative_quantity_stays_excluded_with_datetime(self):
        values = self.base_values()
        values["Qté vendue"] = -1

        result = clean_raw_items_detail_rows(
            self.make_result(values),
            period_start=date(2026, 4, 4),
            period_end=date(2026, 8, 26),
        )

        row = result.rows[0]
        cleaned = row.cleaned_dict()

        self.assertEqual(row.status, STATUS_EXCLUDED)
        self.assertEqual(
            cleaned["sale_datetime"],
            datetime(2026, 7, 4, 10, 15, 30),
        )
        self.assertIn(
            "negative_quantity",
            {issue.code for issue in row.issues},
        )

    def test_rejects_non_items_report_type(self):
        row_result = ReportRowReadResult(
            filename="sales.xlsx",
            report_type="SALES",
            worksheet_name="Classeur",
            headers=(),
            rows=(),
        )

        with self.assertRaises(
            RawItemsDetailCleaningError
        ) as captured:
            clean_raw_items_detail_rows(
                row_result,
                period_start=date(2026, 4, 4),
                period_end=date(2026, 8, 26),
            )

        self.assertEqual(
            captured.exception.code,
            "invalid_report_type",
        )
