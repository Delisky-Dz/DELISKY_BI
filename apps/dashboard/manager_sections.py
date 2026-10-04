from django.http import Http404

from .access import manager_required
from .manager_clients import (
    build_client_section_response,
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


@manager_required
def manager_section(request, section, item):
    section_items = SECTION_ITEMS.get(section)

    if (
        section_items is None
        or item not in section_items
    ):
        raise Http404

    if section == "sellers":
        builder = build_seller_section_response
    elif section == "clients":
        builder = build_client_section_response
    elif section == "fleet-products":
        builder = build_fleet_product_section_response
    elif section == "follow-up":
        builder = build_follow_up_section_response
    else:
        raise Http404

    return builder(
        request,
        item=item,
        item_label=section_items[item],
    )
