from django.shortcuts import render


HOME_CONTENT = {
    "ar": {
        "nav_home": "الرئيسية",
        "nav_about": "من نحن",
        "nav_activity": "نشاطنا",
        "nav_brands": "علاماتنا",
        "nav_contact": "اتصل بنا",
        "platform": "دخول المنصة",

        "demo": "نموذج تجريبي",
        "title": "نقرّب العلامات من السوق",
        "subtitle": "شركة توزيع حديثة تربط العلامات التجارية بنقاط البيع من خلال شبكة ميدانية ولوجستية منظمة.",
        "discover": "اكتشف نشاطنا",
        "learn": "تعرّف على DELISKY",
        "stat_1": "مركبات التوزيع",
        "stat_2": "العلامات التجارية",
        "stat_3": "نقاط البيع",
        "stat_4": "مناطق التغطية",
        "visual": "صور DELISKY الحقيقية ستوضع هنا لاحقًا",

        "about_kicker": "من نحن",
        "about_title": "شبكة توزيع تتحرك مع السوق.",
        "about_text": "نبني عملنا حول القرب من السوق، الانضباط التشغيلي، والوصول المنظم إلى نقاط البيع. ونعمل على تحويل التوزيع إلى عملية أكثر وضوحًا وكفاءة.",
        "about_note": "الصورة الرسمية للشركة ستعوض هذا النموذج.",
        "about_point_1": "تغطية ميدانية منظمة",
        "about_point_2": "إدارة فعالة للتوزيع",
        "about_point_3": "رؤية أوضح للسوق",

        "business_kicker": "كيف نعمل",
        "business_title": "من المخزن إلى نقطة البيع.",
        "business_text": "نظام توزيع مبني على التنظيم، التغطية، والمتابعة الميدانية.",
        "business_1_title": "التوزيع المباشر",
        "business_1_text": "توصيل المنتجات إلى نقاط البيع ضمن مسارات توزيع منظمة.",
        "business_2_title": "البيع المسبق",
        "business_2_text": "العمل على الطلبيات المسجلة مسبقًا وتنظيم عملية التوزيع حسب حاجة السوق.",
        "business_3_title": "التغطية التجارية",
        "business_3_text": "متابعة الوصول إلى نقاط البيع ودعم حضور العلامات في السوق.",

        "brands_kicker": "محفظة العلامات",
        "brands_title": "علامات تصل إلى السوق عبر شبكة واحدة.",
        "brands_text": "سنضع هنا الشعارات والمعلومات الرسمية لكل علامة عند توفرها.",
        "brand_placeholder": "الشعار الرسمي لاحقًا",
    },

    "en": {
        "nav_home": "Home",
        "nav_about": "About us",
        "nav_activity": "Our business",
        "nav_brands": "Our brands",
        "nav_contact": "Contact",
        "platform": "Access platform",

        "demo": "Demo website",
        "title": "Bringing brands closer to the market",
        "subtitle": "A modern distribution company connecting brands with points of sale through an organized field and logistics network.",
        "discover": "Discover our business",
        "learn": "About DELISKY",
        "stat_1": "Distribution vehicles",
        "stat_2": "Brands",
        "stat_3": "Points of sale",
        "stat_4": "Coverage areas",
        "visual": "Real DELISKY photography will be placed here later",

        "about_kicker": "About us",
        "about_title": "A distribution network that moves with the market.",
        "about_text": "Our work is built around market proximity, operational discipline and organized access to points of sale. We aim to make distribution clearer, more efficient and more responsive.",
        "about_note": "Official company photography will replace this visual.",
        "about_point_1": "Organized field coverage",
        "about_point_2": "Efficient distribution management",
        "about_point_3": "Clearer market visibility",

        "business_kicker": "How we work",
        "business_title": "From warehouse to point of sale.",
        "business_text": "A distribution operation built around organization, coverage and consistent field execution.",
        "business_1_title": "Direct distribution",
        "business_1_text": "Moving products to points of sale through organized distribution routes.",
        "business_2_title": "Pre-sales",
        "business_2_text": "Managing pre-recorded orders and organizing distribution around actual market demand.",
        "business_3_title": "Market coverage",
        "business_3_text": "Supporting brand presence by maintaining consistent coverage of points of sale.",

        "brands_kicker": "Brand portfolio",
        "brands_title": "Brands reaching the market through one network.",
        "brands_text": "Official logos and information for each distributed brand will be added here when available.",
        "brand_placeholder": "Official logo coming later",
    },
}


def home(request):
    language = getattr(request, "LANGUAGE_CODE", "ar")
    content = HOME_CONTENT.get(language, HOME_CONTENT["ar"])

    return render(
        request,
        "website/home.html",
        {
            "content": content,
        },
    )
