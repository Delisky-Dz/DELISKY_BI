from django import forms

from .models import Worker


class WorkerForm(forms.ModelForm):
    class Meta:
        model = Worker

        fields = (
            "first_name",
            "last_name",
            "phone",
            "is_active",
            "notes",
        )

        labels = {
            "first_name": "\u0627\u0644\u0627\u0633\u0645",
            "last_name": "\u0627\u0644\u0644\u0642\u0628",
            "phone": (
                "\u0631\u0642\u0645 "
                "\u0627\u0644\u0647\u0627\u062a\u0641"
            ),
            "is_active": (
                "\u0627\u0644\u0628\u0627\u0626\u0639 "
                "\u0646\u0634\u0637"
            ),
            "notes": (
                "\u0645\u0644\u0627\u062d\u0638\u0627\u062a"
            ),
        }

        help_texts = {
            "is_active": (
                "\u0623\u0644\u063a\u0650 "
                "\u0627\u0644\u062a\u062d\u062f\u064a\u062f "
                "\u0644\u062a\u0639\u0637\u064a\u0644 "
                "\u0627\u0644\u0628\u0627\u0626\u0639 "
                "\u062f\u0648\u0646 \u062d\u0630\u0641 "
                "\u0633\u062c\u0644\u0647."
            ),
        }

        widgets = {
            "first_name": forms.TextInput(
                attrs={
                    "class": (
                        "accountant-form-input"
                    ),
                    "autocomplete": "given-name",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": (
                        "accountant-form-input"
                    ),
                    "autocomplete": "family-name",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": (
                        "accountant-form-input"
                    ),
                    "autocomplete": "tel",
                    "dir": "ltr",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": (
                        "accountant-form-checkbox"
                    ),
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": (
                        "accountant-form-textarea"
                    ),
                    "rows": 4,
                }
            ),
        }

    def clean_first_name(self):
        return self.cleaned_data[
            "first_name"
        ].strip()

    def clean_last_name(self):
        return self.cleaned_data[
            "last_name"
        ].strip()

    def clean_phone(self):
        return self.cleaned_data.get(
            "phone",
            "",
        ).strip()

    def clean_notes(self):
        return self.cleaned_data.get(
            "notes",
            "",
        ).strip()
