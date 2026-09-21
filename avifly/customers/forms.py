from django import forms
from django.utils.translation import gettext_lazy as _

from avifly.core.forms import DecimalInput
from avifly.customers.models import Customer, FarmField


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "name", "company_name", "phone", "phone_alt", "email", "town", "address",
            "tax_number", "special_rate_per_ha", "notes", "is_active",
        ]  # fmt: skip
        widgets = {
            "phone": forms.TextInput(attrs={"type": "tel", "autocomplete": "off"}),
            "phone_alt": forms.TextInput(attrs={"type": "tel", "autocomplete": "off"}),
            "special_rate_per_ha": DecimalInput(),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class FarmFieldForm(forms.ModelForm):
    coordinates = forms.CharField(
        label=_("Paste coordinates"),
        required=False,
        help_text=_("e.g. 41.99646, 21.43141 — or a Google Maps link. Or tap the map."),
    )

    field_order = ["name", "hectares", "coordinates", "latitude", "longitude", "notes", "is_active"]

    class Meta:
        model = FarmField
        fields = ["name", "hectares", "latitude", "longitude", "notes", "is_active"]
        widgets = {
            "hectares": DecimalInput(),
            "latitude": DecimalInput(step="any"),
            "longitude": DecimalInput(step="any"),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["coordinates"].widget.attrs.update(
            {
                "data-coords-paste": "",
                "data-lat-target": self["latitude"].auto_id,
                "data-lng-target": self["longitude"].auto_id,
                "autocomplete": "off",
            }
        )

    def clean(self):
        cleaned = super().clean()
        if (cleaned.get("latitude") is None) != (cleaned.get("longitude") is None):
            raise forms.ValidationError(_("Enter both latitude and longitude, or neither."))
        return cleaned


class QuickCustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "phone", "town"]


class QuickFieldForm(forms.ModelForm):
    class Meta:
        model = FarmField
        fields = ["name", "hectares", "latitude", "longitude"]
