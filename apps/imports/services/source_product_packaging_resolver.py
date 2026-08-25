from dataclasses import dataclass
from enum import StrEnum

from apps.imports.models import (
    ImportSourceSystem,
    SourceProductPackaging,
)


class PackagingResolutionStatus(StrEnum):
    READY = "READY"
    UNKNOWN_PRODUCT = "UNKNOWN_PRODUCT"
    UNKNOWN_PACKAGING = "UNKNOWN_PACKAGING"
    AMBIGUOUS_PRODUCT = "AMBIGUOUS_PRODUCT"


@dataclass(frozen=True, slots=True)
class PackagingResolution:
    status: PackagingResolutionStatus
    product: SourceProductPackaging | None
    match_method: str | None
    candidates_count: int = 0

    @property
    def units_per_carton(self) -> int | None:
        if self.product is None:
            return None

        return self.product.units_per_carton


def normalize_product_text(value) -> str:
    if value is None:
        return ""

    return " ".join(
        str(value)
        .replace("\xa0", " ")
        .split()
    ).upper()


def _resolved(
    product: SourceProductPackaging,
    *,
    match_method: str,
) -> PackagingResolution:
    if (
        product.units_per_carton is None
        or product.needs_review
    ):
        status = (
            PackagingResolutionStatus
            .UNKNOWN_PACKAGING
        )
    else:
        status = (
            PackagingResolutionStatus.READY
        )

    return PackagingResolution(
        status=status,
        product=product,
        match_method=match_method,
        candidates_count=1,
    )


def resolve_source_product_packaging(
    *,
    source_system: ImportSourceSystem,
    barcode=None,
    designation=None,
) -> PackagingResolution:
    normalized_barcode = normalize_product_text(
        barcode
    )
    normalized_designation = normalize_product_text(
        designation
    )

    products = (
        SourceProductPackaging.objects
        .filter(
            source_system=source_system,
            is_active=True,
        )
    )

    if normalized_barcode:
        barcode_candidates = list(
            products.filter(
                barcode__iexact=normalized_barcode,
            )
        )

        if len(barcode_candidates) == 1:
            return _resolved(
                barcode_candidates[0],
                match_method="barcode",
            )

        if len(barcode_candidates) > 1:
            if normalized_designation:
                matching_names = [
                    product
                    for product in barcode_candidates
                    if (
                        product.normalized_designation
                        == normalized_designation
                    )
                ]

                if len(matching_names) == 1:
                    return _resolved(
                        matching_names[0],
                        match_method=(
                            "barcode+designation"
                        ),
                    )

            return PackagingResolution(
                status=(
                    PackagingResolutionStatus
                    .AMBIGUOUS_PRODUCT
                ),
                product=None,
                match_method="barcode",
                candidates_count=len(
                    barcode_candidates
                ),
            )

    if normalized_designation:
        name_candidates = list(
            products.filter(
                normalized_designation=(
                    normalized_designation
                ),
            )
        )

        if len(name_candidates) == 1:
            return _resolved(
                name_candidates[0],
                match_method="designation",
            )

        if len(name_candidates) > 1:
            return PackagingResolution(
                status=(
                    PackagingResolutionStatus
                    .AMBIGUOUS_PRODUCT
                ),
                product=None,
                match_method="designation",
                candidates_count=len(
                    name_candidates
                ),
            )

    return PackagingResolution(
        status=(
            PackagingResolutionStatus
            .UNKNOWN_PRODUCT
        ),
        product=None,
        match_method=None,
        candidates_count=0,
    )