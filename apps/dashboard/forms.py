from django import forms

from apps.imports.models import DistributionBrand


class ManagerDashboardFilterForm(forms.Form):
    period_start = forms.DateField(
        required=False,
        label="تاريخ البداية",
        widget=forms.DateInput(
            attrs={
                "type": "date",
            }
        ),
    )
    period_end = forms.DateField(
        required=False,
        label="تاريخ النهاية",
        widget=forms.DateInput(
            attrs={
                "type": "date",
            }
        ),
    )
    brand = forms.ModelChoiceField(
        queryset=DistributionBrand.objects.none(),
        required=False,
        label="العلامة",
        empty_label="جميع العلامات",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["brand"].queryset = (
            DistributionBrand.objects.filter(
                is_active=True,
            ).order_by(
                "name",
                "code",
            )
        )

    def clean(self):
        cleaned_data = super().clean()

        period_start = cleaned_data.get("period_start")
        period_end = cleaned_data.get("period_end")

        if (
            period_start is not None
            and period_end is not None
            and period_end < period_start
        ):
            raise forms.ValidationError(
                "تاريخ النهاية لا يمكن أن يسبق تاريخ البداية."
            )

        return cleaned_data



class AskDeliskyForm(ManagerDashboardFilterForm):
    question = forms.CharField(
        required=True,
        max_length=1000,
        strip=True,
        label="Ask DELISKY",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "maxlength": 1000,
                "autocomplete": "off",
            }
        ),
    )



class MarketingHelperForm(forms.Form):
    question = forms.CharField(
        required=True,
        max_length=1000,
        strip=True,
        label="DELISKY AI Marketing Helper",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "maxlength": 1000,
                "autocomplete": "off",
            }
        ),
    )
