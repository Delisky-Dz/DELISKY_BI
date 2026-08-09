from django.urls import path

from . import accountant_views


app_name = "recruitment_accountant"


urlpatterns = [
    path(
        "",
        accountant_views.application_list,
        name="list",
    ),
    path(
        "<int:application_id>/",
        accountant_views.application_detail,
        name="detail",
    ),
    path(
        "<int:application_id>/status/",
        accountant_views.update_application_status,
        name="update_status",
    ),
    path(
        "<int:application_id>/cv/",
        accountant_views.download_cv,
        name="download_cv",
    ),
]
