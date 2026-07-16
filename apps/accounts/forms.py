from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group


OFFICIAL_ROLE_NAMES = (
    "Super Admin",
    "Accountant",
    "Manager",
)

ROLE_LABEL = "\u0627\u0644\u062f\u0648\u0631 \u0627\u0644\u0631\u0633\u0645\u064a"


class OfficialRoleFormMixin:
    def configure_role_field(self):
        self.fields["role"].queryset = Group.objects.filter(
            name__in=OFFICIAL_ROLE_NAMES,
        ).order_by("name")

        if self.instance and self.instance.pk:
            current_role = self.instance.groups.filter(
                name__in=OFFICIAL_ROLE_NAMES,
            ).first()

            if current_role:
                self.fields["role"].initial = current_role

    def save_official_role(self):
        selected_role = self.cleaned_data.get("role")

        official_roles = list(
            Group.objects.filter(
                name__in=OFFICIAL_ROLE_NAMES,
            )
        )

        if official_roles:
            self.instance.groups.remove(*official_roles)

        if selected_role:
            self.instance.groups.add(selected_role)


class DeliskyUserCreationForm(
    OfficialRoleFormMixin,
    UserCreationForm,
):
    role = forms.ModelChoiceField(
        queryset=Group.objects.none(),
        required=True,
        label=ROLE_LABEL,
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "is_active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.configure_role_field()

    def _save_m2m(self):
        super()._save_m2m()
        self.save_official_role()


class DeliskyUserChangeForm(
    OfficialRoleFormMixin,
    UserChangeForm,
):
    role = forms.ModelChoiceField(
        queryset=Group.objects.none(),
        required=True,
        label=ROLE_LABEL,
    )

    class Meta(UserChangeForm.Meta):
        model = get_user_model()
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.configure_role_field()

    def _save_m2m(self):
        super()._save_m2m()
        self.save_official_role()
