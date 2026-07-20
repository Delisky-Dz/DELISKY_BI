from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from apps.fleet.models import Truck
from apps.imports.services.value_normalizers import (
    normalize_lookup_text,
)


class TruckResolutionStatus(StrEnum):
    MATCHED = "MATCHED"
    MISSING_VAN = "MISSING_VAN"
    TRUCK_NOT_FOUND = "TRUCK_NOT_FOUND"
    AMBIGUOUS_TRUCK_CODE = "AMBIGUOUS_TRUCK_CODE"


@dataclass(frozen=True, slots=True)
class TruckResolution:
    status: TruckResolutionStatus
    normalized_van: str | None
    truck: Truck | None = None
    matching_truck_ids: tuple[int, ...] = ()

    @property
    def is_matched(self) -> bool:
        return (
            self.status == TruckResolutionStatus.MATCHED
            and self.truck is not None
        )


TruckCodeIndex = dict[str, tuple[Truck, ...]]


def build_truck_code_index(
    trucks: Iterable[Truck] | None = None,
) -> TruckCodeIndex:
    """
    Build an in-memory index of Truck.internal_code values.

    Inactive trucks are intentionally included because historical
    analytics must still resolve trucks that are no longer active.
    """
    if trucks is None:
        trucks = Truck.objects.all().only(
            "id",
            "internal_code",
            "registration_number",
            "brand",
            "model",
            "is_active",
        )

    buckets: dict[str, list[Truck]] = {}

    for truck in trucks:
        normalized_code = normalize_lookup_text(
            truck.internal_code
        )

        if normalized_code is None:
            continue

        buckets.setdefault(
            normalized_code,
            [],
        ).append(truck)

    return {
        normalized_code: tuple(matches)
        for normalized_code, matches in buckets.items()
    }


def resolve_truck_by_van(
    van_value: object,
    *,
    truck_index: TruckCodeIndex | None = None,
) -> TruckResolution:
    """
    Resolve a report VAN value against Truck.internal_code only.

    Truck.registration_number is deliberately not used as an
    automatic fallback because VAN is an operational code.
    """
    normalized_van = normalize_lookup_text(van_value)

    if normalized_van is None:
        return TruckResolution(
            status=TruckResolutionStatus.MISSING_VAN,
            normalized_van=None,
        )

    if truck_index is None:
        truck_index = build_truck_code_index()

    matches = truck_index.get(
        normalized_van,
        (),
    )

    matching_truck_ids = tuple(
        sorted(
            truck.pk
            for truck in matches
            if truck.pk is not None
        )
    )

    if not matches:
        return TruckResolution(
            status=TruckResolutionStatus.TRUCK_NOT_FOUND,
            normalized_van=normalized_van,
        )

    if len(matches) > 1:
        return TruckResolution(
            status=(
                TruckResolutionStatus.AMBIGUOUS_TRUCK_CODE
            ),
            normalized_van=normalized_van,
            matching_truck_ids=matching_truck_ids,
        )

    return TruckResolution(
        status=TruckResolutionStatus.MATCHED,
        normalized_van=normalized_van,
        truck=matches[0],
        matching_truck_ids=matching_truck_ids,
    )
