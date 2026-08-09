import re
from datetime import date
from pathlib import Path

from django import forms

from .models import (
    JobApplication,
    MaritalStatus,
    RequestedPosition,
)


MAX_CV_SIZE_BYTES = 5 * 1024 * 1024


AR_POSITION_LABELS = {
    RequestedPosition.SELLER: "\u0628\u0627\u0626\u0639",
    RequestedPosition.DRIVER: "\u0633\u0627\u0626\u0642",
    RequestedPosition.DRIVER_SELLER: (
        "\u0633\u0627\u0626\u0642 \u0648\u0628\u0627\u0626\u0639"
    ),
    RequestedPosition.WAREHOUSE_KEEPER: (
        "\u0623\u0645\u064a\u0646 \u0645\u062e\u0632\u0646"
    ),
    RequestedPosition.ACCOUNTING_MANAGER: (
        "\u0645\u062f\u064a\u0631 \u062d\u0633\u0627\u0628\u0627\u062a"
    ),
    RequestedPosition.SALES_MANAGER: (
        "\u0645\u0633\u064a\u0631 \u0645\u0628\u064a\u0639\u0627\u062a"
    ),
    RequestedPosition.SALES_SUPERVISOR: (
        "\u0645\u0634\u0631\u0641 \u0645\u0628\u064a\u0639\u0627\u062a"
    ),
}


EN_POSITION_LABELS = {
    RequestedPosition.SELLER: "Seller",
    RequestedPosition.DRIVER: "Driver",
    RequestedPosition.DRIVER_SELLER: "Driver & Seller",
    RequestedPosition.WAREHOUSE_KEEPER: "Warehouse Keeper",
    RequestedPosition.ACCOUNTING_MANAGER: "Accounting Manager",
    RequestedPosition.SALES_MANAGER: "Sales Manager",
    RequestedPosition.SALES_SUPERVISOR: "Sales Supervisor",
}


AR_MARITAL_LABELS = {
    MaritalStatus.SINGLE: "\u0623\u0639\u0632\u0628",
    MaritalStatus.MARRIED: "\u0645\u062a\u0632\u0648\u062c",
    MaritalStatus.DIVORCED: "\u0645\u0637\u0644\u0642",
    MaritalStatus.WIDOWED: "\u0623\u0631\u0645\u0644",
}


EN_MARITAL_LABELS = {
    MaritalStatus.SINGLE: "Single",
    MaritalStatus.MARRIED: "Married",
    MaritalStatus.DIVORCED: "Divorced",
    MaritalStatus.WIDOWED: "Widowed",
}


class JobApplicationForm(forms.ModelForm):
    class Meta:
        model = JobApplication

        fields = (
            "first_name",
            "last_name",
            "birth_date",
            "marital_status",
            "children_count",
            "phone",
            "email",
            "wilaya",
            "residence",
            "requested_position",
            "experience_years",
            "previous_companies",
            "has_driving_license",
            "driving_license_category",
            "driving_experience_years",
            "cv",
        )

        widgets = {
            "first_name": forms.TextInput(
                attrs={
                    "class": "career-input",
                    "autocomplete": "given-name",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "career-input",
                    "autocomplete": "family-name",
                }
            ),
            "birth_date": forms.DateInput(
                attrs={
                    "class": "career-input",
                    "type": "date",
                }
            ),
            "marital_status": forms.Select(
                attrs={
                    "class": "career-input career-select",
                }
            ),
            "children_count": forms.NumberInput(
                attrs={
                    "class": "career-input",
                    "min": "0",
                    "inputmode": "numeric",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "career-input",
                    "dir": "ltr",
                    "autocomplete": "tel",
                    "inputmode": "tel",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "career-input",
                    "dir": "ltr",
                    "autocomplete": "email",
                }
            ),
            "wilaya": forms.TextInput(
                attrs={
                    "class": "career-input",
                    "autocomplete": "address-level1",
                }
            ),
            "residence": forms.TextInput(
                attrs={
                    "class": "career-input",
                    "autocomplete": "address-level2",
                }
            ),
            "requested_position": forms.Select(
                attrs={
                    "class": "career-input career-select",
                    "data-position-select": "1",
                }
            ),
            "experience_years": forms.NumberInput(
                attrs={
                    "class": "career-input",
                    "min": "0",
                    "inputmode": "numeric",
                }
            ),
            "previous_companies": forms.Textarea(
                attrs={
                    "class": "career-input career-textarea",
                    "rows": "5",
                }
            ),
            "has_driving_license": forms.CheckboxInput(
                attrs={
                    "class": "career-checkbox",
                    "data-driving-license": "1",
                }
            ),
            "driving_license_category": forms.TextInput(
                attrs={
                    "class": "career-input",
                    "dir": "ltr",
                }
            ),
            "driving_experience_years": forms.NumberInput(
                attrs={
                    "class": "career-input",
                    "min": "0",
                    "inputmode": "numeric",
                }
            ),
            "cv": forms.FileInput(
                attrs={
                    "class": "career-file",
                    "accept": ".pdf,application/pdf",
                }
            ),
        }

    def __init__(
        self,
        *args,
        language="ar",
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        self.language = (
            "en"
            if language == "en"
            else "ar"
        )

        is_en = self.language == "en"

        position_labels = (
            EN_POSITION_LABELS
            if is_en
            else AR_POSITION_LABELS
        )

        marital_labels = (
            EN_MARITAL_LABELS
            if is_en
            else AR_MARITAL_LABELS
        )

        self.fields[
            "requested_position"
        ].choices = [
            ("", "Select a position" if is_en else "\u0627\u062e\u062a\u0631 \u0627\u0644\u0648\u0638\u064a\u0641\u0629"),
            *[
                (
                    value,
                    position_labels[value],
                )
                for value, _label
                in RequestedPosition.choices
            ],
        ]

        self.fields[
            "marital_status"
        ].choices = [
            ("", "Select" if is_en else "\u0627\u062e\u062a\u0631"),
            *[
                (
                    value,
                    marital_labels[value],
                )
                for value, _label
                in MaritalStatus.choices
            ],
        ]

        self.fields["email"].required = False
        self.fields["cv"].required = False

    def _message(
        self,
        ar,
        en,
    ):
        return (
            en
            if self.language == "en"
            else ar
        )

    def clean_birth_date(self):
        value = self.cleaned_data[
            "birth_date"
        ]

        if value > date.today():
            raise forms.ValidationError(
                self._message(
                    "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0645\u064a\u0644\u0627\u062f \u063a\u064a\u0631 \u0635\u062d\u064a\u062d.",
                    "Birth date cannot be in the future.",
                )
            )

        return value

    def clean_phone(self):
        raw = str(
            self.cleaned_data.get(
                "phone",
                "",
            )
        ).strip()

        normalized = re.sub(
            r"[\s\-\(\)\.]",
            "",
            raw,
        )

        if re.fullmatch(
            r"0\d{9}",
            normalized,
        ):
            return (
                "+213"
                + normalized[1:]
            )

        if re.fullmatch(
            r"\+213\d{9}",
            normalized,
        ):
            return normalized

        raise forms.ValidationError(
            self._message(
                "\u0623\u062f\u062e\u0644 \u0631\u0642\u0645 \u0647\u0627\u062a\u0641 \u062c\u0632\u0627\u0626\u0631\u064a \u0635\u062d\u064a\u062d.",
                "Enter a valid Algerian phone number.",
            )
        )

    def clean_cv(self):
        cv = self.cleaned_data.get(
            "cv"
        )

        if not cv:
            return cv

        if cv.size > MAX_CV_SIZE_BYTES:
            raise forms.ValidationError(
                self._message(
                    "\u062d\u062c\u0645 \u0627\u0644\u0633\u064a\u0631\u0629 \u0627\u0644\u0630\u0627\u062a\u064a\u0629 \u064a\u062c\u0628 \u0623\u0644\u0627 \u064a\u062a\u062c\u0627\u0648\u0632 5 MB.",
                    "CV file must not exceed 5 MB.",
                )
            )

        if (
            Path(cv.name).suffix.lower()
            != ".pdf"
        ):
            raise forms.ValidationError(
                self._message(
                    "\u0646\u0642\u0628\u0644 \u0627\u0644\u0633\u064a\u0631\u0629 \u0627\u0644\u0630\u0627\u062a\u064a\u0629 \u0628\u0635\u064a\u063a\u0629 PDF \u0641\u0642\u0637.",
                    "Only PDF CV files are accepted.",
                )
            )

        content_type = getattr(
            cv,
            "content_type",
            "",
        )

        if (
            content_type
            and content_type
            != "application/pdf"
        ):
            raise forms.ValidationError(
                self._message(
                    "\u0645\u0644\u0641 \u0627\u0644\u0633\u064a\u0631\u0629 \u0627\u0644\u0630\u0627\u062a\u064a\u0629 \u0644\u064a\u0633 PDF \u0635\u062d\u064a\u062d.",
                    "The uploaded CV is not a valid PDF.",
                )
            )

        position = cv.tell()

        header = cv.read(5)

        cv.seek(position)

        if header != b"%PDF-":
            raise forms.ValidationError(
                self._message(
                    "\u0645\u0644\u0641 \u0627\u0644\u0633\u064a\u0631\u0629 \u0627\u0644\u0630\u0627\u062a\u064a\u0629 \u0644\u064a\u0633 PDF \u0635\u062d\u064a\u062d.",
                    "The uploaded CV is not a valid PDF.",
                )
            )

        return cv

    def clean(self):
        cleaned = super().clean()

        position = cleaned.get(
            "requested_position"
        )

        driver_positions = {
            RequestedPosition.DRIVER,
            RequestedPosition.DRIVER_SELLER,
        }

        if position in driver_positions:
            if not cleaned.get(
                "has_driving_license"
            ):
                self.add_error(
                    "has_driving_license",
                    self._message(
                        "\u0631\u062e\u0635\u0629 \u0627\u0644\u0633\u064a\u0627\u0642\u0629 \u0645\u0637\u0644\u0648\u0628\u0629 \u0644\u0647\u0630\u0647 \u0627\u0644\u0648\u0638\u064a\u0641\u0629.",
                        "A driving licence is required for this position.",
                    ),
                )

            if not str(
                cleaned.get(
                    "driving_license_category",
                    "",
                )
            ).strip():
                self.add_error(
                    "driving_license_category",
                    self._message(
                        "\u0623\u062f\u062e\u0644 \u0635\u0646\u0641 \u0631\u062e\u0635\u0629 \u0627\u0644\u0633\u064a\u0627\u0642\u0629.",
                        "Enter the driving licence category.",
                    ),
                )

            if (
                cleaned.get(
                    "driving_experience_years"
                )
                is None
            ):
                self.add_error(
                    "driving_experience_years",
                    self._message(
                        "\u0623\u062f\u062e\u0644 \u0633\u0646\u0648\u0627\u062a \u062e\u0628\u0631\u0629 \u0627\u0644\u0633\u064a\u0627\u0642\u0629.",
                        "Enter years of driving experience.",
                    ),
                )

        else:
            cleaned[
                "has_driving_license"
            ] = False
            cleaned[
                "driving_license_category"
            ] = ""
            cleaned[
                "driving_experience_years"
            ] = None

        return cleaned
