from django import forms
from django.utils.translation import gettext_lazy as _

from avifly.core.forms import PeriodForm
from avifly.customers.models import Customer
from avifly.equipment.models import Equipment, EquipmentType
from avifly.jobs.models import Crop, OperationType


class AnalyticsFilterForm(PeriodForm):
    operation = forms.ModelChoiceField(
        queryset=OperationType.objects.all(), required=False, empty_label=_("All operations")
    )
    crop = forms.ModelChoiceField(
        queryset=Crop.objects.all(), required=False, empty_label=_("All crops")
    )
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.all(), required=False, empty_label=_("All customers")
    )
    equipment = forms.ModelChoiceField(
        queryset=Equipment.objects.all(), required=False, empty_label=_("All equipment")
    )
    equipment_type = forms.ModelChoiceField(
        label=_("Compare"),
        queryset=EquipmentType.objects.filter(show_on_jobs=True),
        required=False,
        empty_label=None,
    )

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("default", "this_season")
        super().__init__(*args, **kwargs)
        self.fields["customer"].widget.attrs["data-tom"] = ""

    def value(self, name):
        if not self.is_bound or not self.is_valid():
            return None
        return self.cleaned_data.get(name)

    @property
    def filter_fields(self):
        return [self["operation"], self["crop"], self["customer"], self["equipment"]]
