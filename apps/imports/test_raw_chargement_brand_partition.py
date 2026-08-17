from django.test import TestCase

from apps.fleet.models import Truck
from apps.imports.models import DistributionBrand
from apps.imports.services.raw_chargement_file import (
    AdaptedChargementRow,
)
from apps.imports.services.raw_chargement_brand_partition import (
    partition_raw_chargement_rows_by_brand,
)


class RawChargementBrandPartitionTests(TestCase):
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

        Truck.objects.create(
            internal_code="DELISKY LIV01",
            distribution_brand=self.delisky,
            registration_number="PART-DELISKY-01",
            brand="TEST BRAND",
            model="TEST MODEL",
        )

        Truck.objects.create(
            internal_code="NITA LIV01",
            distribution_brand=self.nita,
            registration_number="PART-NITA-01",
            brand="TEST BRAND",
            model="TEST MODEL",
        )

    def test_partitions_rows_by_truck_distribution_brand(self):
        rows = (
            AdaptedChargementRow(
                excel_row_number=2,
                values={
                    "VAN": "DELISKY LIV01",
                    "Qt\u00e9": 10,
                    "Article": "ARTICLE A",
                },
            ),
            AdaptedChargementRow(
                excel_row_number=3,
                values={
                    "VAN": "NITA LIV01",
                    "Qt\u00e9": 20,
                    "Article": "ARTICLE B",
                },
            ),
            AdaptedChargementRow(
                excel_row_number=4,
                values={
                    "VAN": "DELISKY LIV01",
                    "Qt\u00e9": 30,
                    "Article": "ARTICLE C",
                },
            ),
        )

        result = partition_raw_chargement_rows_by_brand(
            rows
        )

        self.assertEqual(
            set(result),
            {"DELISKY", "NITA"},
        )

        self.assertEqual(
            [
                row.excel_row_number
                for row in result["DELISKY"]
            ],
            [2, 4],
        )

        self.assertEqual(
            [
                row.excel_row_number
                for row in result["NITA"]
            ],
            [3],
        )
