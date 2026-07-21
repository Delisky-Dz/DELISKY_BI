from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "manager/",
        include("apps.dashboard.urls"),
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
