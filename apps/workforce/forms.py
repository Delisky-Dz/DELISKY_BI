from django import forms
from django.db.models import Q

from .models import (
    Worker,
    WorkerCapability,
    WorkerCategory,
    WorkerPositionPeriod,
)


class WorkerCapabilityMultipleChoiceField(
    forms.ModelMultipleChoiceField
):
    def label_from_instance(
        self,
        capability,
    ):
        if capability.is_active:
            return capability.name

        return (
            f"{capability.name} — معطلة"
        )


def capability_queryset_for(
    instance,
    relation_name,
):
    capability_filter = Q(
        is_active=True
    )

    if getattr(instance, "pk", None):
        current_ids = getattr(
            instance,
            relation_name,
        ).values_list(
            "pk",
            flat=True,
        )

        capability_filter |= Q(
            pk__in=current_ids
        )

    return (
        WorkerCapability.objects
        .filter(capability_filter)
        .distinct()
        .order_by(
            "sort_order",
            "name",
        )
    )


class WorkerForm(forms.ModelForm):
    capabilities = (
        WorkerCapabilityMultipleChoiceField(
            queryset=(
                WorkerCapability.objects.none()
            ),
            required=False,
            label="قدرات العامل",
            help_text=(
                "حدد القدرات الفعلية الخاصة "
                "بالعامل. وهي مستقلة عن "
                "منصبه الرسمي."
            ),
            widget=forms.CheckboxSelectMultiple(
                attrs={
                    "class": (
                        "accountant-form-checkbox"
                    ),
                }
            ),
        )
    )

    class Meta:
        model = Worker

        fields = (
            "first_name",
            "last_name",
            "phone",
            "capabilities",
            "is_active",
            "notes",
        )

        labels = {
            "first_name": "الاسم",
            "last_name": "اللقب",
            "phone": "رقم الهاتف",
            "is_active": "العامل نشط",
            "notes": "ملاحظات",
        }

        help_texts = {
            "is_active": (
                "ألغِ التحديد لتعطيل "
                "العامل دون حذف سجله."
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
            "capabilities"
        ].queryset = capability_queryset_for(
            self.instance,
            "capabilities",
        )

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
    default_capabilities = (
        WorkerCapabilityMultipleChoiceField(
            queryset=(
                WorkerCapability.objects.none()
            ),
            required=False,
            label="القدرات الافتراضية",
            help_text=(
                "قدرات مقترحة لهذا الصنف. "
                "لا تغيّر قدرات أي عامل "
                "تلقائيًا."
            ),
            widget=forms.CheckboxSelectMultiple(
                attrs={
                    "class": (
                        "accountant-form-checkbox"
                    ),
                }
            ),
        )
    )

    class Meta:
        model = WorkerCategory

        fields = (
            "name",
            "description",
            "default_capabilities",
            "sort_order",
            "is_active",
        )

        labels = {
            "name": "اسم الصنف",
            "description": "الوصف",
            "sort_order": "الترتيب",
            "is_active": "الصنف نشط",
        }

        help_texts = {
            "name": (
                "يمكن تعديل الاسم لاحقًا "
                "دون تغيير الرمز التقني."
            ),
            "sort_order": (
                "الرقم الأصغر يظهر أولًا."
            ),
            "is_active": (
                "عطّل الصنف بدل حذفه "
                "للحفاظ على السجلات."
            ),
        }

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": (
                        "accountant-form-input"
                    ),
                    "autocomplete": "off",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": (
                        "accountant-form-textarea"
                    ),
                    "rows": 4,
                }
            ),
            "sort_order": forms.NumberInput(
                attrs={
                    "class": (
                        "accountant-form-input"
                    ),
                    "min": 0,
                    "step": 1,
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
            "default_capabilities"
        ].queryset = capability_queryset_for(
            self.instance,
            "default_capabilities",
        )

    def clean_name(self):
        return self.cleaned_data[
            "name"
        ].strip()

    def clean_description(self):
        return self.cleaned_data.get(
            "description",
            "",
        ).strip()


class WorkerCapabilityForm(forms.ModelForm):
    class Meta:
        model = WorkerCapability

        fields = (
            "name",
            "description",
            "sort_order",
            "is_active",
        )

        labels = {
            "name": "اسم القدرة",
            "description": "الوصف",
            "sort_order": "الترتيب",
            "is_active": "القدرة نشطة",
        }

        help_texts = {
            "name": (
                "اكتب اسمًا واضحًا ومحددًا "
                "للقدرة العملية."
            ),
            "sort_order": (
                "الرقم الأصغر يظهر أولًا."
            ),
            "is_active": (
                "عطّل القدرة بدل حذفها "
                "للحفاظ على ارتباطاتها."
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
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": (
                        "accountant-form-checkbox"
                    ),
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


class WorkerPositionPeriodForm(forms.ModelForm):
    class Meta:
        model = WorkerPositionPeriod

        fields = (
            "worker",
            "category",
            "start_date",
            "end_date",
            "notes",
        )

        labels = {
            "worker": "\u0627\u0644\u0639\u0627\u0645\u0644",
            "category": (
                "\u0635\u0646\u0641 "
                "\u0627\u0644\u0645\u0646\u0635\u0628"
            ),
            "start_date": (
                "\u062a\u0627\u0631\u064a\u062e "
                "\u0628\u062f\u0627\u064a\u0629 "
                "\u0627\u0644\u0645\u0646\u0635\u0628"
            ),
            "end_date": (
                "\u062a\u0627\u0631\u064a\u062e "
                "\u0646\u0647\u0627\u064a\u0629 "
                "\u0627\u0644\u0645\u0646\u0635\u0628"
            ),
            "notes": "\u0645\u0644\u0627\u062d\u0638\u0627\u062a",
        }

        help_texts = {
            "category": (
                "\u064a\u0645\u062b\u0644 "
                "\u0627\u0644\u0645\u0646\u0635\u0628 "
                "\u0627\u0644\u0631\u0633\u0645\u064a "
                "\u0644\u0644\u0639\u0627\u0645\u0644 "
                "\u062e\u0644\u0627\u0644 "
                "\u0647\u0630\u0647 "
                "\u0627\u0644\u0641\u062a\u0631\u0629."
            ),
            "end_date": (
                "\u0627\u062a\u0631\u0643\u0647 "
                "\u0641\u0627\u0631\u063a\u064b\u0627 "
                "\u0625\u0630\u0627 "
                "\u0643\u0627\u0646 "
                "\u0627\u0644\u0645\u0646\u0635\u0628 "
                "\u0645\u0633\u062a\u0645\u0631\u064b\u0627."
            ),
        }

        widgets = {
            "worker": forms.HiddenInput(),
            "category": forms.Select(
                attrs={
                    "class": "accountant-form-input",
                }
            ),
            "start_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "accountant-form-input",
                    "type": "date",
                    "dir": "ltr",
                },
            ),
            "end_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "accountant-form-input",
                    "type": "date",
                    "dir": "ltr",
                },
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "accountant-form-textarea",
                    "rows": 4,
                }
            ),
        }

    def __init__(
        self,
        *args,
        worker=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        resolved_worker = worker

        if (
            resolved_worker is None
            and self.instance.worker_id
        ):
            resolved_worker = self.instance.worker

        if resolved_worker is not None:
            self.instance.worker = resolved_worker

            self.fields["worker"].queryset = (
                Worker.objects.filter(
                    pk=resolved_worker.pk
                )
            )

            self.fields["worker"].initial = (
                resolved_worker
            )

            self.fields["worker"].disabled = True
        else:
            self.fields["worker"].queryset = (
                Worker.objects.none()
            )

        category_filter = Q(is_active=True)

        if (
            self.instance.pk
            and self.instance.category_id
        ):
            category_filter |= Q(
                pk=self.instance.category_id
            )

        self.fields["category"].queryset = (
            WorkerCategory.objects
            .filter(category_filter)
            .order_by(
                "sort_order",
                "name",
            )
        )

        self.fields["category"].empty_label = (
            "\u0627\u062e\u062a\u0631 "
            "\u0635\u0646\u0641 "
            "\u0627\u0644\u0645\u0646\u0635\u0628"
        )

    def clean_notes(self):
        return self.cleaned_data.get(
            "notes",
            "",
        ).strip()
