from django.urls import path

from . import views


app_name = "imports"


urlpatterns = [
    path(
        "raw-chargement/",
        views.raw_chargement_upload,
        name="raw_chargement_upload",
    ),
    path(
        "raw-sales/",
        views.raw_sales_upload,
        name="raw_sales_upload",
    ),
    path(
        "",
        views.accountant_home,
        name="accountant_home",
    ),
    path(
        "batches/<int:batch_id>/",
        views.batch_detail,
        name="batch_detail",
    ),
    path(
        "batches/<int:batch_id>/approve/",
        views.approve_batch,
        name="approve_batch",
    ),
]
