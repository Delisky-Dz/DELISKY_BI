"""Print-only presentation of the existing Manager analytics and presenters."""
from datetime import date
from decimal import Decimal

from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .access import manager_required
from .manager_filters import build_filter_form, selected_brand_id
from . import manager_views as overview
from . import manager_sales as sales_view
from . import manager_clients as clients
from . import manager_sellers as sellers
from . import manager_fleet_products as fleet
from . import manager_follow_up as follow


def display(value):
    if value is None:
        return "غير متاح"
    if isinstance(value, bool):
        return "متاح" if value else "لا توجد تغطية"
    if isinstance(value, Decimal):
        return f"{value:,.2f}"
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value)


def table(title, rows, columns, *, note=""):
    return {
        "title": title, "note": note,
        "headers": [label for field, label in columns],
        "rows": [
            [
                display(None if (
                    getattr(row, "has_sales_coverage", True) is False
                    and field in {"sold_quantity", "quantity_gap", "sold_to_supplied_percentage"}
                ) else getattr(row, field))
                for field, label in columns
            ]
            for row in rows
        ],
    }


SELLER_COLUMNS = (
    ("worker_name", "البائع"), ("total_sales", "المبيعات (دج)"),
    ("sale_record_count", "سجلات البيع"), ("pos_record_count", "سجلات الزيارات"),
    ("visited_record_count", "تمت الزيارة"), ("not_visited_record_count", "لم تتم الزيارة"),
    ("visit_success_percentage", "نجاح الزيارة (%)"),
)
CLIENT_COLUMNS = (
    ("brand_name", "العلامة"), ("client_name", "الزبون"),
    ("total_sales", "المبيعات (دج)"), ("sale_record_count", "سجلات البيع"),
    ("visit_record_count", "سجلات الزيارات"), ("visited_record_count", "تمت الزيارة"),
    ("not_visited_record_count", "لم تتم الزيارة"),
)
VISIT_COLUMNS = (
    ("brand_name", "العلامة"), ("client_name", "الزبون"),
    ("total_record_count", "السجلات"), ("visited_record_count", "تمت الزيارة"),
    ("not_visited_record_count", "لم تتم الزيارة"),
    ("unique_client_day_count", "أيام الزبون"), ("visit_success_percentage", "النجاح (%)"),
)
MOVEMENT_COLUMNS = (
    ("truck_name", "الشاحنة"), ("article", "المنتج"),
    ("supplied_quantity", "الكمية المتاحة"), ("sold_quantity", "الكمية المباعة"),
    ("quantity_gap", "الفجوة الحسابية"), ("sold_to_supplied_percentage", "البيع / المتاح (%)"),
    ("has_sales_coverage", "تغطية المبيعات"),
)


def build_print_context(form):
    scope = dict(period_start=form.cleaned_data["period_start"],
                 period_end=form.cleaned_data["period_end"],
                 brand_id=selected_brand_id(form))
    indexes = dict(truck_index=overview.build_truck_code_index(),
                   assignment_index=overview.build_assignment_index())
    sales = overview.aggregate_sales(**scope, **indexes)
    visits = overview.aggregate_pos_visits(**scope, **indexes)
    summary = overview._present_overview_summary(sales, visits)
    quality, coverage, products, operational = follow._data_quality(**scope)
    seller_rows = sellers._build_seller_rows(sales=sales, visits=visits)
    sections = []

    def section(title, tables):
        sections.append({"title": title, "tables": tables})

    section("المبيعات", [
        table("حسب الشاحنة", sales_view._present_truck_sales(sales), (
            ("truck_name", "الشاحنة"), ("brand_name", "العلامة"),
            ("total_sales", "المبيعات (دج)"), ("sale_record_count", "السجلات"),
            ("positive_sale_record_count", "عمليات إيجابية"),
            ("zero_total_record_count", "سجلات صفرية"))),
        {"title": "التفاصيل اليومية", "headers": ["التاريخ", "المبيعات (دج)", "السجلات"],
         "rows": [[display(row.sale_date), display(row.metrics.total_sales),
                   display(row.metrics.sale_record_count)] for row in sales.by_date]},
    ])
    section("أداء البائعين والزيارات", [
        table("ترتيب البائعين", sellers._rank_sellers(seller_rows, "sales"), SELLER_COLUMNS),
        table("أداء الزيارات", sellers._rank_sellers(seller_rows, "success"), SELLER_COLUMNS),
        table("أقل البائعين مبيعًا", sellers._lowest_sales(seller_rows), SELLER_COLUMNS),
    ])
    seller_product_tables = [table(group.worker_name, group.products, (
        ("article", "المنتج"), ("supplied_quantity", "الكمية المتاحة"),
        ("sold_quantity", "الكمية المباعة")))
        for group in sellers._present_not_sold_groups(products, limit=None)]
    section("المنتجات غير المباعة حسب البائع", seller_product_tables)
    section("العملاء", [
        table("المبيعات والزيارات — جميع الزبائن", clients._client_sales_rows(sales, visits=visits), CLIENT_COLUMNS),
        table("متابعة الزيارات — جميع الزبائن", clients._client_visit_rows(visits), VISIT_COLUMNS),
        table("زار ولم يشترِ", clients._visited_without_sales(sales=sales, visits=visits), VISIT_COLUMNS),
    ])
    previous_period = clients._previous_period(scope["period_start"], scope["period_end"])
    comparison_note = "لا توجد بيانات كافية للمقارنة"
    trends = ()
    if previous_period:
        previous_sales = overview.aggregate_sales(
            period_start=previous_period[0], period_end=previous_period[1],
            brand_id=scope["brand_id"], **indexes)
        if previous_sales.included_row_count:
            trends = clients._trend_rows(current_sales=sales, previous_sales=previous_sales)
            comparison_note = "فترة المقارنة: من " + display(previous_period[0]) + " إلى " + display(previous_period[1])
    trend_columns = (("brand_name", "العلامة"), ("client_name", "الزبون"),
                     ("previous_sales", "المبيعات السابقة (دج)"), ("current_sales", "المبيعات الحالية (دج)"),
                     ("change_percentage", "التغير (%)"))
    sections[-1]["tables"].extend([
        table("الزبائن المتراجعون", clients._declining_clients(trends), trend_columns, note=comparison_note),
        table("الزبائن المتوقفون", clients._stopped_clients(trends), trend_columns, note=comparison_note),
    ])
    section("الشاحنات", [table("حالة الشاحنات", fleet._status_rows(**scope), (
        ("truck_name", "الشاحنة"), ("status_label", "الحالة"),
        ("sales_activity_count", "نشاط المبيعات"), ("sales_total", "المبيعات (دج)"),
        ("authoritative_stopped_count", "توقف مؤكد"), ("possible_stopped_count", "توقف محتمل")))])
    section("المنتجات", [
        table("التحميل مقابل البيع", fleet._load_vs_sales_rows(products, limit=None), MOVEMENT_COLUMNS),
        table("المنتجات ضعيفة الحركة", fleet._slow_moving_rows(products, limit=None), MOVEMENT_COLUMNS),
        *[table("غير مباع — " + group.truck_name, group.products, MOVEMENT_COLUMNS)
          for group in fleet._not_sold_groups(products, limit=None)],
    ])
    attention = follow._attention(products, operational, quality)
    section("المتابعة والتنبيهات", [table("مركز الانتباه", [attention], (
        ("truck_not_sold_product_count", "منتجات غير مباعة / شاحنة"),
        ("confirmed_stopped_truck_count", "شاحنات متوقفة مؤكدًا"),
        ("possible_stopped_truck_count", "شاحنات يحتمل توقفها"),
        ("conflicting_truck_state_count", "حالات متعارضة"),
        ("attribution_issue_count", "مشكلات الإسناد"))),
        table("الفجوات الحسابية", follow._gap_rows(products, limit=None), (
            ("scope", "النطاق"), ("entity_id", "الرقم"), ("article", "المنتج"),
            ("supplied_quantity", "المتاح"), ("sold_quantity", "المباع"),
            ("analytical_gap", "الفجوة الحسابية"))),
    ])
    section("التغطية الزمنية", [table("تغطية المصادر", coverage, (
        ("source_name", "المصدر"), ("source_row_count", "السجلات المصدرية"),
        ("included_row_count", "السجلات المشمولة"), ("outside_period_count", "خارج الفترة"),
        ("partial_overlap_count", "تداخل جزئي مستبعد")))])
    section("جودة البيانات", [
        table("مشكلات الإسناد والتحذيرات", [quality], (
            ("sales_attribution_issue_count", "المبيعات"), ("pos_attribution_issue_count", "الزيارات"),
            ("items_attribution_issue_count", "المنتجات"),
            ("opening_stock_attribution_issue_count", "المخزون الافتتاحي"),
            ("chargement_attribution_issue_count", "التحميل"),
            ("operational_attribution_issue_count", "الحالة التشغيلية"),
            ("pos_numeric_message_warning_count", "رسائل رقمية"),
            ("pos_duplicate_same_day_warning_count", "تكرار نفس اليوم"))),
        table("الاستبعادات", [follow._exclusion_summary(**scope)], (
            ("approved_batch_count", "دفعات معتمدة"), ("superseded_batch_count", "دفعات مستبدلة"),
            ("excluded_rows", "صفوف مستبعدة"), ("stopped_rows", "صفوف توقف"),
            ("warning_count", "تحذيرات"), ("error_count", "أخطاء"))),
        table("حالة مصادر البيانات", follow._source_status_rows(**scope), (
            ("report_label", "المصدر"), ("approved_batch_count", "دفعات معتمدة"),
            ("latest_period_end", "نهاية آخر فترة"), ("accepted_rows", "صفوف مقبولة"),
            ("excluded_rows", "صفوف مستبعدة"), ("stopped_rows", "صفوف توقف"),
            ("warning_count", "تحذيرات"), ("error_count", "أخطاء"))),
    ])
    return dict(
        sections=sections, overview_summary=summary,
        sales_timeline=overview.present_sales_timeline(sales),
        brand_sales_chart=overview.present_brand_sales_chart(sales, overview._load_brands_by_id(sales)),
        generated_at=timezone.localtime(), selected_brand=form.cleaned_data["brand"], **scope,
    )


@never_cache
@manager_required
def manager_print(request):
    requested, form = build_filter_form(request)
    if not requested or not form.is_valid():
        return render(request, "dashboard/manager_print.html", {"filter_form": form}, status=400)
    return render(request, "dashboard/manager_print.html", build_print_context(form))
