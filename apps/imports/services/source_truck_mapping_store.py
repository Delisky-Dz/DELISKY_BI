from typing import Any

from apps.imports.models import (
    ImportSourceSystem,
    SourceTruckMapping,
)


class SourceTruckMappingStoreError(Exception):
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


def build_source_truck_mapping(
    source_system_code: str,
) -> dict[str, str]:
    normalized_code = str(
        source_system_code or ""
    ).strip().upper()

    if not normalized_code:
        raise SourceTruckMappingStoreError(
            "source_system_not_found",
            "Source system was not found.",
            details={
                "source_system_code": (
                    source_system_code
                ),
            },
        )

    source_system = (
        ImportSourceSystem.objects
        .filter(code__iexact=normalized_code)
        .first()
    )

    if source_system is None:
        raise SourceTruckMappingStoreError(
            "source_system_not_found",
            "Source system was not found.",
            details={
                "source_system_code": (
                    normalized_code
                ),
            },
        )

    if not source_system.is_active:
        raise SourceTruckMappingStoreError(
            "source_system_inactive",
            "Source system is inactive.",
            details={
                "source_system_id": source_system.pk,
                "source_system_code": (
                    source_system.code
                ),
            },
        )

    mappings = (
        SourceTruckMapping.objects
        .select_related("truck")
        .filter(
            source_system=source_system,
            is_active=True,
        )
        .order_by("source_code", "pk")
    )

    result: dict[str, str] = {}

    for mapping in mappings:
        internal_code = mapping.truck.internal_code

        if not internal_code:
            raise SourceTruckMappingStoreError(
                "truck_internal_code_missing",
                (
                    "Mapped truck does not have "
                    "an internal distribution code."
                ),
                details={
                    "mapping_id": mapping.pk,
                    "truck_id": mapping.truck_id,
                    "source_code": (
                        mapping.source_code
                    ),
                },
            )

        result[mapping.source_code] = (
            internal_code
        )

    return result
