from pathlib import Path

from django import forms

from .models import (
    DistributionBrand,
    ImportBatch,
    ImportBatchStatus,
    ImportReportType,
    ImportSourceSystem,
)
from .services.filename_parser import (
    ImportFilenameError,
    parse_import_filename,
)


class ImportBatchUploadForm(forms.ModelForm):
    source_file = forms.FileField(
        label="\u0645\u0644\u0641 Excel",
        required=True,
        help_text=(
            "\u0627\u062e\u062a\u0631 \u0645\u0644\u0641 Excel "
            "\u0628\u0627\u0644\u0627\u0633\u0645 \u0627\u0644\u0645\u0639\u062a\u0645\u062f\u060c "
            "\u0645\u062b\u0644: "
            "Sales_BIFA_2026-03-07_2026-03-11.xlsx"
        ),
    )

    class Meta:
        model = ImportBatch
        fields = (
            "source_file",
            "replaces_batch",
            "notes",
        )
        widgets = {
            "notes": forms.Textarea(
                attrs={
                    "rows": 4,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["replaces_batch"].queryset = (
            ImportBatch.objects.filter(
                status=ImportBatchStatus.APPROVED,
            )
            .select_related("brand")
            .order_by(
                "-approved_at",
                "-id",
            )
        )

        self.fields["replaces_batch"].required = False
        self.fields["replaces_batch"].label = (
            "\u0627\u0633\u062a\u0628\u062f\u0627\u0644 "
            "\u062f\u0641\u0639\u0629 \u0645\u0639\u062a\u0645\u062f\u0629"
        )
        self.fields["replaces_batch"].help_text = (
            "\u0627\u062a\u0631\u0643\u0647 \u0641\u0627\u0631\u063a\u064b\u0627 "
            "\u0625\u0644\u0627 \u0625\u0630\u0627 \u0643\u0627\u0646 "
            "\u0627\u0644\u0645\u0644\u0641 \u062a\u0635\u062d\u064a\u062d\u064b\u0627 "
            "\u0644\u062f\u0641\u0639\u0629 \u0633\u0627\u0628\u0642\u0629."
        )

    def clean_source_file(self):
        source_file = self.cleaned_data["source_file"]

        suffix = Path(source_file.name).suffix.lower()

        if suffix not in {
            ".xlsx",
            ".xlsm",
        }:
            raise forms.ValidationError(
                "\u064a\u062c\u0628 \u0631\u0641\u0639 "
                "\u0645\u0644\u0641 Excel \u0628\u0635\u064a\u063a\u0629 "
                "XLSX \u0623\u0648 XLSM."
            )

        return source_file


class ImportUploadForm(forms.Form):
    brand = forms.ModelChoiceField(
        label="\u0627\u0644\u0639\u0644\u0627\u0645\u0629 \u0627\u0644\u062a\u062c\u0627\u0631\u064a\u0629",
        queryset=DistributionBrand.objects.none(),
        empty_label=(
            "\u0627\u062e\u062a\u0631 "
            "\u0627\u0644\u0639\u0644\u0627\u0645\u0629"
        ),
        widget=forms.Select(
            attrs={
                "class": "accountant-select",
            }
        ),
        error_messages={
            "required": (
                "\u064a\u062c\u0628 \u0627\u062e\u062a\u064a\u0627\u0631 "
                "\u0627\u0644\u0639\u0644\u0627\u0645\u0629."
            ),
            "invalid_choice": (
                "\u0627\u0644\u0639\u0644\u0627\u0645\u0629 "
                "\u0627\u0644\u0645\u062e\u062a\u0627\u0631\u0629 "
                "\u063a\u064a\u0631 \u0645\u062a\u0627\u062d\u0629."
            ),
        },
    )

    report_type = forms.ChoiceField(
        label="\u0646\u0648\u0639 \u0627\u0644\u062a\u0642\u0631\u064a\u0631",
        choices=ImportReportType.choices,
        widget=forms.Select(
            attrs={
                "class": "accountant-select",
            }
        ),
        error_messages={
            "required": (
                "\u064a\u062c\u0628 \u0627\u062e\u062a\u064a\u0627\u0631 "
                "\u0646\u0648\u0639 \u0627\u0644\u062a\u0642\u0631\u064a\u0631."
            ),
        },
    )

    period_start = forms.DateField(
        label="\u0645\u0646 \u062a\u0627\u0631\u064a\u062e",
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "accountant-date-input",
            }
        ),
        error_messages={
            "required": (
                "\u064a\u062c\u0628 \u062a\u062d\u062f\u064a\u062f "
                "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0628\u062f\u0627\u064a\u0629."
            ),
            "invalid": (
                "\u062a\u0627\u0631\u064a\u062e "
                "\u0627\u0644\u0628\u062f\u0627\u064a\u0629 "
                "\u063a\u064a\u0631 \u0635\u062d\u064a\u062d."
            ),
        },
    )

    period_end = forms.DateField(
        label="\u0625\u0644\u0649 \u062a\u0627\u0631\u064a\u062e",
        required=False,
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "accountant-date-input",
            }
        ),
        error_messages={
            "invalid": (
                "\u062a\u0627\u0631\u064a\u062e "
                "\u0627\u0644\u0646\u0647\u0627\u064a\u0629 "
                "\u063a\u064a\u0631 \u0635\u062d\u064a\u062d."
            ),
        },
    )

    source_file = forms.FileField(
        label="\u0645\u0644\u0641 Excel",
        help_text=(
            "\u0627\u0644\u0635\u064a\u063a\u0629 "
            "\u0627\u0644\u0645\u0642\u0628\u0648\u0644\u0629: "
            "XLSX"
        ),
        widget=forms.ClearableFileInput(
            attrs={
                "accept": (
                    ".xlsx,"
                    "application/vnd.openxmlformats-"
                    "officedocument.spreadsheetml.sheet"
                ),
                "class": "accountant-file-input",
            }
        ),
        error_messages={
            "required": (
                "\u064a\u062c\u0628 \u0627\u062e\u062a\u064a\u0627\u0631 "
                "\u0645\u0644\u0641 Excel \u0623\u0648\u0644\u064b\u0627."
            ),
            "empty": (
                "\u0627\u0644\u0645\u0644\u0641 "
                "\u0627\u0644\u0645\u062e\u062a\u0627\u0631 "
                "\u0641\u0627\u0631\u063a."
            ),
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["brand"].queryset = (
            DistributionBrand.objects
            .filter(is_active=True)
            .order_by("name", "code")
        )

    def clean_source_file(self):
        source_file = self.cleaned_data["source_file"]

        extension = Path(
            source_file.name
        ).suffix.casefold()

        if extension != ".xlsx":
            raise forms.ValidationError(
                "\u064a\u0642\u0628\u0644 "
                "\u0627\u0644\u0646\u0638\u0627\u0645 "
                "\u0645\u0644\u0641\u0627\u062a XLSX "
                "\u0641\u0642\u0637."
            )

        return source_file

    def clean(self):
        cleaned_data = super().clean()

        brand = cleaned_data.get("brand")
        report_type = cleaned_data.get(
            "report_type"
        )
        period_start = cleaned_data.get(
            "period_start"
        )
        period_end = cleaned_data.get(
            "period_end"
        )
        source_file = cleaned_data.get(
            "source_file"
        )

        if (
            report_type
            == ImportReportType.OPENING_STOCK
        ):
            if period_start:
                period_end = period_start
                cleaned_data["period_end"] = (
                    period_start
                )
        elif report_type and not period_end:
            self.add_error(
                "period_end",
                (
                    "\u064a\u062c\u0628 \u062a\u062d\u062f\u064a\u062f "
                    "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0646\u0647\u0627\u064a\u0629."
                ),
            )

        if (
            period_start
            and period_end
            and period_end < period_start
        ):
            self.add_error(
                "period_end",
                (
                    "\u062a\u0627\u0631\u064a\u062e "
                    "\u0627\u0644\u0646\u0647\u0627\u064a\u0629 "
                    "\u0644\u0627 \u064a\u0645\u0643\u0646 "
                    "\u0623\u0646 \u064a\u0643\u0648\u0646 "
                    "\u0642\u0628\u0644 \u062a\u0627\u0631\u064a\u062e "
                    "\u0627\u0644\u0628\u062f\u0627\u064a\u0629."
                ),
            )

        identity_is_complete = bool(
            brand
            and report_type
            and period_start
            and period_end
            and source_file
        )

        if not identity_is_complete:
            return cleaned_data

        try:
            parsed = parse_import_filename(
                source_file.name
            )
        except ImportFilenameError:
            self.add_error(
                "source_file",
                (
                    "\u0627\u0633\u0645 \u0627\u0644\u0645\u0644\u0641 "
                    "\u0644\u0627 \u064a\u0637\u0627\u0628\u0642 "
                    "\u0627\u0644\u0635\u064a\u063a\u0629 "
                    "\u0627\u0644\u0631\u0633\u0645\u064a\u0629 "
                    "\u0644\u0646\u0638\u0627\u0645 DELISKY BI."
                ),
            )

            return cleaned_data

        mismatches = []

        if (
            parsed.brand_code.casefold()
            != brand.code.casefold()
        ):
            mismatches.append(
                (
                    "\u0627\u0644\u0639\u0644\u0627\u0645\u0629 "
                    f"\u0627\u0644\u0645\u062e\u062a\u0627\u0631\u0629 "
                    f"{brand.code} "
                    "\u0644\u0627 \u062a\u0637\u0627\u0628\u0642 "
                    "\u0627\u0644\u0639\u0644\u0627\u0645\u0629 "
                    f"{parsed.brand_code} "
                    "\u0641\u064a \u0627\u0633\u0645 "
                    "\u0627\u0644\u0645\u0644\u0641"
                )
            )

        if parsed.report_type != report_type:
            report_labels = dict(
                ImportReportType.choices
            )

            mismatches.append(
                (
                    "\u0646\u0648\u0639 \u0627\u0644\u062a\u0642\u0631\u064a\u0631 "
                    "\u0627\u0644\u0645\u062e\u062a\u0627\u0631 "
                    f"{report_labels.get(report_type, report_type)} "
                    "\u0644\u0627 \u064a\u0637\u0627\u0628\u0642 "
                    "\u0646\u0648\u0639 \u0627\u0644\u0645\u0644\u0641"
                )
            )

        if parsed.period_start != period_start:
            mismatches.append(
                (
                    "\u062a\u0627\u0631\u064a\u062e "
                    "\u0627\u0644\u0628\u062f\u0627\u064a\u0629 "
                    "\u0627\u0644\u0645\u062e\u062a\u0627\u0631 "
                    f"{period_start.isoformat()} "
                    "\u0644\u0627 \u064a\u0637\u0627\u0628\u0642 "
                    "\u0627\u0633\u0645 \u0627\u0644\u0645\u0644\u0641"
                )
            )

        if parsed.period_end != period_end:
            mismatches.append(
                (
                    "\u062a\u0627\u0631\u064a\u062e "
                    "\u0627\u0644\u0646\u0647\u0627\u064a\u0629 "
                    "\u0627\u0644\u0645\u062e\u062a\u0627\u0631 "
                    f"{period_end.isoformat()} "
                    "\u0644\u0627 \u064a\u0637\u0627\u0628\u0642 "
                    "\u0627\u0633\u0645 \u0627\u0644\u0645\u0644\u0641"
                )
            )

        if mismatches:
            self.add_error(
                None,
                (
                    "\u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a "
                    "\u0627\u0644\u0645\u062e\u062a\u0627\u0631\u0629 "
                    "\u0644\u0627 \u062a\u0637\u0627\u0628\u0642 "
                    "\u0627\u0633\u0645 \u0627\u0644\u0645\u0644\u0641: "
                    + " \u2014 ".join(mismatches)
                ),
            )

        return cleaned_data

class RawChargementUploadForm(forms.Form):
    source_system = forms.ModelChoiceField(
        label=(
            "\u0646\u0638\u0627\u0645 "
            "\u0627\u0644\u0645\u0635\u062f\u0631"
        ),
        queryset=ImportSourceSystem.objects.none(),
        empty_label=(
            "\u0627\u062e\u062a\u0631 "
            "\u0646\u0638\u0627\u0645 "
            "\u0627\u0644\u0645\u0635\u062f\u0631"
        ),
        widget=forms.Select(
            attrs={
                "class": "accountant-select",
            }
        ),
    )

    period_start = forms.DateField(
        label=(
            "\u0645\u0646 "
            "\u062a\u0627\u0631\u064a\u062e"
        ),
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "accountant-date-input",
            }
        ),
    )

    period_end = forms.DateField(
        label=(
            "\u0625\u0644\u0649 "
            "\u062a\u0627\u0631\u064a\u062e"
        ),
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "accountant-date-input",
            }
        ),
    )

    source_file = forms.FileField(
        label=(
            "\u0645\u0644\u0641 "
            "Chargement Excel"
        ),
        help_text=(
            "\u0627\u0644\u0635\u064a\u063a\u0629 "
            "\u0627\u0644\u0645\u0642\u0628\u0648\u0644\u0629: "
            "XLSX"
        ),
        widget=forms.ClearableFileInput(
            attrs={
                "accept": (
                    ".xlsx,"
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                "class": "accountant-file-input",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["source_system"].queryset = (
            ImportSourceSystem.objects
            .filter(is_active=True)
            .order_by("name", "code")
        )

    def clean_source_file(self):
        source_file = self.cleaned_data["source_file"]

        extension = Path(
            source_file.name
        ).suffix.casefold()

        if extension != ".xlsx":
            raise forms.ValidationError(
                (
                    "\u064a\u0642\u0628\u0644 "
                    "\u0627\u0644\u0646\u0638\u0627\u0645 "
                    "\u0645\u0644\u0641\u0627\u062a XLSX "
                    "\u0641\u0642\u0637."
                )
            )

        return source_file

    def clean(self):
        cleaned_data = super().clean()

        period_start = cleaned_data.get(
            "period_start"
        )
        period_end = cleaned_data.get(
            "period_end"
        )

        if (
            period_start
            and period_end
            and period_end < period_start
        ):
            raise forms.ValidationError(
                (
                    "\u062a\u0627\u0631\u064a\u062e "
                    "\u0627\u0644\u0646\u0647\u0627\u064a\u0629 "
                    "\u0644\u0627 \u064a\u0645\u0643\u0646 "
                    "\u0623\u0646 \u064a\u0643\u0648\u0646 "
                    "\u0642\u0628\u0644 "
                    "\u062a\u0627\u0631\u064a\u062e "
                    "\u0627\u0644\u0628\u062f\u0627\u064a\u0629."
                )
            )

        return cleaned_data

RawChargementUploadFormSet = forms.formset_factory(
    RawChargementUploadForm,
    extra=1,
    min_num=1,
    validate_min=True,
    max_num=20,
    validate_max=True,
    absolute_max=20,
    can_delete=True,
)



class RawSalesUploadForm(RawChargementUploadForm):
    source_file = forms.FileField(
        label=(
            "\u0645\u0644\u0641 "
            "Sales Excel"
        ),
        help_text=(
            "\u0627\u0644\u0635\u064a\u063a\u0629 "
            "\u0627\u0644\u0645\u0642\u0628\u0648\u0644\u0629: "
            "XLSX"
        ),
        widget=forms.ClearableFileInput(
            attrs={
                "accept": (
                    ".xlsx,"
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                "class": "accountant-file-input",
            }
        ),
    )


RawSalesUploadFormSet = forms.formset_factory(
    RawSalesUploadForm,
    extra=1,
    min_num=1,
    validate_min=True,
    max_num=20,
    validate_max=True,
    absolute_max=20,
    can_delete=True,
)
