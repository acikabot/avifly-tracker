from django import forms

from avifly.core.forms import DateInput
from avifly.equipment.models import Equipment, EquipmentType


class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = [
            "name", "equipment_type", "model_name", "serial_number", "purchase_date",
            "status", "notes",
        ]  # fmt: skip
        widgets = {"purchase_date": DateInput(), "notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current = self.instance.equipment_type if self.instance.pk else None
        self.fields["equipment_type"].queryset = EquipmentType.choices_for(current)
