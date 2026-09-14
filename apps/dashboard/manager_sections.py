from django.http import Http404
from django.shortcuts import render

from .access import (
    can_use_ai_assistants,
    manager_required,
)
from .manager_clients import (
    build_client_section_response,
)
from .manager_filters import (
    build_filter_form,
    manager_filter_query,
)
from .manager_fleet_products import (
    build_fleet_product_section_response,
)
from .manager_follow_up import (
    build_follow_up_section_response,
)
from .manager_sellers import (
    build_seller_section_response,
)


SECTION_TEMPLATE_NAME = (
    "dashboard/manager_section_placeholder.html"
)
SECTION_ITEMS = {
    "sellers": {
        "rankings": "ترتيب البائعين",
        "visits": "أداء الزيارات",
        "lowest-sales": "أقل البائعين مبيعًا",
        "not-sold": "المنتجات غير المباعة",
        "card": "بطاقة بائع",
    },
    "clients": {
        "overview": "نظرة عامة على الزبائن",
        "top": "أهم الزبائن",
        "declining": "الزبائن المتراجعون",
        "stopped": "الزبائن المتوقفون",
        "visited-no-sale": "زار ولم يشترِ",
        "visits": "متابعة الزيارات",
        "card": "بطاقة زبون",
    },
    "fleet-products": {
        "not-sold": "المنتجات غير المباعة",
        "slow-moving": "المنتجات ضعيفة الحركة",
        "load-vs-sales": "التحميل مقابل البيع",
        "truck-status": "حالة الشاحنات",
        "truck": "تفاصيل شاحنة",
        "product": "تفاصيل منتج",
    },
    "follow-up": {
        "attention": "مركز الانتباه",
        "data-quality": "جودة البيانات",
        "gaps": "الفجوات الحسابية",
        "coverage": "التغطية الزمنية",
        "exclusions": "الاستبعادات",
        "sources": "حالة مصادر البيانات",
    },
}
SECTION_LABELS = {
    "sellers": "البائعون",
    "clients": "الزبائن",
    "fleet-products": "الشاحنات والمنتجات",
    "follow-up": "المتابعة",
}


@manager_required
def manager_section(request, section, item):
    section_items = SECTION_ITEMS.get(section)

    if (
        section_items is None
        or item not in section_items
    ):
        raise Http404

    if section == "sellers":
        return build_seller_section_response(
            request,
            item=item,
            item_label=section_items[item],
        )

    if section == "clients":
        return build_client_section_response(
            request,
            item=item,
            item_label=section_items[item],
        )

    if section == "fleet-products":
        return build_fleet_product_section_response(
            request,
            item=item,
            item_label=section_items[item],
        )

    if section == "follow-up":
        return build_follow_up_section_response(
            request,
            item=item,
            item_label=section_items[item],
        )

    filter_requested, filter_form = (
        build_filter_form(request)
    )

    response_status = 200

    if filter_requested and not filter_form.is_valid():
        response_status = 400

    context = {
        "active_section": section,
        "active_item": f"{section}-{item}",
        "manager_query": manager_filter_query(
            request
        ),
        "filter_reset_url": request.path,
        "filter_requested": filter_requested,
        "filter_form": filter_form,
        "can_use_ai_assistants": can_use_ai_assistants(
            request.user
        ),
        "section_label": SECTION_LABELS[section],
        "item_label": section_items[item],
        "section_key": section,
        "item_key": item,
    }

    return render(
        request,
        SECTION_TEMPLATE_NAME,
        context,
        status=response_status,
    )
