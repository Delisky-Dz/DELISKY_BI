from django.urls import path

from . import public_views


app_name = "recruitment_public"


urlpatterns = [
    path(
        "apply/",
        public_views.application_form,
        name="apply",
    ),
    path(
        "success/",
        public_views.application_success,
        name="success",
    ),
]
