from django.test import TestCase

from apps.fleet.models import Truck
from apps.imports.models import DistributionBrand
from apps.imports.services.raw_chargement_file import (
    AdaptedChargementRow,
)
from apps.imports.services.raw_chargement_brand_validator import (
    validate_raw_chargement_brand,
)


class RawChargementBrandValidatorTests(TestCase):
    def setUp(self):
        self.delisky = DistributionBrand.objects.create(
            code="DELISKY",
            name="DELISKY",
            is_active=True,
        )
        self.nita = DistributionBrand.objects.create(
            code="NITA",
            name="NITA",
            is_active=True,
        )

    def create_truck(
        self,
        *,
        internal_code,
        registration_number,
        distribution_brand,
    ):
        return Truck.objects.create(
            internal_code=internal_code,
            distribution_brand=distribution_brand,
            registration_number=registration_number,
            brand="TEST BRAND",
            model="TEST MODEL",
        )

    def make_row(
        self,
        *,
        row_number,
        van,
    ):
        return AdaptedChargementRow(
            excel_row_number=row_number,
            values={
                "VAN": van,
                "Qt\u00e9": 10,
                "Article": "ARTICLE TEST",
            },
        )

    def test_accepts_trucks_from_selected_distribution_brand(self):
        self.create_truck(
            internal_code="DELISKY LIV01",
            registration_number="REG-DELISKY-01",
            distribution_brand=self.delisky,
        )

        result = validate_raw_chargement_brand(
            (
                self.make_row(
                    row_number=3,
                    van="DELISKY LIV01",
                ),
            ),
            brand_code="DELISKY",
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.issues, ())

    def test_reports_brand_mismatch_with_excel_row_number(self):
        self.create_truck(
            internal_code="NITA LIV01",
            registration_number="REG-NITA-01",
            distribution_brand=self.nita,
        )

        result = validate_raw_chargement_brand(
            (
                self.make_row(
                    row_number=5,
                    van="NITA LIV01",
                ),
            ),
            brand_code="DELISKY",
        )

        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.issues), 1)

        issue = result.issues[0]

        self.assertEqual(issue.code, "brand_mismatch")
        self.assertEqual(issue.excel_row_number, 5)
        self.assertEqual(issue.van, "NITA LIV01")
        self.assertEqual(
            issue.details["expected_brand_code"],
            "DELISKY",
        )
        self.assertEqual(
            issue.details["actual_brand_code"],
            "NITA",
        )

    def test_reports_ambiguous_normalized_truck_code(self):
        first = self.create_truck(
            internal_code="DELISKY LIV09",
            registration_number="REG-AMBIGUOUS-01",
            distribution_brand=self.delisky,
        )
        second = self.create_truck(
            internal_code=" delisky   liv09 ",
            registration_number="REG-AMBIGUOUS-02",
            distribution_brand=self.delisky,
        )

        result = validate_raw_chargement_brand(
            (
                self.make_row(
                    row_number=11,
                    van="DELISKY LIV09",
                ),
            ),
            brand_code="DELISKY",
        )

        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.issues), 1)

        issue = result.issues[0]

        self.assertEqual(
            issue.code,
            "ambiguous_truck_code",
        )
        self.assertEqual(
            issue.excel_row_number,
            11,
        )
        self.assertEqual(
            issue.details["matching_truck_ids"],
            sorted(
                [
                    first.pk,
                    second.pk,
                ]
            ),
        )

    def test_reports_unknown_truck(self):
        result = validate_raw_chargement_brand(
            (
                self.make_row(
                    row_number=7,
                    van="UNKNOWN LIV01",
                ),
            ),
            brand_code="DELISKY",
        )

        self.assertFalse(result.is_valid)
        self.assertEqual(
            result.issues[0].code,
            "truck_not_found",
        )
        self.assertEqual(
            result.issues[0].excel_row_number,
            7,
        )

    def test_reports_truck_without_distribution_brand(self):
        self.create_truck(
            internal_code="LEGACY LIV01",
            registration_number="REG-LEGACY-01",
            distribution_brand=None,
        )

        result = validate_raw_chargement_brand(
            (
                self.make_row(
                    row_number=9,
                    van="LEGACY LIV01",
                ),
            ),
            brand_code="DELISKY",
        )

        self.assertFalse(result.is_valid)
        self.assertEqual(
            result.issues[0].code,
            "missing_distribution_brand",
        )
        self.assertEqual(
            result.issues[0].excel_row_number,
            9,
        )

    def test_collects_all_brand_validation_issues(self):
        self.create_truck(
            internal_code="NITA LIV02",
            registration_number="REG-NITA-02",
            distribution_brand=self.nita,
        )

        result = validate_raw_chargement_brand(
            (
                self.make_row(
                    row_number=3,
                    van="NITA LIV02",
                ),
                self.make_row(
                    row_number=8,
                    van="UNKNOWN LIV02",
                ),
            ),
            brand_code="DELISKY",
        )

        self.assertFalse(result.is_valid)
        self.assertEqual(
            tuple(
                (
                    issue.excel_row_number,
                    issue.code,
                )
                for issue in result.issues
            ),
            (
                (3, "brand_mismatch"),
                (8, "truck_not_found"),
            ),
        )
