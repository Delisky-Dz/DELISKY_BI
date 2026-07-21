from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import DeliskyLoginView, account_route


app_name = "accounts"

urlpatterns = [
    path(
        "login/",
        DeliskyLoginView.as_view(),
        name="login",
    ),
    path(
        "logout/",
        LogoutView.as_view(
            next_page="accounts:login",
        ),
        name="logout",
    ),
    path(
        "account/route/",
        account_route,
        name="route",
    ),
]
