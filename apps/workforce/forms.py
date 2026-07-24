from django import forms

from .models import Worker, WorkerCategory


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
                "\u0627\u0644\u0639\u0627\u0645\u0644 "
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
                "\u0627\u0644\u0639\u0627\u0645\u0644 "
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


class WorkerCategoryForm(forms.ModelForm):
    class Meta:
        model = WorkerCategory

        fields = (
            "name",
            "description",
            "default_can_drive",
            "default_can_sell",
            "default_can_work_in_warehouse",
            "default_can_assist_distribution",
            "default_can_train_workers",
            "sort_order",
            "is_active",
        )

        labels = {
            "name": (
                "\u0627\u0633\u0645 "
                "\u0627\u0644\u0635\u0646\u0641"
            ),
            "description": (
                "\u0627\u0644\u0648\u0635\u0641"
            ),
            "default_can_drive": (
                "\u0627\u0644\u0642\u064a\u0627\u062f\u0629"
            ),
            "default_can_sell": (
                "\u0627\u0644\u0628\u064a\u0639"
            ),
            "default_can_work_in_warehouse": (
                "\u0627\u0644\u0639\u0645\u0644 "
                "\u0641\u064a \u0627\u0644\u0645\u062e\u0632\u0646"
            ),
            "default_can_assist_distribution": (
                "\u0645\u0633\u0627\u0639\u062f\u0629 "
                "\u0627\u0644\u062a\u0648\u0632\u064a\u0639"
            ),
            "default_can_train_workers": (
                "\u062a\u062f\u0631\u064a\u0628 "
                "\u0627\u0644\u0639\u0645\u0627\u0644"
            ),
            "sort_order": (
                "\u0627\u0644\u062a\u0631\u062a\u064a\u0628"
            ),
            "is_active": (
                "\u0627\u0644\u0635\u0646\u0641 "
                "\u0646\u0634\u0637"
            ),
        }

        help_texts = {
            "name": (
                "\u064a\u0645\u0643\u0646 \u062a\u0639\u062f\u064a\u0644 "
                "\u0627\u0644\u0627\u0633\u0645 \u0644\u0627\u062d\u0642\u064b\u0627 "
                "\u062f\u0648\u0646 \u062a\u063a\u064a\u064a\u0631 "
                "\u0627\u0644\u0631\u0645\u0632 \u0627\u0644\u062a\u0642\u0646\u064a."
            ),
            "sort_order": (
                "\u0627\u0644\u0631\u0642\u0645 \u0627\u0644\u0623\u0635\u063a\u0631 "
                "\u064a\u0638\u0647\u0631 \u0623\u0648\u0644\u064b\u0627."
            ),
            "is_active": (
                "\u0639\u0637\u0651\u0644 \u0627\u0644\u0635\u0646\u0641 "
                "\u0628\u062f\u0644 \u062d\u0630\u0641\u0647 "
                "\u0644\u0644\u062d\u0641\u0627\u0638 "
                "\u0639\u0644\u0649 \u0627\u0644\u0633\u062c\u0644\u0627\u062a."
            ),
        }

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "accountant-form-input",
                    "autocomplete": "off",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "accountant-form-textarea",
                    "rows": 4,
                }
            ),
            "sort_order": forms.NumberInput(
                attrs={
                    "class": "accountant-form-input",
                    "min": 0,
                    "step": 1,
                    "dir": "ltr",
                }
            ),
            "default_can_drive": forms.CheckboxInput(
                attrs={
                    "class": "accountant-form-checkbox",
                }
            ),
            "default_can_sell": forms.CheckboxInput(
                attrs={
                    "class": "accountant-form-checkbox",
                }
            ),
            "default_can_work_in_warehouse": (
                forms.CheckboxInput(
                    attrs={
                        "class": (
                            "accountant-form-checkbox"
                        ),
                    }
                )
            ),
            "default_can_assist_distribution": (
                forms.CheckboxInput(
                    attrs={
                        "class": (
                            "accountant-form-checkbox"
                        ),
                    }
                )
            ),
            "default_can_train_workers": (
                forms.CheckboxInput(
                    attrs={
                        "class": (
                            "accountant-form-checkbox"
                        ),
                    }
                )
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "accountant-form-checkbox",
                }
            ),
        }

    def clean_name(self):
        return self.cleaned_data[
            "name"
        ].strip()

    def clean_description(self):
        return self.cleaned_data.get(
            "description",
            "",
        ).strip()
