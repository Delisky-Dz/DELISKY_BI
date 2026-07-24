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

    path(
        "categories/",
        views.category_list,
        name="category_list",
    ),
    path(
        "categories/add/",
        views.category_create,
        name="category_create",
    ),
    path(
        "categories/<int:category_id>/edit/",
        views.category_update,
        name="category_update",
    ),
    path(
        "categories/<int:category_id>/toggle-status/",
        views.category_toggle_status,
        name="category_toggle_status",
    ),
]
