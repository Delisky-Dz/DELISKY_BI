from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse

from .forms import DeliskyAuthenticationForm


ROLE_MANAGER = "Manager"
ROLE_ACCOUNTANT = "Accountant"


class DeliskyLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = DeliskyAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse("accounts:route")


@login_required
def account_route(request):
    user = request.user

    if not user.is_active:
        raise PermissionDenied

    if user.is_superuser:
        return redirect("admin:index")

    if user.groups.filter(
        name=ROLE_MANAGER,
    ).exists():
        return redirect(
            "dashboard:manager_dashboard"
        )

    if user.groups.filter(
        name=ROLE_ACCOUNTANT,
    ).exists():
        return redirect(
            "imports:accountant_home"
        )

    raise PermissionDenied
