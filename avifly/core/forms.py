"""Form rendering and shared form helpers.

All forms render through :class:`AviflyFormRenderer`, which uses the Bootstrap
templates in ``core/templates/forms/``; forms don't need any styling code.
"""

from __future__ import annotations

from django import forms
from django.forms.renderers import TemplatesSetting
from django.forms.utils import ErrorDict

from avifly.core.models import BusinessSettings
from avifly.core.periods import PRESETS, resolve_period


class AviflyFormRenderer(TemplatesSetting):
    form_template_name = "forms/form.html"
    field_template_name = "forms/field.html"


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%d")


class TimeInput(forms.TimeInput):
    input_type = "time"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%H:%M")


class DecimalInput(forms.NumberInput):
    """Number input that brings up the numeric keypad on phones."""

    def __init__(self, attrs=None, step="0.01"):
        base = {"step": step, "inputmode": "decimal"}
        super().__init__(attrs={**base, **(attrs or {})})


def suppress_validation(*forms_or_formsets) -> None:
    """Render bound forms without running validation (and without error messages).

    Used when a form is posted only to change its layout — e.g. "Add day" — so the
    half-filled form comes back as typed, without "This field is required" noise.
    """
    for item in forms_or_formsets:
        if isinstance(item, forms.BaseForm):
            item._errors = ErrorDict()
        elif isinstance(item, forms.BaseFormSet):
            item._errors = []
            item._non_form_errors = item.error_class()
            for form in item.forms:
                form._errors = ErrorDict()


class BusinessSettingsForm(forms.ModelForm):
    class Meta:
        model = BusinessSettings
        fields = ["name", "currency", "address", "phone", "email", "tax_number", "bank_account"]


class PeriodForm(forms.Form):
    """Pick a period ("this month", "last season", …) or custom dates."""

    period = forms.ChoiceField(choices=[], required=False)
    start = forms.DateField(required=False, widget=DateInput())
    end = forms.DateField(required=False, widget=DateInput())

    def __init__(self, data=None, *, default: str = "this_month", **kwargs):
        super().__init__(data, **kwargs)
        self.default = default
        self.fields["period"].choices = list(PRESETS.items())
        self.fields["period"].initial = default

    def get_period(self):
        if not self.is_bound or not self.is_valid():
            return resolve_period(self.default)
        data = self.cleaned_data
        preset = data.get("period") or self.default
        return resolve_period(preset, data.get("start"), data.get("end"))
