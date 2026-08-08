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
