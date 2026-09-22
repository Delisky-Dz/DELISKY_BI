from datetime import date
from unittest.mock import patch

from django.test import TestCase

from apps.fleet.models import Truck
from apps.imports.models import DistributionBrand, ImportSourceSystem
from apps.imports.services.raw_items_detail_file import (
    AdaptedItemsDetailRow,
    ExcludedItemsDetailSourceRow,
    RawItemsDetailFileResult,
)
from apps.imports.services.raw_items_detail_review import (
    RawItemsDetailReviewError,
    prepare_raw_items_detail_review,
)


class RawItemsDetailReviewTests(TestCase):
    def setUp(self):
        self.source_system = ImportSourceSystem.objects.create(
            code="AIO_WEB", name="AIO", is_active=True
        )
        self.delisky = DistributionBrand.objects.create(
            code="DELISKY", name="DELISKY", is_active=True
        )
        self.nita = DistributionBrand.objects.create(
            code="NITA", name="NITA", is_active=True
        )
        Truck.objects.create(
            internal_code="DELISKY LIV01",
            distribution_brand=self.delisky,
            registration_number="DETAIL-REVIEW-D1",
            brand="DELISKY",
            model="",
        )
        Truck.objects.create(
            internal_code="NITA LIV01",
            distribution_brand=self.nita,
            registration_number="DETAIL-REVIEW-N1",
            brand="NITA",
            model="",
        )

    @staticmethod
    def row(number, van, user):
        return AdaptedItemsDetailRow(
            excel_row_number=number,
            values={
                "VAN": van,
                "Article": "ARTICLE A",
                "Qté vendue": 1,
                "Client": "CLIENT A",
                "Date de vente": "04/07/2026 10:00:00",
                "Utilisateur": user,
                "Document": "VDD-1",
                "Num doc.": 1,
            },
        )

    @patch("apps.imports.services.raw_items_detail_review.enrich_raw_items_cleaning_result")
    @patch("apps.imports.services.raw_items_detail_review.build_source_truck_exclusions")
    @patch("apps.imports.services.raw_items_detail_review.build_source_truck_mapping")
    @patch("apps.imports.services.raw_items_detail_review.adapt_raw_items_detail_file")
    def test_partitions_cleans_and_preserves_exclusion_audit(
        self, adapt, mapping, exclusions, enrich
    ):
        excluded = ExcludedItemsDetailSourceRow(
            excel_row_number=4,
            source_code="RACHID",
            reason="OUT_OF_SCOPE",
            sale_datetime_raw="04/07/2026 10:00:00",
            article="ARTICLE X",
            quantity_raw=1,
            client="CLIENT X",
            document="VDD-X",
            document_number=9,
        )
        adapt.return_value = RawItemsDetailFileResult(
            filename="AIO_Items_DETAIL.xlsx",
            worksheet_name="Classeur",
            rows=(
                self.row(2, "DELISKY LIV01", "VAN1-DELISKY"),
                self.row(3, "NITA LIV01", "VAN1-NITA"),
            ),
            excluded_source_rows=(excluded,),
        )
        mapping.return_value = {}
        exclusions.return_value = {"RACHID": "OUT_OF_SCOPE"}
        enrich.side_effect = lambda result, **kwargs: result

        result = prepare_raw_items_detail_review(
            object(),
            source_system_code="AIO_WEB",
            period_start="2026-04-04",
            period_end="2026-08-26",
            original_filename="AIO_Items_DETAIL.xlsx",
        )

        self.assertEqual(result.period_start, date(2026, 4, 4))
        self.assertEqual(result.period_end, date(2026, 8, 26))
        self.assertEqual(
            [review.brand_code for review in result.brand_reviews],
            ["DELISKY", "NITA"],
        )
        self.assertEqual(
            result.brand_reviews[0].covered_trucks,
            ("DELISKY LIV01",),
        )
        self.assertEqual(
            result.brand_reviews[1].covered_trucks,
            ("NITA LIV01",),
        )
        self.assertEqual(result.excluded_source_rows, (excluded,))
        self.assertEqual(enrich.call_count, 2)

    def test_invalid_period_is_rejected_before_file_read(self):
        with self.assertRaises(RawItemsDetailReviewError) as captured:
            prepare_raw_items_detail_review(
                object(),
                source_system_code="AIO_WEB",
                period_start="2026-08-27",
                period_end="2026-08-26",
            )
        self.assertEqual(captured.exception.code, "invalid_period_range")
