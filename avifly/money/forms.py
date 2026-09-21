from __future__ import annotations

from datetime import timedelta

from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from avifly.core.forms import DateInput, DecimalInput
from avifly.core.validators import validate_upload
from avifly.equipment.models import Equipment
from avifly.jobs.models import Job
from avifly.money.models import Cost, CostCategory, Payment, PaymentMethod


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["method", "follows_job_total", "amount", "date", "note"]
        widgets = {
            "amount": DecimalInput(attrs={"data-payment-amount": ""}),
            "date": DateInput(),
            "follows_job_total": forms.CheckboxInput(attrs={"data-follows-total": ""}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current = self.instance.method if self.instance.pk else None
        self.fields["method"].queryset = PaymentMethod.choices_for(current)
        self.fields["method"].empty_label = None
        self.fields["amount"].required = False
        self.fields["date"].required = False
        self.fields["date"].help_text = _("Defaults to the job's last day.")

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("follows_job_total") and cleaned.get("amount") is None:
            self.add_error("amount", _("Enter the amount, or tick “same as job total”."))
        return cleaned


class CostForm(forms.ModelForm):
    class Meta:
        model = Cost
        fields = [
            "date",
            "amount",
            "category",
            "description",
            "equipment",
            "job",
            "receipt",
            "notes",
        ]
        widgets = {
            "date": DateInput(),
            "amount": DecimalInput(),
            "notes": forms.Textarea(attrs={"rows": 2}),
            "receipt": forms.ClearableFileInput(attrs={"accept": "image/*,application/pdf"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        cost = self.instance
        self.fields["category"].queryset = CostCategory.choices_for(
            cost.category if cost.pk else None
        )
        equipment = Equipment.objects.filter(status__in=Equipment.USABLE)
        if cost.equipment_id:
            equipment = equipment | Equipment.all_objects.filter(pk=cost.equipment_id)
        self.fields["equipment"].queryset = equipment.select_related("equipment_type").distinct()
        self.fields["equipment"].help_text = _("If this cost was for one machine.")
        self.fields["equipment"].widget.attrs["data-tom"] = ""

        since = timezone.localdate() - timedelta(days=400)
        recent = Job.objects.filter(start_date__gte=since)
        if user is not None:
            recent = recent.visible_to(user)
        condition = Q(pk__in=recent.values("pk"))
        if cost.job_id:
            condition |= Q(pk=cost.job_id)
        self.fields["job"].queryset = (
            Job.all_objects.filter(condition).select_related("customer").order_by("-start_date")
        )
        self.fields["job"].help_text = _(
            "If this cost belongs to one job (e.g. fuel for that trip)."
        )
        self.fields["job"].widget.attrs["data-tom"] = ""

    def clean_receipt(self):
        receipt = self.cleaned_data.get("receipt")
        if isinstance(receipt, UploadedFile):
            validate_upload(receipt)
        return receipt


class CostFilterForm(forms.Form):
    category = forms.ModelChoiceField(
        queryset=CostCategory.objects.all(), required=False, empty_label=_("All categories")
    )
    equipment = forms.ModelChoiceField(
        queryset=Equipment.objects.all(), required=False, empty_label=_("All equipment")
    )
