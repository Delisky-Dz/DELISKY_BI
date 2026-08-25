from decimal import Decimal

from django.test import SimpleTestCase

from apps.imports.services.product_quantity import (
    ProductQuantityError,
    quantity_from_carton_value,
    quantity_from_total_units,
)


class ProductQuantityTests(SimpleTestCase):
    def test_piece_quantity_to_cartons_and_pieces(self):
        result = quantity_from_total_units(
            34,
            units_per_carton=8,
        )

        self.assertEqual(
            result.total_units,
            34,
        )
        self.assertEqual(
            result.cartons,
            4,
        )
        self.assertEqual(
            result.pieces,
            2,
        )
        self.assertEqual(
            result.carton_quantity,
            Decimal("4.25"),
        )

    def test_full_carton_piece_quantity(self):
        result = quantity_from_total_units(
            300,
            units_per_carton=20,
        )

        self.assertEqual(
            result.cartons,
            15,
        )
        self.assertEqual(
            result.pieces,
            0,
        )
        self.assertEqual(
            result.carton_quantity,
            Decimal("15"),
        )

    def test_carton_piece_notation(self):
        result = quantity_from_carton_value(
            "4:2",
            units_per_carton=8,
        )

        self.assertEqual(
            result.total_units,
            34,
        )
        self.assertEqual(
            result.cartons,
            4,
        )
        self.assertEqual(
            result.pieces,
            2,
        )
        self.assertEqual(
            result.carton_quantity,
            Decimal("4.25"),
        )

    def test_real_bifa_mixed_item_case(self):
        result = quantity_from_carton_value(
            "5:5",
            units_per_carton=6,
        )

        self.assertEqual(
            result.total_units,
            35,
        )
        self.assertEqual(
            result.cartons,
            5,
        )
        self.assertEqual(
            result.pieces,
            5,
        )
        self.assertEqual(
            result.carton_quantity,
            Decimal(35) / Decimal(6),
        )

    def test_numeric_carton_count(self):
        result = quantity_from_carton_value(
            15,
            units_per_carton=20,
        )

        self.assertEqual(
            result.total_units,
            300,
        )
        self.assertEqual(
            result.carton_quantity,
            Decimal("15"),
        )

    def test_decimal_carton_value_with_comma(self):
        result = quantity_from_carton_value(
            "4,25",
            units_per_carton=8,
        )

        self.assertEqual(
            result.total_units,
            34,
        )
        self.assertEqual(
            result.cartons,
            4,
        )
        self.assertEqual(
            result.pieces,
            2,
        )

    def test_rejects_piece_remainder_equal_to_carton(self):
        with self.assertRaises(
            ProductQuantityError
        ) as context:
            quantity_from_carton_value(
                "4:8",
                units_per_carton=8,
            )

        self.assertEqual(
            context.exception.code,
            "pieces_exceed_carton_size",
        )

    def test_rejects_fractional_piece_quantity(self):
        with self.assertRaises(
            ProductQuantityError
        ) as context:
            quantity_from_total_units(
                "34.5",
                units_per_carton=8,
            )

        self.assertEqual(
            context.exception.code,
            "fractional_total_units",
        )

    def test_negative_source_units_are_preserved(self):
        result = quantity_from_total_units(
            -10,
            units_per_carton=4,
        )

        self.assertEqual(
            result.total_units,
            -10,
        )
        self.assertEqual(
            result.cartons,
            -2,
        )
        self.assertEqual(
            result.pieces,
            -2,
        )
        self.assertEqual(
            result.carton_quantity,
            Decimal("-2.5"),
        )

    def test_rejects_zero_units_per_carton(self):
        with self.assertRaises(
            ProductQuantityError
        ) as context:
            quantity_from_total_units(
                10,
                units_per_carton=0,
            )

        self.assertEqual(
            context.exception.code,
            "invalid_units_per_carton",
        )