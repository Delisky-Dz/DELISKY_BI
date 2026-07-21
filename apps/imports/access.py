from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


ACCOUNTANT_ROLE_NAME = "Accountant"


def can_access_accountant_area(user) -> bool:
    return bool(
        user.is_authenticated
        and user.is_active
        and (
            user.is_superuser
            or user.groups.filter(
                name=ACCOUNTANT_ROLE_NAME,
            ).exists()
        )
    )


def accountant_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not can_access_accountant_area(
            request.user
        ):
            raise PermissionDenied

        return view_func(
            request,
            *args,
            **kwargs,
        )

    return wrapped_view
