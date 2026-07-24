from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "manager/",
        include("apps.dashboard.urls"),
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
