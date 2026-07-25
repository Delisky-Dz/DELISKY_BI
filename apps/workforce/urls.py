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
        "<int:worker_id>/",
        views.worker_detail,
        name="worker_detail",
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
        "<int:worker_id>/positions/add/",
        views.worker_position_create,
        name="worker_position_create",
    ),
    path(
        (
            "<int:worker_id>/positions/"
            "<int:position_id>/edit/"
        ),
        views.worker_position_update,
        name="worker_position_update",
    ),
    path(
        (
            "<int:worker_id>/positions/"
            "<int:position_id>/end/"
        ),
        views.worker_position_end,
        name="worker_position_end",
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

    path(
        "capabilities/",
        views.capability_list,
        name="capability_list",
    ),
    path(
        "capabilities/add/",
        views.capability_create,
        name="capability_create",
    ),
    path(
        "capabilities/<int:capability_id>/edit/",
        views.capability_update,
        name="capability_update",
    ),
    path(
        (
            "capabilities/"
            "<int:capability_id>/toggle-status/"
        ),
        views.capability_toggle_status,
        name="capability_toggle_status",
    ),
]
