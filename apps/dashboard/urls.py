from django.urls import path

from . import views


app_name = "dashboard"

urlpatterns = [
    path(
        "",
        views.manager_dashboard,
        name="manager_dashboard",
    ),
    path(
        "ask-delisky/",
        views.ask_delisky_api,
        name="ask_delisky",
    ),
]
