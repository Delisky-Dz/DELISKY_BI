from django.urls import path

from . import views


app_name = "imports"


urlpatterns = [
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
