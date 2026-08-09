from django.contrib import admin
from django.conf.urls.i18n import i18n_patterns
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "manager/",
        include("apps.dashboard.urls"),
    ),
    path(
        "accountant/recruitment/",
        include("apps.recruitment.accountant_urls"),
    ),
    path(
        "accountant/workers/",
        include("apps.workforce.urls"),
    ),
    path(
        "accountant/",
        include("apps.fleet.urls"),
    ),
    path(
        "accountant/",
        include("apps.imports.urls"),
    ),
    path(
        "",
        include("apps.accounts.urls"),
    ),
]

urlpatterns += i18n_patterns(
    path(
        "careers/",
        include("apps.recruitment.public_urls"),
    ),
    path("", include("apps.website.urls")),
)
