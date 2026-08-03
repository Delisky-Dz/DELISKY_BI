from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


MANAGER_ROLE_NAME = "Manager"
ACCOUNTANT_ROLE_NAME = "Accountant"
SUPER_ADMIN_ROLE_NAME = "Super Admin"


def can_access_manager_dashboard(user) -> bool:
    return bool(
        user.is_authenticated
        and user.is_active
        and (
            user.is_superuser
            or user.groups.filter(
                name=MANAGER_ROLE_NAME,
            ).exists()
        )
    )


def can_use_ai_assistants(user) -> bool:
    if not (
        user.is_authenticated
        and user.is_active
    ):
        return False

    if user.is_superuser:
        return False

    role_names = set(
        user.groups.filter(
            name__in=(
                MANAGER_ROLE_NAME,
                ACCOUNTANT_ROLE_NAME,
                SUPER_ADMIN_ROLE_NAME,
            )
        ).values_list(
            "name",
            flat=True,
        )
    )

    blocked_role_names = {
        ACCOUNTANT_ROLE_NAME,
        SUPER_ADMIN_ROLE_NAME,
    }

    return bool(
        MANAGER_ROLE_NAME in role_names
        and role_names.isdisjoint(
            blocked_role_names
        )
    )


def manager_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not can_access_manager_dashboard(
            request.user
        ):
            raise PermissionDenied

        return view_func(
            request,
            *args,
            **kwargs,
        )

    return wrapped_view


def ai_assistant_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not can_use_ai_assistants(
            request.user
        ):
            raise PermissionDenied

        return view_func(
            request,
            *args,
            **kwargs,
        )

    return wrapped_view
