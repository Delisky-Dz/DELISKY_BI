from django.urls import path

from . import (
    manager_sales,
    manager_sections,
    manager_tools,
    manager_views,
    views,
)


app_name = "dashboard"

urlpatterns = [
    path(
        "",
        manager_views.manager_dashboard,
        name="manager_dashboard",
    ),
    path(
        "sales/<slug:tab>/",
        manager_sales.manager_sales,
        name="manager_sales",
    ),
    path(
        "section/<slug:section>/<slug:item>/",
        manager_sections.manager_section,
        name="manager_section",
    ),
    path(
        "tools/<slug:tool>/",
        manager_tools.manager_tool,
        name="manager_tool",
    ),
    path(
        "ask-delisky/",
        views.ask_delisky_api,
        name="ask_delisky",
    ),
    path(
        "marketing-helper/",
        views.marketing_helper_api,
        name="marketing_helper",
    ),
]
