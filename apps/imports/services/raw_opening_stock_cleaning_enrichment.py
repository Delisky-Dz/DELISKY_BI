from apps.imports.models import ImportSourceSystem

from .raw_opening_stock_quantity_enrichment import (
    OpeningStockQuantityStatus,
    enrich_raw_opening_stock_quantity,
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
    OpeningStockQuantityStatus.MISSING_BUSINESS_QUANTITY,
    OpeningStockQuantityStatus.INVALID_BUSINESS_QUANTITY,
    OpeningStockQuantityStatus.UNKNOWN_PRODUCT,
    OpeningStockQuantityStatus.UNKNOWN_PACKAGING,
    OpeningStockQuantityStatus.AMBIGUOUS_PRODUCT,
}


def _quantity_issue(
    enrichment,
) -> RowCleaningIssue | None:
    status = enrichment.status

    if status == OpeningStockQuantityStatus.READY:
        return None

    if (
        status
        == OpeningStockQuantityStatus.SOURCE_QUANTITY_MISMATCH
    ):
        return RowCleaningIssue(
            code="opening_stock_source_quantity_mismatch",
            severity=SEVERITY_WARNING,
            message=(
                "Opening Stock Qté does not match the "
                "official العلبة business quantity."
            ),
            field="العلبة",
            raw_value=enrichment.business_quantity_raw,
            details={
                "source_total_units": (
                    enrichment.source_total_units
                ),
                "official_total_units": (
                    enrichment.total_units
                ),
                "units_per_carton": (
                    enrichment.units_per_carton
                ),
                "authoritative_field": "العلبة",
            },
        )

    if (
        status
        == OpeningStockQuantityStatus.SOURCE_PACKAGING_MISMATCH
    ):
        return RowCleaningIssue(
            code="opening_stock_source_packaging_mismatch",
            severity=SEVERITY_WARNING,
            message=(
                "Opening Stock Colisage does not match "
                "the source Product Master packaging."
            ),
            field="Colisage",
            raw_value=enrichment.source_packaging_raw,
            details={
                "source_units_per_carton": (
                    enrichment.source_units_per_carton
                ),
                "product_master_units_per_carton": (
                    enrichment.units_per_carton
                ),
                "authoritative_packaging": (
                    "source_product_master"
                ),
            },
        )

    if (
        status
        == OpeningStockQuantityStatus
        .SOURCE_QUANTITY_AND_PACKAGING_MISMATCH
    ):
        return RowCleaningIssue(
            code=(
                "opening_stock_source_quantity_"
                "and_packaging_mismatch"
            ),
            severity=SEVERITY_WARNING,
            message=(
                "Opening Stock Qté and Colisage both "
                "differ from the interpreted official "
                "business quantity and Product Master."
            ),
            field="العلبة",
            raw_value=enrichment.business_quantity_raw,
            details={
                "source_total_units": (
                    enrichment.source_total_units
                ),
                "official_total_units": (
                    enrichment.total_units
                ),
                "source_units_per_carton": (
                    enrichment.source_units_per_carton
                ),
                "product_master_units_per_carton": (
                    enrichment.units_per_carton
                ),
                "authoritative_field": "العلبة",
                "authoritative_packaging": (
                    "source_product_master"
                ),
            },
        )

    if (
        status
        == OpeningStockQuantityStatus.INVALID_SOURCE_QUANTITY
    ):
        return RowCleaningIssue(
            code="invalid_opening_stock_source_quantity",
            severity=SEVERITY_WARNING,
            message=(
                "Opening Stock Qté could not be validated, "
                "but العلبة remains the authoritative "
                "business quantity."
            ),
            field="Qté",
            raw_value=enrichment.source_quantity_raw,
            details={
                "official_total_units": (
                    enrichment.total_units
                ),
                "units_per_carton": (
                    enrichment.units_per_carton
                ),
                "authoritative_field": "العلبة",
            },
        )

    if (
        status
        == OpeningStockQuantityStatus.INVALID_SOURCE_PACKAGING
    ):
        return RowCleaningIssue(
            code="invalid_opening_stock_source_packaging",
            severity=SEVERITY_WARNING,
            message=(
                "Opening Stock Colisage could not be "
                "validated, but Product Master packaging "
                "remains authoritative."
            ),
            field="Colisage",
            raw_value=enrichment.source_packaging_raw,
            details={
                "official_total_units": (
                    enrichment.total_units
                ),
                "product_master_units_per_carton": (
                    enrichment.units_per_carton
                ),
                "authoritative_packaging": (
                    "source_product_master"
                ),
            },
        )

    messages = {
        OpeningStockQuantityStatus.MISSING_BUSINESS_QUANTITY: (
            "The official Opening Stock العلبة quantity "
            "is missing."
        ),
        OpeningStockQuantityStatus.INVALID_BUSINESS_QUANTITY: (
            "The official Opening Stock العلبة quantity "
            "is invalid."
        ),
        OpeningStockQuantityStatus.UNKNOWN_PRODUCT: (
            "The Opening Stock product does not exist "
            "in the source Product Master."
        ),
        OpeningStockQuantityStatus.UNKNOWN_PACKAGING: (
            "The Opening Stock product packaging "
            "is unknown."
        ),
        OpeningStockQuantityStatus.AMBIGUOUS_PRODUCT: (
            "The Opening Stock product matches more "
            "than one source product."
        ),
    }

    return RowCleaningIssue(
        code=f"opening_stock_{status.value.lower()}",
        severity=SEVERITY_ERROR,
        message=messages[status],
        field="العلبة",
        raw_value=enrichment.business_quantity_raw,
        details={
            "packaging_status": status.value,
            "error_code": enrichment.error_code,
            "match_method": enrichment.match_method,
            "product_packaging_id": (
                enrichment.product.pk
                if enrichment.product is not None
                else None
            ),
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
            "source_packaging": (
                enrichment.source_units_per_carton
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
            "packaging_matches_product": (
                enrichment.packaging_matches_product
            ),
        }
    )

    return tuple(cleaned.items())


def enrich_raw_opening_stock_cleaning_result(
    cleaning_result: ReportCleaningResult,
    *,
    source_system: ImportSourceSystem,
) -> ReportCleaningResult:
    if cleaning_result.report_type != "OPENING_STOCK":
        raise ValueError(
            "Opening Stock cleaning enrichment requires "
            "an OPENING_STOCK cleaning result."
        )

    enriched_rows: list[CleanedReportRow] = []

    for row in cleaning_result.rows:
        if row.status == STATUS_STOPPED:
            enriched_rows.append(row)
            continue

        raw = row.raw_dict()
        cleaned = row.cleaned_dict()

        enrichment = enrich_raw_opening_stock_quantity(
            {
                "Article": (
                    cleaned.get("article")
                    or raw.get("Article")
                ),
                "Barcode": raw.get("Barcode"),
                "Qté": raw.get("Qté"),
                "Colisage": raw.get("Colisage"),
                "العلبة": raw.get("العلبة"),
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