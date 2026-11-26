from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.views.csrf import csrf_failure as django_csrf_failure

from .forms import DeliskyAuthenticationForm


ROLE_MANAGER = "Manager"
ROLE_ACCOUNTANT = "Accountant"


def csrf_failure(request, reason=""):
    match = request.resolver_match
    if request.method == "POST" and match and match.view_name == "accounts:login":
        if not request.user.is_authenticated:
            messages.warning(request, "انتهت صلاحية صفحة الدخول", extra_tags="login_expired")
        return HttpResponseRedirect(reverse("accounts:login"), status=303)
    return django_csrf_failure(request, reason=reason)


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
