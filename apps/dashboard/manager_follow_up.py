from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Max, Sum
from django.shortcuts import render

from apps.analytics.services.assignment_resolver import (
    build_assignment_index,
)
from apps.analytics.services.items_aggregation import (
    aggregate_items,
)
from apps.analytics.services.pos_visit_aggregation import (
    aggregate_pos_visits,
)
from apps.analytics.services.product_performance import (
    combine_product_performance,
)
from apps.analytics.services.sales_aggregation import (
    aggregate_sales,
)
from apps.analytics.services.stock_flow_aggregation import (
    aggregate_chargement,
    aggregate_opening_stock,
)
from apps.analytics.services.truck_operational_status import (
    determine_truck_operational_status,
)
from apps.analytics.services.truck_resolver import (
    build_truck_code_index,
)
from apps.imports.models import (
    ImportBatch,
    ImportBatchStatus,
    ImportReportType,
)

from .access import can_use_ai_assistants
from .manager_filters import (
    build_filter_form,
    manager_filter_query,
    selected_brand_id,
)


FOLLOW_UP_TEMPLATE_NAME = "dashboard/manager_follow_up.html"


@dataclass(frozen=True, slots=True)
class AttentionPresentation:
    truck_not_sold_product_count: int
    confirmed_stopped_truck_count: int
    possible_stopped_truck_count: int
    conflicting_truck_state_count: int
    attribution_issue_count: int


@dataclass(frozen=True, slots=True)
class DataQualityPresentation:
    sales_attribution_issue_count: int
    pos_attribution_issue_count: int
    items_attribution_issue_count: int
    opening_stock_attribution_issue_count: int
    chargement_attribution_issue_count: int
    operational_attribution_issue_count: int
    pos_numeric_message_warning_count: int
    pos_duplicate_same_day_warning_count: int

    @property
    def attribution_issue_count(self):
        return (
            self.sales_attribution_issue_count
            + self.pos_attribution_issue_count
            + self.items_attribution_issue_count
            + self.opening_stock_attribution_issue_count
            + self.chargement_attribution_issue_count
            + self.operational_attribution_issue_count
        )

    @property
    def warning_count(self):
        return (
            self.pos_numeric_message_warning_count
            + self.pos_duplicate_same_day_warning_count
        )


@dataclass(frozen=True, slots=True)
class CoverageRow:
    source_name: str
    source_row_count: int
    included_row_count: int
    outside_period_count: int
    partial_overlap_count: int


@dataclass(frozen=True, slots=True)
class GapRow:
    scope: str
    entity_id: int
    article: str
    supplied_quantity: Decimal
    sold_quantity: Decimal
    analytical_gap: Decimal


@dataclass(frozen=True, slots=True)
class ImportSourceStatusRow:
    report_type: str
    report_label: str
    approved_batch_count: int
    latest_period_end: object
    accepted_rows: int
    excluded_rows: int
    stopped_rows: int
    warning_count: int
    error_count: int


@dataclass(frozen=True, slots=True)
class ExclusionSummary:
    approved_batch_count: int
    superseded_batch_count: int
    excluded_rows: int
    stopped_rows: int
    warning_count: int
    error_count: int


def _build_product_sources(
    *,
    period_start,
    period_end,
    brand_id,
):
    truck_index = build_truck_code_index()
    assignment_index = build_assignment_index()

    items = aggregate_items(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
        truck_index=truck_index,
        assignment_index=assignment_index,
    )
    opening_stock = aggregate_opening_stock(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
        truck_index=truck_index,
        assignment_index=assignment_index,
    )
    chargement = aggregate_chargement(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
        truck_index=truck_index,
        assignment_index=assignment_index,
    )
    products = combine_product_performance(
        items_result=items,
        opening_stock_result=opening_stock,
        chargement_result=chargement,
    )

    return (
        truck_index,
        assignment_index,
        items,
        opening_stock,
        chargement,
        products,
    )


def _data_quality(
    *,
    period_start,
    period_end,
    brand_id,
):
    (
        truck_index,
        assignment_index,
        items,
        opening_stock,
        chargement,
        products,
    ) = _build_product_sources(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
    )
    sales = aggregate_sales(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
        truck_index=truck_index,
        assignment_index=assignment_index,
    )
    visits = aggregate_pos_visits(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
        truck_index=truck_index,
        assignment_index=assignment_index,
    )
    operational = determine_truck_operational_status(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
        truck_index=truck_index,
    )

    quality = DataQualityPresentation(
        sales_attribution_issue_count=len(
            sales.attribution_issues
        ),
        pos_attribution_issue_count=len(
            visits.attribution_issues
        ),
        items_attribution_issue_count=(
            products.items_attribution_issue_count
        ),
        opening_stock_attribution_issue_count=(
            products.opening_stock_attribution_issue_count
        ),
        chargement_attribution_issue_count=(
            products.chargement_attribution_issue_count
        ),
        operational_attribution_issue_count=len(
            operational.attribution_issues
        ),
        pos_numeric_message_warning_count=(
            visits.numeric_message_warning_count
        ),
        pos_duplicate_same_day_warning_count=(
            visits.duplicate_same_day_warning_count
        ),
    )

    coverage = (
        CoverageRow(
            "المبيعات",
            sales.source_row_count,
            sales.included_row_count,
            sales.outside_requested_period_count,
            0,
        ),
        CoverageRow(
            "الزيارات / POS",
            visits.source_row_count,
            visits.included_row_count,
            visits.outside_requested_period_count,
            0,
        ),
        CoverageRow(
            "Items",
            items.source_row_count,
            items.included_row_count,
            items.outside_requested_period_count,
            items.partial_overlap_excluded_count,
        ),
        CoverageRow(
            "Opening Stock",
            opening_stock.source_row_count,
            opening_stock.included_row_count,
            opening_stock.outside_requested_period_count,
            opening_stock.partial_overlap_excluded_count,
        ),
        CoverageRow(
            "Chargement",
            chargement.source_row_count,
            chargement.included_row_count,
            chargement.outside_requested_period_count,
            chargement.partial_overlap_excluded_count,
        ),
        CoverageRow(
            "الحالة التشغيلية",
            operational.source_row_count,
            operational.included_evidence_row_count,
            operational.outside_requested_period_count,
            operational.partial_overlap_excluded_count,
        ),
    )

    return (
        quality,
        coverage,
        products,
        operational,
    )


def _gap_rows(products):
    rows = []

    for item in products.worker_products:
        if item.quantities.has_negative_quantity_gap:
            rows.append(
                GapRow(
                    scope="البائع / المسار",
                    entity_id=item.worker_id,
                    article=item.article,
                    supplied_quantity=(
                        item.quantities.supplied_quantity
                    ),
                    sold_quantity=(
                        item.quantities.sold_quantity
                    ),
                    analytical_gap=(
                        item.quantities.analytical_quantity_gap
                    ),
                )
            )

    for item in products.truck_products:
        if item.quantities.has_negative_quantity_gap:
            rows.append(
                GapRow(
                    scope="الشاحنة",
                    entity_id=item.truck_id,
                    article=item.article,
                    supplied_quantity=(
                        item.quantities.supplied_quantity
                    ),
                    sold_quantity=(
                        item.quantities.sold_quantity
                    ),
                    analytical_gap=(
                        item.quantities.analytical_quantity_gap
                    ),
                )
            )

    return tuple(
        sorted(
            rows,
            key=lambda row: (
                row.analytical_gap,
                row.article.casefold(),
                row.scope,
                row.entity_id,
            ),
        )[:100]
    )


def _attention(products, operational, quality):
    return AttentionPresentation(
        truck_not_sold_product_count=(
            products.truck_not_sold_count
        ),
        confirmed_stopped_truck_count=len(
            operational.confirmed_stopped
        ),
        possible_stopped_truck_count=len(
            operational.possible_stopped
        ),
        conflicting_truck_state_count=len(
            operational.conflicting
        ),
        attribution_issue_count=(
            quality.attribution_issue_count
        ),
    )


def _scope_batches(
    queryset,
    *,
    period_start=None,
    period_end=None,
    brand_id=None,
):
    if brand_id is not None:
        queryset = queryset.filter(
            brand_id=brand_id,
        )

    if period_start is not None:
        queryset = queryset.filter(
            period_end__gte=period_start,
        )

    if period_end is not None:
        queryset = queryset.filter(
            period_start__lte=period_end,
        )

    return queryset


def _exclusion_summary(
    *,
    period_start=None,
    period_end=None,
    brand_id=None,
):
    approved = _scope_batches(
        ImportBatch.objects.filter(
            status=ImportBatchStatus.APPROVED,
        ),
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
    )
    superseded = _scope_batches(
        ImportBatch.objects.filter(
            status=ImportBatchStatus.SUPERSEDED,
        ),
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
    )
    totals = approved.aggregate(
        excluded_rows=Sum("excluded_rows"),
        stopped_rows=Sum("stopped_rows"),
        warning_count=Sum("warning_count"),
        error_count=Sum("error_count"),
    )

    return ExclusionSummary(
        approved_batch_count=approved.count(),
        superseded_batch_count=superseded.count(),
        excluded_rows=totals["excluded_rows"] or 0,
        stopped_rows=totals["stopped_rows"] or 0,
        warning_count=totals["warning_count"] or 0,
        error_count=totals["error_count"] or 0,
    )


def _source_status_rows(
    *,
    period_start=None,
    period_end=None,
    brand_id=None,
):
    labels = dict(ImportReportType.choices)
    rows = []

    for report_type, report_label in ImportReportType.choices:
        approved = _scope_batches(
            ImportBatch.objects.filter(
                status=ImportBatchStatus.APPROVED,
                report_type=report_type,
            ),
            period_start=period_start,
            period_end=period_end,
            brand_id=brand_id,
        )
        totals = approved.aggregate(
            latest_period_end=Max("period_end"),
            accepted_rows=Sum("accepted_rows"),
            excluded_rows=Sum("excluded_rows"),
            stopped_rows=Sum("stopped_rows"),
            warning_count=Sum("warning_count"),
            error_count=Sum("error_count"),
        )
        rows.append(
            ImportSourceStatusRow(
                report_type=report_type,
                report_label=labels.get(
                    report_type,
                    report_label,
                ),
                approved_batch_count=approved.count(),
                latest_period_end=(
                    totals["latest_period_end"]
                ),
                accepted_rows=(
                    totals["accepted_rows"] or 0
                ),
                excluded_rows=(
                    totals["excluded_rows"] or 0
                ),
                stopped_rows=(
                    totals["stopped_rows"] or 0
                ),
                warning_count=(
                    totals["warning_count"] or 0
                ),
                error_count=(
                    totals["error_count"] or 0
                ),
            )
        )

    return tuple(rows)


def build_follow_up_section_response(
    request,
    *,
    item,
    item_label,
):
    filter_requested, filter_form = (
        build_filter_form(request)
    )
    response_status = 200
    context_data = {
        "attention": None,
        "data_quality": None,
        "coverage_rows": (),
        "gap_rows": (),
        "exclusion_summary": None,
        "source_status_rows": (),
        "audit_scope_is_filtered": False,
    }

    period_start = None
    period_end = None
    brand_id = None

    if filter_requested:
        if filter_form.is_valid():
            period_start = filter_form.cleaned_data[
                "period_start"
            ]
            period_end = filter_form.cleaned_data[
                "period_end"
            ]
            brand_id = selected_brand_id(filter_form)
            context_data["audit_scope_is_filtered"] = True
        else:
            response_status = 400

    if response_status == 200:
        if item == "exclusions":
            context_data["exclusion_summary"] = (
                _exclusion_summary(
                    period_start=period_start,
                    period_end=period_end,
                    brand_id=brand_id,
                )
            )

        elif item == "sources":
            context_data["source_status_rows"] = (
                _source_status_rows(
                    period_start=period_start,
                    period_end=period_end,
                    brand_id=brand_id,
                )
            )

        elif filter_requested:
            if item == "gaps":
                (
                    _truck_index,
                    _assignment_index,
                    _items,
                    _opening_stock,
                    _chargement,
                    products,
                ) = _build_product_sources(
                    period_start=period_start,
                    period_end=period_end,
                    brand_id=brand_id,
                )
                context_data["gap_rows"] = (
                    _gap_rows(products)
                )
            else:
                (
                    quality,
                    coverage,
                    products,
                    operational,
                ) = _data_quality(
                    period_start=period_start,
                    period_end=period_end,
                    brand_id=brand_id,
                )

                if item == "attention":
                    context_data["attention"] = (
                        _attention(
                            products,
                            operational,
                            quality,
                        )
                    )
                elif item == "data-quality":
                    context_data["data_quality"] = (
                        quality
                    )
                elif item == "coverage":
                    context_data["coverage_rows"] = (
                        coverage
                    )

    context = {
        "active_section": "follow-up",
        "active_item": f"follow-up-{item}",
        "manager_query": manager_filter_query(request),
        "filter_reset_url": request.path,
        "filter_requested": filter_requested,
        "filter_form": filter_form,
        "can_use_ai_assistants": can_use_ai_assistants(
            request.user
        ),
        "section_label": "المتابعة",
        "item_label": item_label,
        "follow_up_item": item,
        **context_data,
    }

    return render(
        request,
        FOLLOW_UP_TEMPLATE_NAME,
        context,
        status=response_status,
    )
