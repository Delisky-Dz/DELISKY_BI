from django import forms
from django.db.models import Q

from apps.workforce.models import Worker

from .models import (
    Truck,
    WorkerTruckAssignment,
)


class TruckForm(forms.ModelForm):
    class Meta:
        model = Truck

        fields = (
            "internal_code",
            "registration_number",
            "brand",
            "model",
            "manufacturing_year",
            "is_active",
            "notes",
        )

        labels = {
            "internal_code": (
                "\u0627\u0644\u0631\u0645\u0632 "
                "\u0627\u0644\u062f\u0627\u062e\u0644\u064a"
            ),
            "registration_number": (
                "\u0631\u0642\u0645 "
                "\u0627\u0644\u062a\u0633\u062c\u064a\u0644"
            ),
            "brand": "\u0627\u0644\u0639\u0644\u0627\u0645\u0629",
            "model": "\u0627\u0644\u0637\u0631\u0627\u0632",
            "manufacturing_year": (
                "\u0633\u0646\u0629 "
                "\u0627\u0644\u0635\u0646\u0639"
            ),
            "is_active": (
                "\u0627\u0644\u0634\u0627\u062d\u0646\u0629 "
                "\u0646\u0634\u0637\u0629"
            ),
            "notes": "\u0645\u0644\u0627\u062d\u0638\u0627\u062a",
        }

        help_texts = {
            "internal_code": (
                "\u0631\u0645\u0632 "
                "\u0625\u062c\u0628\u0627\u0631\u064a "
                "\u0648\u0641\u0631\u064a\u062f "
                "\u0644\u0644\u0634\u0627\u062d\u0646\u0629\u060c "
                "\u0648\u064a\u062c\u0628 \u0623\u0646 "
                "\u064a\u0637\u0627\u0628\u0642 "
                "\u0645\u0644\u0641\u0627\u062a Excel."
            ),
            "registration_number": (
                "\u0623\u062f\u062e\u0644 "
                "\u0631\u0642\u0645 "
                "\u0627\u0644\u062a\u0633\u062c\u064a\u0644 "
                "\u0643\u0645\u0627 \u0647\u0648 "
                "\u0641\u064a "
                "\u0627\u0644\u0648\u062b\u0627\u0626\u0642."
            ),
            "is_active": (
                "\u0623\u0644\u063a\u0650 "
                "\u0627\u0644\u062a\u062d\u062f\u064a\u062f "
                "\u0644\u062a\u0639\u0637\u064a\u0644 "
                "\u0627\u0644\u0634\u0627\u062d\u0646\u0629 "
                "\u062f\u0648\u0646 \u062d\u0630\u0641 "
                "\u0633\u062c\u0644\u0647\u0627."
            ),
        }

        widgets = {
            "internal_code": forms.TextInput(
                attrs={
                    "class": "accountant-form-input",
                    "autocomplete": "off",
                    "dir": "ltr",
                }
            ),
            "registration_number": forms.TextInput(
                attrs={
                    "class": "accountant-form-input",
                    "autocomplete": "off",
                    "dir": "ltr",
                }
            ),
            "brand": forms.TextInput(
                attrs={
                    "class": "accountant-form-input",
                    "autocomplete": "off",
                }
            ),
            "model": forms.TextInput(
                attrs={
                    "class": "accountant-form-input",
                    "autocomplete": "off",
                }
            ),
            "manufacturing_year": forms.NumberInput(
                attrs={
                    "class": "accountant-form-input",
                    "min": 1900,
                    "max": 2100,
                    "inputmode": "numeric",
                    "dir": "ltr",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "accountant-form-checkbox",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "accountant-form-textarea",
                    "rows": 4,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields[
            "internal_code"
        ].required = True

    def clean_internal_code(self):
        value = self.cleaned_data.get(
            "internal_code"
        )

        if not value:
            return None

        return value.strip().upper()

    def clean_registration_number(self):
        return self.cleaned_data[
            "registration_number"
        ].strip().upper()

    def clean_brand(self):
        return self.cleaned_data[
            "brand"
        ].strip()

    def clean_model(self):
        return self.cleaned_data.get(
            "model",
            "",
        ).strip()

    def clean_notes(self):
        return self.cleaned_data.get(
            "notes",
            "",
        ).strip()


class WorkerChoiceField(
    forms.ModelChoiceField
):
    def label_from_instance(self, worker):
        code = (
            worker.employee_code
            or "-"
        )

        return (
            f"{worker.full_name} "
            f"\u2014 {code}"
        )


class TruckChoiceField(
    forms.ModelChoiceField
):
    def label_from_instance(self, truck):
        code = (
            truck.internal_code
            or "-"
        )

        return (
            f"{code} "
            f"\u2014 "
            f"{truck.registration_number}"
        )


class WorkerTruckAssignmentForm(
    forms.ModelForm
):
    worker = WorkerChoiceField(
        queryset=Worker.objects.none(),
        label="\u0627\u0644\u0628\u0627\u0626\u0639",
        widget=forms.Select(
            attrs={
                "class": (
                    "accountant-form-input"
                ),
            }
        ),
    )

    truck = TruckChoiceField(
        queryset=Truck.objects.none(),
        label="\u0627\u0644\u0634\u0627\u062d\u0646\u0629",
        widget=forms.Select(
            attrs={
                "class": (
                    "accountant-form-input"
                ),
            }
        ),
    )

    class Meta:
        model = WorkerTruckAssignment

        fields = (
            "worker",
            "truck",
            "start_date",
            "end_date",
            "notes",
        )

        labels = {
            "start_date": (
                "\u062a\u0627\u0631\u064a\u062e "
                "\u0627\u0644\u0628\u062f\u0627\u064a\u0629"
            ),
            "end_date": (
                "\u062a\u0627\u0631\u064a\u062e "
                "\u0627\u0644\u0646\u0647\u0627\u064a\u0629"
            ),
            "notes": (
                "\u0645\u0644\u0627\u062d\u0638\u0627\u062a"
            ),
        }

        help_texts = {
            "end_date": (
                "\u0627\u062a\u0631\u0643\u0647 "
                "\u0641\u0627\u0631\u063a\u064b\u0627 "
                "\u0625\u0630\u0627 \u0643\u0627\u0646 "
                "\u0627\u0644\u0628\u0627\u0626\u0639 "
                "\u0645\u0627 \u0632\u0627\u0644 "
                "\u0645\u0631\u062a\u0628\u0637\u064b\u0627 "
                "\u0628\u0627\u0644\u0634\u0627\u062d\u0646\u0629."
            ),
        }

        widgets = {
            "start_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": (
                        "accountant-form-input"
                    ),
                    "type": "date",
                    "dir": "ltr",
                },
            ),
            "end_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": (
                        "accountant-form-input"
                    ),
                    "type": "date",
                    "dir": "ltr",
                },
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": (
                        "accountant-form-textarea"
                    ),
                    "rows": 4,
                },
            ),
        }

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        worker_filter = Q(
            is_active=True
        )

        truck_filter = Q(
            is_active=True
        )

        if (
            self.instance
            and self.instance.pk
        ):
            worker_filter |= Q(
                pk=self.instance.worker_id
            )

            truck_filter |= Q(
                pk=self.instance.truck_id
            )

        self.fields[
            "worker"
        ].queryset = (
            Worker.objects
            .filter(worker_filter)
            .order_by(
                "last_name",
                "first_name",
                "employee_code",
            )
        )

        self.fields[
            "truck"
        ].queryset = (
            Truck.objects
            .filter(truck_filter)
            .order_by(
                "internal_code",
                "registration_number",
            )
        )

    def clean_notes(self):
        return self.cleaned_data.get(
            "notes",
            "",
        ).strip()


class AssignmentEndForm(
    forms.ModelForm
):
    class Meta:
        model = WorkerTruckAssignment

        fields = (
            "end_date",
        )

        labels = {
            "end_date": (
                "\u062a\u0627\u0631\u064a\u062e "
                "\u0646\u0647\u0627\u064a\u0629 "
                "\u0627\u0644\u062a\u0639\u064a\u064a\u0646"
            ),
        }

        widgets = {
            "end_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": (
                        "accountant-form-input"
                    ),
                    "type": "date",
                    "dir": "ltr",
                },
            ),
        }

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        self.fields[
            "end_date"
        ].required = True

        if (
            self.instance
            and self.instance.start_date
        ):
            self.fields[
                "end_date"
            ].widget.attrs[
                "min"
            ] = (
                self.instance
                .start_date
                .isoformat()
            )
