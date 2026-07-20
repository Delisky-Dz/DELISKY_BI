from datetime import date, datetime
from decimal import Decimal

from django.test import SimpleTestCase

from apps.analytics.services.typed_values import (
    AnalyticalValueError,
    read_optional_date,
    read_optional_decimal,
    read_optional_text,
    read_required_date,
    read_required_datetime,
    read_required_decimal,
    read_required_lookup_text,
    read_required_text,
)


class TypedValuesTests(SimpleTestCase):
    def test_required_text_is_normalized(self):
        result = read_required_text(
            {
                "client": "  Test\u00a0   Client  ",
            },
            "client",
        )

        self.assertEqual(
            result,
            "Test Client",
        )

    def test_optional_blank_text_returns_none(self):
        result = read_optional_text(
            {
                "region": "   ",
            },
            "region",
        )

        self.assertIsNone(result)

    def test_required_lookup_text_is_casefolded(self):
        result = read_required_lookup_text(
            {
                "van_normalized": "  TEST-VAN-001  ",
            },
            "van_normalized",
        )

        self.assertEqual(
            result,
            "test-van-001",
        )

    def test_missing_required_text_has_structured_error(self):
        with self.assertRaises(
            AnalyticalValueError
        ) as context:
            read_required_text(
                {},
                "client",
            )

        error = context.exception

        self.assertEqual(
            error.code,
            "missing_text",
        )
        self.assertEqual(
            error.field_name,
            "client",
        )
        self.assertIsNone(error.raw_value)

    def test_required_decimal_reads_json_string(self):
        result = read_required_decimal(
            {
                "total": "1250.50",
            },
            "total",
        )

        self.assertEqual(
            result,
            Decimal("1250.50"),
        )
        self.assertIsInstance(
            result,
            Decimal,
        )

    def test_decimal_with_comma_is_supported(self):
        result = read_required_decimal(
            {
                "quantity": "15,75",
            },
            "quantity",
        )

        self.assertEqual(
            result,
            Decimal("15.75"),
        )

    def test_optional_blank_decimal_returns_none(self):
        result = read_optional_decimal(
            {
                "quantity": "",
            },
            "quantity",
        )

        self.assertIsNone(result)

    def test_invalid_decimal_has_structured_error(self):
        with self.assertRaises(
            AnalyticalValueError
        ) as context:
            read_required_decimal(
                {
                    "total": "not-a-number",
                },
                "total",
            )

        error = context.exception

        self.assertEqual(
            error.code,
            "invalid_decimal",
        )
        self.assertEqual(
            error.field_name,
            "total",
        )
        self.assertEqual(
            error.raw_value,
            "not-a-number",
        )

    def test_missing_required_decimal_is_rejected(self):
        with self.assertRaises(
            AnalyticalValueError
        ) as context:
            read_required_decimal(
                {},
                "total",
            )

        self.assertEqual(
            context.exception.code,
            "missing_decimal",
        )

    def test_required_date_reads_json_string(self):
        result = read_required_date(
            {
                "visit_date": "2026-07-19",
            },
            "visit_date",
        )

        self.assertEqual(
            result,
            date(2026, 7, 19),
        )
        self.assertIsInstance(
            result,
            date,
        )

    def test_optional_blank_date_returns_none(self):
        result = read_optional_date(
            {
                "visit_date": None,
            },
            "visit_date",
        )

        self.assertIsNone(result)

    def test_required_datetime_reads_json_string(self):
        result = read_required_datetime(
            {
                "sale_datetime": "2026-07-19T10:30:45",
            },
            "sale_datetime",
        )

        self.assertEqual(
            result,
            datetime(
                2026,
                7,
                19,
                10,
                30,
                45,
            ),
        )
        self.assertIsNone(result.tzinfo)

    def test_invalid_date_has_structured_error(self):
        with self.assertRaises(
            AnalyticalValueError
        ) as context:
            read_required_date(
                {
                    "visit_date": "invalid-date",
                },
                "visit_date",
            )

        error = context.exception

        self.assertEqual(
            error.code,
            "invalid_date",
        )
        self.assertEqual(
            error.field_name,
            "visit_date",
        )
