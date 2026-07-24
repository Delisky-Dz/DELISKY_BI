from django.urls import path

from . import views


app_name = "fleet"


urlpatterns = [
    path(
        "assignments/",
        views.assignment_list,
        name="assignment_list",
    ),
    path(
        "assignments/add/",
        views.assignment_create,
        name="assignment_create",
    ),
    path(
        "assignments/<int:assignment_id>/edit/",
        views.assignment_update,
        name="assignment_update",
    ),
    path(
        "assignments/<int:assignment_id>/end/",
        views.assignment_end,
        name="assignment_end",
    ),
    path(
        "trucks/",
        views.truck_list,
        name="truck_list",
    ),
    path(
        "trucks/add/",
        views.truck_create,
        name="truck_create",
    ),
    path(
        "trucks/<int:truck_id>/edit/",
        views.truck_update,
        name="truck_update",
    ),
    path(
        "trucks/<int:truck_id>/toggle-status/",
        views.truck_toggle_status,
        name="truck_toggle_status",
    ),
]
