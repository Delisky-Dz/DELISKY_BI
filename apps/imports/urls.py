from django.urls import path

from . import views


app_name = "imports"

urlpatterns = [
    path(
        "",
        views.accountant_home,
        name="accountant_home",
    ),
]
