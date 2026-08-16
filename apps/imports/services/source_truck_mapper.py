from collections.abc import Mapping
from typing import Any

from .value_normalizers import (
    normalize_lookup_text,
    normalize_text,
)


class SourceTruckMappingError(ValueError):
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


def _canonical_target_code(value: object) -> str | None:
    cleaned = normalize_text(value)

    if cleaned is None:
        return None

    return " ".join(cleaned.split()).upper()


def map_source_truck_code(
    source_code: object,
    *,
    mapping: Mapping[object, object],
) -> str:
    normalized_source = normalize_lookup_text(source_code)

    if normalized_source is None:
        raise SourceTruckMappingError(
            "missing_source_truck_code",
            "The source truck code is required.",
        )

    matched_targets: dict[str, str] = {}

    for mapped_source, target_code in mapping.items():
        if (
            normalize_lookup_text(mapped_source)
            != normalized_source
        ):
            continue

        canonical_target = _canonical_target_code(
            target_code
        )

        if canonical_target is None:
            raise SourceTruckMappingError(
                "invalid_target_truck_code",
                (
                    "The mapped DELISKY BI truck code "
                    "cannot be blank."
                ),
                details={
                    "source_code": str(source_code),
                },
            )

        normalized_target = normalize_lookup_text(
            canonical_target
        )

        matched_targets[
            normalized_target
        ] = canonical_target

    if not matched_targets:
        raise SourceTruckMappingError(
            "source_truck_not_mapped",
            (
                "The source truck code has no explicit "
                "DELISKY BI mapping."
            ),
            details={
                "source_code": str(source_code),
            },
        )

    if len(matched_targets) > 1:
        raise SourceTruckMappingError(
            "ambiguous_source_truck_mapping",
            (
                "The source truck code maps to more than "
                "one DELISKY BI truck code."
            ),
            details={
                "source_code": str(source_code),
                "target_codes": sorted(
                    matched_targets.values()
                ),
            },
        )

    return next(iter(matched_targets.values()))
