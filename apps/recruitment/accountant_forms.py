from django import forms

from .models import JobApplication


class ApplicationStatusForm(forms.ModelForm):
    class Meta:
        model = JobApplication
        fields = (
            "status",
        )
        widgets = {
            "status": forms.Select(
                attrs={
                    "class": "accountant-form-input recruitment-status-select",
                }
            ),
        }
