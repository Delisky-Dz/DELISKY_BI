from apps.imports.models import ImportSourceSystem

from .raw_items_quantity_enrichment import (
    ItemsQuantityStatus,
    QTY_SOLD_FIELD,
    enrich_raw_items_quantity,
)
from .report_row_cleaner import (
    CleanedReportRow,
    ReportCleaningResult,
    RowCleaningIssue,
    SEVERITY_ERROR,
    STATUS_EXCLUDED,
    STATUS_STOPPED,
)


_BLOCKING_STATUSES = {
    ItemsQuantityStatus.MISSING_BUSINESS_QUANTITY,
    ItemsQuantityStatus.INVALID_BUSINESS_QUANTITY,
    ItemsQuantityStatus.UNKNOWN_PRODUCT,
    ItemsQuantityStatus.UNKNOWN_PACKAGING,
    ItemsQuantityStatus.AMBIGUOUS_PRODUCT,
}


def _quantity_issue(
    enrichment,
) -> RowCleaningIssue | None:
    status = enrichment.status

    if status == ItemsQuantityStatus.READY:
        return None

    messages = {
        ItemsQuantityStatus.MISSING_BUSINESS_QUANTITY: (
            "The official Items Qte total-unit quantity "
            "is missing."
        ),
        ItemsQuantityStatus.INVALID_BUSINESS_QUANTITY: (
            "The official Items Qte total-unit quantity "
            "is invalid."
        ),
        ItemsQuantityStatus.UNKNOWN_PRODUCT: (
            "The Items product does not exist in the "
            "source product master."
        ),
        ItemsQuantityStatus.UNKNOWN_PACKAGING: (
            "The Items product packaging is unknown."
        ),
        ItemsQuantityStatus.AMBIGUOUS_PRODUCT: (
            "The Items product matches more than one "
            "source product."
        ),
    }

    return RowCleaningIssue(
        code=f"items_{status.value.lower()}",
        severity=SEVERITY_ERROR,
        message=messages[status],
        field=QTY_SOLD_FIELD,
        raw_value=(
            enrichment.business_quantity_raw
        ),
        details={
            "packaging_status": status.value,
            "error_code": enrichment.error_code,
            "match_method": (
                enrichment.match_method
            ),
            "product_packaging_id": (
                enrichment.product.pk
                if enrichment.product is not None
                else None
            ),
            "authoritative_field": QTY_SOLD_FIELD,
        },
    )

def _enriched_cleaned_values(
    row: CleanedReportRow,
    enrichment,
) -> tuple[tuple[str, object], ...]:
    cleaned = row.cleaned_dict()

    cleaned.update(
        {
            "source_quantity": (
                enrichment.source_total_units
            ),
            "business_quantity_raw": (
                enrichment.business_quantity_raw
            ),
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
            "quantity_matches_source": (
                enrichment.quantity_matches_source
            ),
        }
    )

    return tuple(cleaned.items())


def enrich_raw_items_cleaning_result(
    cleaning_result: ReportCleaningResult,
    *,
    source_system: ImportSourceSystem,
) -> ReportCleaningResult:
    if cleaning_result.report_type != "ITEMS":
        raise ValueError(
            "Items cleaning enrichment requires "
            "an ITEMS cleaning result."
        )

    enriched_rows: list[CleanedReportRow] = []

    for row in cleaning_result.rows:
        if row.status == STATUS_STOPPED:
            enriched_rows.append(row)
            continue

        raw = row.raw_dict()
        cleaned = row.cleaned_dict()

        enrichment = enrich_raw_items_quantity(
            {
                "Article": (
                    cleaned.get("article")
                    or raw.get("Article")
                ),
                "Barcode": raw.get("Barcode"),
                QTY_SOLD_FIELD: raw.get(
                    QTY_SOLD_FIELD
                ),
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
