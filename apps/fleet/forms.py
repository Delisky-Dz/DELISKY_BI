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
            "distribution_brand",
            "route_type",
            "route_number",
            "is_active",
            "notes",
        )

        labels = {
            "distribution_brand": "العلامة",
            "route_type": "نوع التوزيع",
            "route_number": "الرقم",
            "is_active": "رمز التوزيع نشط",
            "notes": "ملاحظات",
        }

        help_texts = {
            "distribution_brand": (
                "اختر العلامة الرسمية."
            ),
            "route_type": (
                "اختر نوع التوزيع."
            ),
            "route_number": (
                "مثال: أدخل 1 ليولد النظام 01."
            ),
            "is_active": (
                "ألغِ التحديد لتعطيله دون حذف تاريخه."
            ),
        }

        widgets = {
            "distribution_brand": forms.Select(
                attrs={
                    "class": "accountant-form-input",
                }
            ),
            "route_type": forms.Select(
                attrs={
                    "class": "accountant-form-input",
                }
            ),
            "route_number": forms.NumberInput(
                attrs={
                    "class": "accountant-form-input",
                    "min": 1,
                    "max": 999,
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
            "distribution_brand"
        ].required = True

        self.fields[
            "route_type"
        ].required = True

        self.fields[
            "route_number"
        ].required = True

        self.fields[
            "route_number"
        ].min_value = 1

        self.fields[
            "route_number"
        ].max_value = 999

        self.fields[
            "route_number"
        ].widget.attrs["min"] = 1

        self.fields[
            "route_number"
        ].widget.attrs["max"] = 999

        self.fields[
            "distribution_brand"
        ].queryset = (
            self.fields[
                "distribution_brand"
            ].queryset.order_by("code")
        )

        if self.instance and self.instance.pk:
            for field_name in (
                "distribution_brand",
                "route_type",
                "route_number",
            ):
                self.fields.pop(field_name)

    def clean(self):
        cleaned_data = super().clean()

        if self.instance and self.instance.pk:
            return cleaned_data

        distribution_brand = cleaned_data.get(
            "distribution_brand"
        )
        route_type = cleaned_data.get("route_type")
        route_number = cleaned_data.get(
            "route_number"
        )

        if not (
            distribution_brand
            and route_type
            and route_number
        ):
            return cleaned_data

        generated_code = Truck.build_internal_code(
            distribution_brand.code,
            route_type,
            route_number,
        )

        duplicates = Truck.objects.filter(
            Q(internal_code=generated_code)
            | Q(
                distribution_brand=distribution_brand,
                route_type=route_type,
                route_number=route_number,
            )
        )

        if duplicates.exists():
            self.add_error(
                "route_number",
                (
                    "رمز التوزيع "
                    f"{generated_code} "
                    "موجود مسبقًا."
                ),
            )
        else:
            self.generated_internal_code = (
                generated_code
            )

        return cleaned_data

    def save(self, commit=True):
        truck = super().save(commit=False)

        generated_code = getattr(
            self,
            "generated_internal_code",
            None,
        )

        if generated_code:
            truck.internal_code = generated_code

        # حقول قديمة ما زالت مطلوبة مؤقتًا
        # للمحافظة على التوافق مع النظام الحالي.
        if not truck.registration_number:
            truck.registration_number = (
                generated_code
            )

        if not truck.brand:
            truck.brand = (
                truck.distribution_brand.code
            )

        if commit:
            truck.save()

        return truck


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
        return (
            truck.internal_code
            or "-"
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
