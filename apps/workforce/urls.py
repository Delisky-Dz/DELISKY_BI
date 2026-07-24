from django.urls import path

from . import views


app_name = "workforce"


urlpatterns = [
    path(
        "",
        views.worker_list,
        name="worker_list",
    ),
    path(
        "add/",
        views.worker_create,
        name="worker_create",
    ),
    path(
        "<int:worker_id>/edit/",
        views.worker_update,
        name="worker_update",
    ),
    path(
        "<int:worker_id>/toggle-status/",
        views.worker_toggle_status,
        name="worker_toggle_status",
    ),
]
