from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .forms import (
    DeliskyUserChangeForm,
    DeliskyUserCreationForm,
    OFFICIAL_ROLE_NAMES,
)


User = get_user_model()

ROLE_LABEL = "\u0627\u0644\u062f\u0648\u0631"
PERSONAL_INFO = (
    "\u0627\u0644\u0645\u0639\u0644\u0648\u0645\u0627\u062a "
    "\u0627\u0644\u0634\u062e\u0635\u064a\u0629"
)
ACCESS_INFO = (
    "\u0627\u0644\u062f\u0648\u0631 "
    "\u0648\u062d\u0627\u0644\u0629 "
    "\u0627\u0644\u062f\u062e\u0648\u0644"
)
IMPORTANT_DATES = (
    "\u0627\u0644\u062a\u0648\u0627\u0631\u064a\u062e "
    "\u0627\u0644\u0645\u0647\u0645\u0629"
)


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class DeliskyUserAdmin(UserAdmin):
    form = DeliskyUserChangeForm
    add_form = DeliskyUserCreationForm

    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "official_role",
        "is_active",
        "is_staff",
        "is_superuser",
    )

    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
    )

    search_fields = (
        "username",
        "first_name",
        "last_name",
        "email",
    )

    ordering = ("username",)
    filter_horizontal = ()

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "username",
                    "password",
                )
            },
        ),
        (
            PERSONAL_INFO,
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "email",
                )
            },
        ),
        (
            ACCESS_INFO,
            {
                "fields": (
                    "role",
                    "is_active",
                )
            },
        ),
        (
            IMPORTANT_DATES,
            {
                "fields": (
                    "last_login",
                    "date_joined",
                )
            },
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "password1",
                    "password2",
                    "first_name",
                    "last_name",
                    "email",
                    "role",
                    "is_active",
                ),
            },
        ),
    )

    readonly_fields = (
        "last_login",
        "date_joined",
    )

    def save_model(self, request, obj, form, change):
        selected_role = form.cleaned_data.get("role")

        if selected_role:
            obj.is_staff = True
            obj.is_superuser = (
                selected_role.name == "Super Admin"
            )

        super().save_model(
            request,
            obj,
            form,
            change,
        )

    @admin.display(
        description=ROLE_LABEL,
        ordering="groups__name",
    )
    def official_role(self, obj):
        return (
            obj.groups.filter(
                name__in=OFFICIAL_ROLE_NAMES,
            )
            .values_list("name", flat=True)
            .first()
            or "-"
        )
