from django.test import TestCase

from apps.fleet.models import Truck
from apps.imports.models import DistributionBrand
from apps.imports.services.raw_items_detail_brand_partition import (
    RawItemsDetailBrandPartitionError,
    partition_raw_items_detail_rows_by_brand,
)
from apps.imports.services.raw_items_detail_file import (
    AdaptedItemsDetailRow,
)


class RawItemsDetailBrandPartitionTests(TestCase):
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
        self.bifa = DistributionBrand.objects.create(
            code="BIFA",
            name="BIFA",
            is_active=True,
        )

        Truck.objects.create(
            internal_code="DELISKY LIV01",
            distribution_brand=self.delisky,
            registration_number="DETAIL-DELISKY-01",
            brand="DELISKY",
            model="",
        )
        Truck.objects.create(
            internal_code="NITA LIV01",
            distribution_brand=self.nita,
            registration_number="DETAIL-NITA-01",
            brand="NITA",
            model="",
        )
        Truck.objects.create(
            internal_code="BIFA PLIV07",
            distribution_brand=self.bifa,
            registration_number="DETAIL-BIFA-PLIV07",
            brand="BIFA",
            model="",
            is_active=False,
        )

    @staticmethod
    def row(number, van):
        return AdaptedItemsDetailRow(
            excel_row_number=number,
            values={
                "VAN": van,
                "Article": "ARTICLE A",
                "Qté vendue": 1,
                "Client": "CLIENT A",
                "Date de vente": "04/07/2026 10:00:00",
                "Utilisateur": "SOURCE",
                "Document": "VDD-1",
                "Num doc.": 1,
            },
        )

    def test_partitions_aio_rows_into_delisky_and_nita(self):
        result = partition_raw_items_detail_rows_by_brand(
            (
                self.row(2, "DELISKY LIV01"),
                self.row(3, "NITA LIV01"),
                self.row(4, "DELISKY LIV01"),
            )
        )

        self.assertEqual(set(result), {"DELISKY", "NITA"})
        self.assertEqual(
            [row.excel_row_number for row in result["DELISKY"]],
            [2, 4],
        )
        self.assertEqual(
            [row.excel_row_number for row in result["NITA"]],
            [3],
        )

    def test_historical_inactive_truck_still_partitions_by_brand(self):
        result = partition_raw_items_detail_rows_by_brand(
            (self.row(20, "BIFA PLIV07"),)
        )

        self.assertEqual(set(result), {"BIFA"})
        self.assertEqual(
            result["BIFA"][0].excel_row_number,
            20,
        )

    def test_unknown_van_reports_excel_row(self):
        with self.assertRaises(
            RawItemsDetailBrandPartitionError
        ) as captured:
            partition_raw_items_detail_rows_by_brand(
                (self.row(99, "UNKNOWN VAN"),)
            )

        self.assertEqual(
            captured.exception.code,
            "truck_not_found",
        )
        self.assertEqual(
            captured.exception.details["excel_row_number"],
            99,
        )
