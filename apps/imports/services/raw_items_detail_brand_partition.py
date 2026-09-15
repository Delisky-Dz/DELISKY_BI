from typing import Any, Iterable

from apps.analytics.services.truck_resolver import (
    TruckResolutionStatus,
    build_truck_code_index,
    resolve_truck_by_van,
)
from apps.fleet.models import Truck

from .raw_items_detail_file import AdaptedItemsDetailRow


class RawItemsDetailBrandPartitionError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def partition_raw_items_detail_rows_by_brand(
    rows: Iterable[AdaptedItemsDetailRow],
) -> dict[str, tuple[AdaptedItemsDetailRow, ...]]:
    trucks = (
        Truck.objects
        .select_related("distribution_brand")
        .all()
    )

    truck_index = build_truck_code_index(trucks)

    buckets: dict[
        str,
        list[AdaptedItemsDetailRow],
    ] = {}

    for row in rows:
        van = row.values.get("VAN")

        resolution = resolve_truck_by_van(
            van,
            truck_index=truck_index,
        )

        if (
            resolution.status
            == TruckResolutionStatus.MISSING_VAN
        ):
            raise RawItemsDetailBrandPartitionError(
                "missing_van",
                "The adapted Items detail row has no VAN.",
                details={
                    "excel_row_number": row.excel_row_number,
                    "van": van,
                },
            )

        if (
            resolution.status
            == TruckResolutionStatus.TRUCK_NOT_FOUND
        ):
            raise RawItemsDetailBrandPartitionError(
                "truck_not_found",
                (
                    "The adapted Items detail VAN does not "
                    "match a DELISKY BI truck."
                ),
                details={
                    "excel_row_number": row.excel_row_number,
                    "van": van,
                },
            )

        if (
            resolution.status
            == TruckResolutionStatus.AMBIGUOUS_TRUCK_CODE
        ):
            raise RawItemsDetailBrandPartitionError(
                "ambiguous_truck_code",
                (
                    "The adapted Items detail VAN matches "
                    "more than one DELISKY BI truck."
                ),
                details={
                    "excel_row_number": row.excel_row_number,
                    "van": van,
                    "matching_truck_ids": (
                        resolution.matching_truck_ids
                    ),
                },
            )

        truck = resolution.truck

        if truck is None:
            raise RawItemsDetailBrandPartitionError(
                "truck_resolution_failed",
                "The Items detail truck resolution is invalid.",
                details={
                    "excel_row_number": row.excel_row_number,
                    "van": van,
                },
            )

        distribution_brand = truck.distribution_brand

        if distribution_brand is None:
            raise RawItemsDetailBrandPartitionError(
                "missing_distribution_brand",
                (
                    "The resolved Items detail truck has no "
                    "distribution brand."
                ),
                details={
                    "excel_row_number": row.excel_row_number,
                    "van": van,
                    "truck_id": truck.pk,
                },
            )

        brand_code = str(
            distribution_brand.code or ""
        ).strip().upper()

        if not brand_code:
            raise RawItemsDetailBrandPartitionError(
                "missing_distribution_brand_code",
                (
                    "The resolved Items detail truck distribution "
                    "brand has no code."
                ),
                details={
                    "excel_row_number": row.excel_row_number,
                    "van": van,
                    "truck_id": truck.pk,
                    "distribution_brand_id": distribution_brand.pk,
                },
            )

        if not distribution_brand.is_active:
            raise RawItemsDetailBrandPartitionError(
                "distribution_brand_inactive",
                (
                    "The resolved Items detail truck distribution "
                    "brand is inactive."
                ),
                details={
                    "excel_row_number": row.excel_row_number,
                    "van": van,
                    "truck_id": truck.pk,
                    "brand_code": brand_code,
                    "distribution_brand_id": distribution_brand.pk,
                },
            )

        buckets.setdefault(brand_code, []).append(row)

    return {
        brand_code: tuple(brand_rows)
        for brand_code, brand_rows in buckets.items()
    }
