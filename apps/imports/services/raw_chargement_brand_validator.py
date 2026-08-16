from dataclasses import dataclass
from typing import Any, Iterable

from apps.analytics.services.truck_resolver import (
    TruckResolutionStatus,
    build_truck_code_index,
    resolve_truck_by_van,
)
from apps.fleet.models import Truck
from apps.imports.services.value_normalizers import (
    normalize_lookup_text,
)

from .raw_chargement_file import AdaptedChargementRow


@dataclass(frozen=True, slots=True)
class RawChargementBrandIssue:
    code: str
    excel_row_number: int
    van: object
    details: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RawChargementBrandValidation:
    issues: tuple[RawChargementBrandIssue, ...]

    @property
    def is_valid(self) -> bool:
        return not self.issues


def validate_raw_chargement_brand(
    rows: Iterable[AdaptedChargementRow],
    *,
    brand_code: str,
) -> RawChargementBrandValidation:
    expected_brand_normalized = normalize_lookup_text(
        brand_code
    )

    trucks = (
        Truck.objects
        .select_related("distribution_brand")
        .all()
    )

    truck_index = build_truck_code_index(
        trucks
    )

    issues: list[RawChargementBrandIssue] = []

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
            issues.append(
                RawChargementBrandIssue(
                    code="missing_van",
                    excel_row_number=(
                        row.excel_row_number
                    ),
                    van=van,
                    details={},
                )
            )
            continue

        if (
            resolution.status
            == TruckResolutionStatus.TRUCK_NOT_FOUND
        ):
            issues.append(
                RawChargementBrandIssue(
                    code="truck_not_found",
                    excel_row_number=(
                        row.excel_row_number
                    ),
                    van=van,
                    details={
                        "normalized_van": (
                            resolution.normalized_van
                        ),
                    },
                )
            )
            continue

        if (
            resolution.status
            == TruckResolutionStatus.AMBIGUOUS_TRUCK_CODE
        ):
            issues.append(
                RawChargementBrandIssue(
                    code="ambiguous_truck_code",
                    excel_row_number=(
                        row.excel_row_number
                    ),
                    van=van,
                    details={
                        "matching_truck_ids": list(
                            resolution.matching_truck_ids
                        ),
                    },
                )
            )
            continue

        truck = resolution.truck

        if truck is None:
            issues.append(
                RawChargementBrandIssue(
                    code="truck_not_found",
                    excel_row_number=(
                        row.excel_row_number
                    ),
                    van=van,
                    details={},
                )
            )
            continue

        distribution_brand = (
            truck.distribution_brand
        )

        if distribution_brand is None:
            issues.append(
                RawChargementBrandIssue(
                    code="missing_distribution_brand",
                    excel_row_number=(
                        row.excel_row_number
                    ),
                    van=van,
                    details={
                        "truck_id": truck.pk,
                    },
                )
            )
            continue

        actual_brand_code = distribution_brand.code

        if (
            normalize_lookup_text(actual_brand_code)
            != expected_brand_normalized
        ):
            issues.append(
                RawChargementBrandIssue(
                    code="brand_mismatch",
                    excel_row_number=(
                        row.excel_row_number
                    ),
                    van=van,
                    details={
                        "truck_id": truck.pk,
                        "expected_brand_code": (
                            brand_code
                        ),
                        "actual_brand_code": (
                            actual_brand_code
                        ),
                    },
                )
            )

    return RawChargementBrandValidation(
        issues=tuple(issues),
    )
