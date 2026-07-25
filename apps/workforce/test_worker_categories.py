from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import WorkerCategory
from .test_category_fixtures import (
    ensure_system_categories,
)


class WorkerCategorySeedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_system_categories()

    EXPECTED_CATEGORIES = (
        (
            "SELLER",
            "بائع ميداني",
            (
                "CAP-SELL",
            ),
            10,
        ),
        (
            "DRIVER",
            "سائق",
            (
                "CAP-DRIVE",
            ),
            20,
        ),
        (
            "DRIVER_SELLER",
            "سائق وبائع",
            (
                "CAP-DRIVE",
                "CAP-SELL",
            ),
            30,
        ),
        (
            "WAREHOUSE_WORKER",
            "عامل مخزن",
            (
                "CAP-WAREHOUSE",
            ),
            40,
        ),
        (
            "DISTRIBUTION_ASSISTANT",
            "مساعد توزيع",
            (
                "CAP-DISTRIBUTION-ASSIST",
            ),
            50,
        ),
        (
            "WAREHOUSE_SUPERVISOR",
            "مسؤول مخزن",
            (
                "CAP-WAREHOUSE",
                "CAP-TRAIN",
            ),
            60,
        ),
        (
            "FIELD_SUPERVISOR",
            "مشرف ميداني",
            (
                "CAP-TRAIN",
            ),
            70,
        ),
        (
            "ACCOUNTANT",
            "محاسب",
            (),
            80,
        ),
        (
            "ADMINISTRATIVE",
            "إداري",
            (),
            90,
        ),
        (
            "OTHER",
            "منصب آخر",
            (),
            100,
        ),
    )

    def test_all_system_categories_are_seeded(
        self,
    ):
        categories = []

        queryset = (
            WorkerCategory.objects
            .filter(
                is_system=True,
            )
            .prefetch_related(
                "default_capabilities",
            )
            .order_by(
                "sort_order",
                "name",
            )
        )

        for category in queryset:
            capability_codes = tuple(
                category
                .default_capabilities
                .order_by(
                    "sort_order",
                    "name",
                )
                .values_list(
                    "code",
                    flat=True,
                )
            )

            categories.append(
                (
                    category.code,
                    category.name,
                    capability_codes,
                    category.sort_order,
                )
            )

        self.assertEqual(
            categories,
            list(
                self.EXPECTED_CATEGORIES
            ),
        )

    def test_system_categories_are_active(self):
        self.assertEqual(
            WorkerCategory.objects.filter(
                is_system=True,
                is_active=True,
            ).count(),
            10,
        )

    def test_system_category_code_is_immutable(self):
        category = WorkerCategory.objects.get(
            code="SELLER",
        )

        original_code = category.code
        category.code = "CHANGED"
        category.name = (
            "\u0645\u0646\u062f\u0648\u0628 "
            "\u0645\u0628\u064a\u0639\u0627\u062a"
        )
        category.save()
        category.refresh_from_db()

        self.assertEqual(
            category.code,
            original_code,
        )
        self.assertEqual(
            category.name,
            (
                "\u0645\u0646\u062f\u0648\u0628 "
                "\u0645\u0628\u064a\u0639\u0627\u062a"
            ),
        )


class WorkerCategoryModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_system_categories()

    def test_custom_category_gets_automatic_code(self):
        category = WorkerCategory.objects.create(
            name="\u0639\u0627\u0645\u0644 \u0635\u064a\u0627\u0646\u0629",
            description=(
                "\u0645\u0633\u0624\u0648\u0644 \u0639\u0646 "
                "\u0627\u0644\u0635\u064a\u0627\u0646\u0629."
            ),
            sort_order=110,
        )

        self.assertRegex(
            category.code,
            r"^WC-\d{5,}$",
        )
        self.assertFalse(category.is_system)
        self.assertTrue(category.is_active)

    def test_custom_category_code_is_immutable(self):
        category = WorkerCategory.objects.create(
            name="\u062d\u0627\u0631\u0633",
        )

        original_code = category.code

        category.code = "MANUAL-CODE"
        category.save()
        category.refresh_from_db()

        self.assertEqual(
            category.code,
            original_code,
        )

    def test_name_and_description_are_trimmed(self):
        category = WorkerCategory.objects.create(
            name=(
                "  \u0639\u0627\u0645\u0644 "
                "\u0646\u0638\u0627\u0641\u0629  "
            ),
            description=(
                "  \u0648\u0635\u0641 "
                "\u0627\u0644\u0635\u0646\u0641.  "
            ),
        )

        self.assertEqual(
            category.name,
            "\u0639\u0627\u0645\u0644 \u0646\u0638\u0627\u0641\u0629",
        )
        self.assertEqual(
            category.description,
            "\u0648\u0635\u0641 \u0627\u0644\u0635\u0646\u0641.",
        )

    def test_duplicate_category_name_is_rejected(self):
        WorkerCategory.objects.create(
            name="\u062a\u0642\u0646\u064a \u0635\u064a\u0627\u0646\u0629",
        )

        duplicate = WorkerCategory(
            name="\u062a\u0642\u0646\u064a \u0635\u064a\u0627\u0646\u0629",
        )

        with self.assertRaises(
            ValidationError
        ):
            duplicate.full_clean()

    def test_categories_follow_sort_order(self):
        custom_category = (
            WorkerCategory.objects.create(
                name="\u0635\u0646\u0641 \u0628\u064a\u0646\u064a",
                sort_order=15,
            )
        )

        ordered_codes = list(
            WorkerCategory.objects.values_list(
                "code",
                flat=True,
            )
        )

        self.assertLess(
            ordered_codes.index("SELLER"),
            ordered_codes.index(
                custom_category.code
            ),
        )
        self.assertLess(
            ordered_codes.index(
                custom_category.code
            ),
            ordered_codes.index("DRIVER"),
        )

    def test_string_representation_contains_name_and_code(
        self,
    ):
        category = WorkerCategory.objects.create(
            name="\u0645\u0631\u0627\u0642\u0628",
        )

        self.assertEqual(
            str(category),
            (
                f"\u0645\u0631\u0627\u0642\u0628 "
                f"\u2014 {category.code}"
            ),
        )
