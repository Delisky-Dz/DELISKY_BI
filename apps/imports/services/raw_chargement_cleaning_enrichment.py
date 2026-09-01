from apps.imports.models import ImportSourceSystem

from .raw_chargement_quantity_enrichment import (
    ChargementQuantityStatus,
    enrich_raw_chargement_quantity,
)
from .report_row_cleaner import (
    CleanedReportRow,
    ReportCleaningResult,
    RowCleaningIssue,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    STATUS_EXCLUDED,
    STATUS_STOPPED,
)


_BLOCKING_STATUSES = {
    ChargementQuantityStatus.INVALID_QUANTITY,
    ChargementQuantityStatus.UNKNOWN_PRODUCT,
    ChargementQuantityStatus.UNKNOWN_PACKAGING,
    ChargementQuantityStatus.AMBIGUOUS_PRODUCT,
}


def _uses_packaging_consensus(
    enrichment,
) -> bool:
    return (
        enrichment.status
        == ChargementQuantityStatus.AMBIGUOUS_PRODUCT
        and enrichment.total_units is not None
        and enrichment.units_per_carton is not None
    )


def _quantity_issue(
    enrichment,
) -> RowCleaningIssue | None:
    status = enrichment.status

    if status == ChargementQuantityStatus.READY:
        return None

    if _uses_packaging_consensus(enrichment):
        return RowCleaningIssue(
            code="chargement_ambiguous_product",
            severity=SEVERITY_WARNING,
            message=(
                "The Chargement product matches multiple "
                "source products with the same confirmed "
                "packaging. Quantity was accepted using "
                "packaging consensus without selecting "
                "a product record."
            ),
            field="Article",
            raw_value=enrichment.quantity_raw,
            details={
                "packaging_status":
                    status.value,
                "match_method":
                    enrichment.match_method,
                "product_packaging_id":
                    None,
                "consensus_units_per_carton":
                    enrichment.units_per_carton,
                "total_units":
                    enrichment.total_units,
                "error_code":
                    enrichment.error_code,
            },
        )

    messages = {
        ChargementQuantityStatus.INVALID_QUANTITY: (
            "The Chargement quantity is invalid."
        ),
        ChargementQuantityStatus.UNKNOWN_PRODUCT: (
            "The Chargement product does not exist "
            "in the source product master."
        ),
        ChargementQuantityStatus.UNKNOWN_PACKAGING: (
            "The Chargement product packaging is unknown."
        ),
        ChargementQuantityStatus.AMBIGUOUS_PRODUCT: (
            "The Chargement product matches more than "
            "one source product."
        ),
    }

    field = "Article"

    if (
        status
        == ChargementQuantityStatus.INVALID_QUANTITY
    ):
        field = "Qt\u00e9"

    return RowCleaningIssue(
        code=f"chargement_{status.value.lower()}",
        severity=SEVERITY_ERROR,
        message=messages[status],
        field=field,
        raw_value=enrichment.quantity_raw,
        details={
            "packaging_status": status.value,
            "error_code": enrichment.error_code,
            "match_method": enrichment.match_method,
            "product_packaging_id": (
                enrichment.product.pk
                if enrichment.product is not None
                else None
            ),
            "total_units": enrichment.total_units,
        },
    )


def _enriched_cleaned_values(
    row: CleanedReportRow,
    enrichment,
) -> tuple[tuple[str, object], ...]:
    cleaned = row.cleaned_dict()

    cleaned.update(
        {
            "units_per_carton": (
                enrichment.units_per_carton
            ),
            "total_units": enrichment.total_units,
            "carton_quantity": (
                str(enrichment.carton_quantity)
                if enrichment.carton_quantity
                is not None
                else None
            ),
            "cartons": enrichment.cartons,
            "pieces": enrichment.pieces,
            "packaging_status": (
                enrichment.status.value
            ),
            "product_packaging_id": (
                enrichment.product.pk
                if enrichment.product is not None
                else None
            ),
            "product_match_method": (
                enrichment.match_method
            ),
        }
    )

    return tuple(cleaned.items())


def enrich_raw_chargement_cleaning_result(
    cleaning_result: ReportCleaningResult,
    *,
    source_system: ImportSourceSystem,
) -> ReportCleaningResult:
    if cleaning_result.report_type != "CHARGEMENT":
        raise ValueError(
            "Chargement cleaning enrichment requires "
            "a CHARGEMENT cleaning result."
        )

    enriched_rows: list[CleanedReportRow] = []

    for row in cleaning_result.rows:
        if row.status == STATUS_STOPPED:
            enriched_rows.append(row)
            continue

        raw = row.raw_dict()
        cleaned = row.cleaned_dict()

        enrichment = enrich_raw_chargement_quantity(
            {
                "Article": (
                    cleaned.get("article")
                    or raw.get("Article")
                ),
                "Barcode": raw.get("Barcode"),
                "Qt\u00e9": raw.get("Qt\u00e9"),
            },
            source_system=source_system,
        )

        issue = _quantity_issue(
            enrichment
        )

        issues = list(row.issues)

        if issue is not None:
            issues.append(issue)

        status = row.status

        if (
            enrichment.status
            in _BLOCKING_STATUSES
            and not _uses_packaging_consensus(
                enrichment
            )
        ):
            status = STATUS_EXCLUDED

        enriched_rows.append(
            CleanedReportRow(
                row_number=row.row_number,
                status=status,
                raw_values=row.raw_values,
                cleaned_values=(
                    _enriched_cleaned_values(
                        row,
                        enrichment,
                    )
                ),
                issues=tuple(issues),
            )
        )

    return ReportCleaningResult(
        filename=cleaning_result.filename,
        report_type=cleaning_result.report_type,
        rows=tuple(enriched_rows),
    )
