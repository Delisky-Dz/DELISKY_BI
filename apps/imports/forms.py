from pathlib import Path

from django import forms

from .models import (
    ImportBatch,
    ImportBatchStatus,
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
