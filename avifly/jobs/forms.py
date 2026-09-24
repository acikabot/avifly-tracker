"""The job form: job details + one form per day + extra charges + module sections.

:class:`JobFormBundle` ties the parts together so the view stays small. Other
modules add their own sections to the job form (e.g. the money module's "Payment")
by registering a :class:`JobFormSection` under the ``jobs.job_form`` extension point.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext_lazy as _

from avifly.core.forms import DateInput, DecimalInput, TimeInput, suppress_validation
from avifly.core.registry import registry
from avifly.customers.models import Customer, FarmField
from avifly.equipment.models import Equipment, EquipmentType
from avifly.jobs import services
from avifly.jobs.models import CrewRole, Crop, ExtraCharge, Job, JobDay, OperationType

JOB_FORM_SECTIONS = "jobs.job_form"


class JobFormSection:
    """Base class for a section another module adds to the job form.

    Subclasses set ``key``, ``title`` and ``template_name`` (rendered with ``form``
    and ``section`` in the context) and implement :meth:`get_form` and :meth:`save`.
    """

    key = ""
    title = ""
    template_name = ""
    order = 100

    def is_available(self, request, job: Job | None) -> bool:
        return True

    def get_form(self, request, job: Job | None, data=None, files=None) -> forms.Form:
        raise NotImplementedError

    def save(self, request, form: forms.Form, job: Job) -> None:
        raise NotImplementedError


def _tom(select_widget: forms.Widget, placeholder: str = "") -> forms.Widget:
    select_widget.attrs["data-tom"] = ""
    if placeholder:
        select_widget.attrs["data-placeholder"] = placeholder
    return select_widget


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = [
            "customer", "operation_type", "crop", "material_note", "rate_per_ha",
            "is_multi_day", "is_cancelled", "notes",
        ]  # fmt: skip
        widgets = {
            "rate_per_ha": DecimalInput(),
            "is_multi_day": forms.CheckboxInput(attrs={"role": "switch"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        job = self.instance
        editing = job.pk is not None
        customers = Customer.objects.filter(is_active=True)
        if editing:
            customers = Customer.objects.filter(pk=job.customer_id) | customers
        self.fields["customer"].queryset = customers.order_by("name")
        self.fields["operation_type"].queryset = OperationType.choices_for(
            job.operation_type if editing else None
        )
        self.fields["crop"].queryset = Crop.choices_for(job.crop if editing and job.crop else None)
        self.fields["rate_per_ha"].required = False
        self.fields["rate_per_ha"].help_text = _(
            "Filled in from the customer's special rate or the operation's normal rate."
        )
        _tom(self.fields["customer"].widget, _("Search customers…"))
        _tom(self.fields["crop"].widget, _("Choose a crop (optional)"))
        self.fields["operation_type"].empty_label = None
        if not editing and not self.initial.get("operation_type"):
            first = self.fields["operation_type"].queryset.first()
            self.initial["operation_type"] = first.pk if first else None
        if not editing:
            del self.fields["is_cancelled"]
        rates = {
            str(op.pk): str(op.default_rate_per_ha)
            for op in self.fields["operation_type"].queryset
            if op.default_rate_per_ha is not None
        }
        self.operation_rates = rates

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("rate_per_ha") is None and not self.has_error("rate_per_ha"):
            rate = services.resolve_rate(cleaned.get("customer"), cleaned.get("operation_type"))
            if rate is None:
                self.add_error(
                    "rate_per_ha",
                    _("There's no normal rate for this operation yet — enter the rate."),
                )
            else:
                cleaned["rate_per_ha"] = rate
        return cleaned


class JobDayForm(forms.ModelForm):
    class Meta:
        model = JobDay
        fields = ["date", "farm_fields", "hectares", "start_time", "end_time", "notes"]
        widgets = {
            "date": DateInput(),
            "start_time": TimeInput(),
            "end_time": TimeInput(),
            "hectares": DecimalInput(),
            "notes": forms.TextInput(),
        }
        labels = {"farm_fields": _("Field(s)")}

    def __init__(self, *args, customer: Customer | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        day = self.instance
        selected_fields = list(day.farm_fields.all()) if day.pk else []

        fields_qs = FarmField.objects.filter(is_active=True).select_related("customer")
        if customer is not None:
            fields_qs = fields_qs.filter(customer=customer)
        if selected_fields:
            # Keep already-chosen fields visible even if they were deactivated since.
            fields_qs = fields_qs | FarmField.all_objects.filter(
                pk__in=[f.pk for f in selected_fields]
            )
        self.fields["farm_fields"].queryset = fields_qs.distinct()
        self.fields["farm_fields"].label_from_instance = (
            (lambda f: f.name) if customer is not None else str
        )
        _tom(self.fields["farm_fields"].widget, _("Pick the field(s)…"))

        self.crew_field_names: list[str] = []
        self._add_crew_fields()

        self.equipment_field_names: list[str] = []
        self._add_equipment_fields()

    def _add_crew_fields(self) -> None:
        """One dropdown per crew role (Pilot, Ground crew…), as the owners defined them."""
        User = get_user_model()
        day = self.instance
        links = list(day.crew_links.all()) if day.pk else []
        people = User.objects.usable()
        if links:
            # Keep people who are already on the day, even if their account was closed.
            people = people | User.objects.filter(pk__in=[link.user_id for link in links])
        people = people.distinct()
        for role in CrewRole.objects.filter(is_active=True):
            mine = [link.user_id for link in links if link.role_id == role.pk]
            name = f"crew_{role.pk}"
            if role.allow_multiple:
                field = forms.ModelMultipleChoiceField(
                    queryset=people, required=False, label=role.name, initial=mine
                )
                _tom(field.widget, _("Who?"))
            else:
                field = forms.ModelChoiceField(
                    queryset=people,
                    required=False,
                    label=role.name,
                    empty_label="—",
                    initial=mine[0] if mine else None,
                )
            field.label_from_instance = lambda u: u.display_name
            self.fields[name] = field
            self.crew_field_names.append(name)

    @property
    def crew_fields(self):
        return [self[name] for name in self.crew_field_names]

    def selected_crew(self) -> list[tuple]:
        """The chosen people with the role they were chosen for."""
        chosen: list[tuple] = []
        roles = {role.pk: role for role in CrewRole.objects.all()}
        for name in self.crew_field_names:
            value = self.cleaned_data.get(name)
            if not value:
                continue
            role = roles[int(name.removeprefix("crew_"))]
            people = [value] if hasattr(value, "pk") else list(value)  # single or several
            chosen.extend((person, role) for person in people)
        return chosen

    def _add_equipment_fields(self) -> None:
        day = self.instance
        current = list(day.equipment.all()) if day.pk else []
        for kind in EquipmentType.objects.filter(is_active=True, show_on_jobs=True):
            items = Equipment.objects.filter(equipment_type=kind, status__in=Equipment.USABLE)
            mine = [e.pk for e in current if e.equipment_type_id == kind.pk]
            if mine:
                items = items | Equipment.objects.filter(pk__in=mine)
            name = f"equipment_{kind.pk}"
            if kind.allow_multiple:
                field = forms.ModelMultipleChoiceField(
                    queryset=items.distinct(), required=False, label=kind.name
                )
                _tom(field.widget)
                if day.pk:
                    field.initial = mine
            else:
                field = forms.ModelChoiceField(
                    queryset=items.distinct(), required=False, label=kind.name, empty_label="—"
                )
                if day.pk:
                    field.initial = mine[0] if mine else None
            self.fields[name] = field
            self.equipment_field_names.append(name)

    @property
    def equipment_fields(self):
        return [self[name] for name in self.equipment_field_names]

    def selected_equipment(self) -> list[Equipment]:
        chosen: list[Equipment] = []
        for name in self.equipment_field_names:
            value = self.cleaned_data.get(name)
            if value is None:
                continue
            if isinstance(value, Equipment):
                chosen.append(value)
            else:
                chosen.extend(value)
        return chosen


class BaseJobDayFormSet(forms.BaseInlineFormSet):
    def live_forms(self) -> list[JobDayForm]:
        return [f for f in self.forms if not (self.can_delete and self._should_delete_form(f))]

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        live = self.live_forms()
        if not live:
            raise forms.ValidationError(_("A job needs at least one day."))
        customer = self.form_kwargs.get("customer")
        if customer is not None:
            for form in live:
                for field in form.cleaned_data.get("farm_fields", []):
                    if field.customer_id != customer.pk:
                        form.add_error(
                            "farm_fields",
                            _("“%(field)s” belongs to another customer.") % {"field": field.name},
                        )


JobDayFormSet = forms.inlineformset_factory(
    Job,
    JobDay,
    form=JobDayForm,
    formset=BaseJobDayFormSet,
    extra=0,
    min_num=1,
    validate_min=False,
    can_delete=True,
)


class ExtraChargeForm(forms.ModelForm):
    class Meta:
        model = ExtraCharge
        fields = ["note", "amount"]
        widgets = {"amount": DecimalInput(attrs={"data-extra-amount": ""})}
        labels = {"note": _("Extra charge"), "amount": _("Amount")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The row is optional; clean() asks for both parts once either is filled in.
        self.fields["note"].required = False
        self.fields["amount"].required = False
        self.fields["note"].widget.attrs["placeholder"] = _("e.g. Far field, extra travel")

    def clean(self):
        cleaned = super().clean()
        note, amount = cleaned.get("note"), cleaned.get("amount")
        if amount is not None and not note:
            self.add_error("note", _("Say what the extra charge is for."))
        if note and amount is None and not self.has_error("amount"):
            self.add_error("amount", _("Enter the amount."))
        return cleaned


ExtraChargeFormSet = forms.inlineformset_factory(
    Job, ExtraCharge, form=ExtraChargeForm, extra=1, can_delete=True
)


class BoundSection:
    def __init__(self, section: JobFormSection, form: forms.Form):
        self.section = section
        self.form = form


class JobFormBundle:
    """Job form + day forms + extra charges + module sections, validated and saved together."""

    def __init__(self, request, job: Job | None = None, data=None, files=None, initial=None):
        self.request = request
        self.is_new = job is None
        self.job = job if job is not None else Job()
        initial = initial or {}

        self.form = JobForm(data, instance=self.job, prefix="job", initial=initial.get("job"))
        customer = self._customer(data)
        day_initial = (
            None if (data is not None or not self.is_new) else [self._first_day_initial(initial)]
        )
        self.days = JobDayFormSet(
            data,
            files,
            instance=self.job,
            prefix="days",
            form_kwargs={"customer": customer},
            initial=day_initial,
        )
        self.charges = ExtraChargeFormSet(data, instance=self.job, prefix="charges")
        job_or_none = None if self.is_new else self.job
        self.sections = [
            BoundSection(section, section.get_form(request, job_or_none, data, files))
            for section in registry.extensions(JOB_FORM_SECTIONS)
            if section.is_available(request, job_or_none)
        ]

    # -- construction helpers ------------------------------------------------------------
    def _customer(self, data) -> Customer | None:
        if data is None:
            return self.job.customer if not self.is_new else self._initial_customer()
        raw = data.get("job-customer")
        if not raw or not str(raw).isdigit():
            return None
        return Customer.objects.filter(pk=raw).first()

    def _initial_customer(self) -> Customer | None:
        value = (self.form.initial or {}).get("customer")
        if value and str(value).isdigit():
            return Customer.objects.filter(pk=value).first()
        return None

    def _first_day_initial(self, initial: dict) -> dict:
        user = self.request.user
        day = {"date": timezone.localdate()}
        role = CrewRole.default()
        if role is not None:
            day[f"crew_{role.pk}"] = [user.pk] if role.allow_multiple else user.pk
        for type_id, ids in services.last_used_equipment(user).items():
            day[f"equipment_{type_id}"] = ids
        day.update(initial.get("day", {}))
        return day

    # -- validation & saving ---------------------------------------------------------------
    def is_valid(self) -> bool:
        results = [self.form.is_valid(), self.days.is_valid(), self.charges.is_valid()]
        results.extend(bound.form.is_valid() for bound in self.sections)
        return all(results)

    @transaction.atomic
    def save(self) -> Job:
        job = self.form.save(commit=False)
        live_days = self.days.live_forms()
        if len(live_days) > 1:
            job.is_multi_day = True
        if self.is_new:
            job.created_by = self.request.user
            first_date = min(f.cleaned_data["date"] for f in live_days)
            services.assign_number(job, first_date)
        job.save()

        for form in self.days.forms:
            if self.days._should_delete_form(form) and form.instance.pk:
                form.instance.delete()
        ordered = sorted(
            enumerate(live_days), key=lambda item: (item[1].cleaned_data["date"], item[0])
        )
        for position, (_index, form) in enumerate(ordered, start=1):
            day = form.save(commit=False)
            day.job = job
            day.position = position
            day.save()
            form.save_m2m()
            day.equipment.set(form.selected_equipment())
            services.set_day_crew(day, form.selected_crew())

        for form in self.charges.forms:
            if self.charges._should_delete_form(form):
                if form.instance.pk:
                    form.instance.delete()
                continue
            if form.cleaned_data.get("amount") is None:
                continue  # the empty row
            charge = form.save(commit=False)
            charge.job = job
            charge.save()

        services.recalculate_job(job)
        for bound in self.sections:
            bound.section.save(self.request, bound.form, job)
        return job

    # -- layout-only actions ("add a day", "add a charge") -------------------------------------
    @staticmethod
    def with_extra_day(data):
        """Copy of the POST data with one more day, continuing from the last one."""
        data = data.copy()
        total = int(data.get("days-TOTAL_FORMS") or 0)
        previous, new = total - 1, total
        data["days-TOTAL_FORMS"] = str(total + 1)
        try:
            previous_date = parse_date(data.get(f"days-{previous}-date") or "")
        except ValueError:
            previous_date = None
        next_date = previous_date + timedelta(days=1) if previous_date else timezone.localdate()
        data[f"days-{new}-date"] = next_date.isoformat()
        prefix = f"days-{previous}-"
        for key in list(data.keys()):
            if key.startswith(prefix):
                name = key[len(prefix) :]
                if name.startswith(("crew_", "equipment_")):
                    data.setlist(f"days-{new}-{name}", data.getlist(key))
        data["job-is_multi_day"] = "on"
        return data

    @staticmethod
    def with_extra_charge(data):
        data = data.copy()
        data["charges-TOTAL_FORMS"] = str(int(data.get("charges-TOTAL_FORMS") or 0) + 1)
        return data

    def without_errors(self) -> JobFormBundle:
        suppress_validation(self.form, self.days, self.charges, *(b.form for b in self.sections))
        return self

    # -- template helpers ----------------------------------------------------------------------
    @property
    def operation_rates(self) -> dict[str, str]:
        return self.form.operation_rates

    @property
    def rate_was_set(self) -> bool:
        return not self.is_new


class FinishDayForm(forms.Form):
    hectares = forms.DecimalField(
        label=_("Hectares done"),
        required=False,
        min_value=Decimal(0),
        max_digits=10,
        decimal_places=2,
        widget=DecimalInput(),
    )


class JobPhotoForm(forms.Form):
    photos = forms.FileField(
        label=_("Add photos"),
        widget=forms.ClearableFileInput(attrs={"accept": "image/*"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["photos"].widget.allow_multiple_selected = True
        self.fields["photos"].widget.attrs["multiple"] = True


class JobFilterForm(forms.Form):
    q = forms.CharField(label=_("Search"), required=False)
    status = forms.ChoiceField(
        label=_("Status"), required=False, choices=[("", _("Any status")), *Job.Status.choices]
    )
    operation = forms.ModelChoiceField(
        label=_("Operation"),
        queryset=OperationType.objects.all(),
        required=False,
        empty_label=_("Any operation"),
    )
    crop = forms.ModelChoiceField(
        label=_("Crop"), queryset=Crop.objects.all(), required=False, empty_label=_("Any crop")
    )
    customer = forms.ModelChoiceField(
        label=_("Customer"), queryset=Customer.objects.all(), required=False,
        widget=forms.HiddenInput(),
    )  # fmt: skip
    date_from = forms.DateField(label=_("From"), required=False, widget=DateInput())
    date_to = forms.DateField(label=_("To"), required=False, widget=DateInput())

    def filter(self, qs):
        if not self.is_valid():
            return qs
        data = self.cleaned_data
        if data["q"]:
            query = data["q"].strip()
            customer_ids = Customer.all_objects.search(query).values("pk")
            qs = qs.filter(Q(number__icontains=query) | Q(customer__in=customer_ids))
        if data["status"]:
            qs = qs.filter(status=data["status"])
        if data["operation"]:
            qs = qs.filter(operation_type=data["operation"])
        if data["crop"]:
            qs = qs.filter(crop=data["crop"])
        if data["customer"]:
            qs = qs.filter(customer=data["customer"])
        if data["date_from"]:
            qs = qs.filter(end_date__gte=data["date_from"])
        if data["date_to"]:
            qs = qs.filter(start_date__lte=data["date_to"])
        return qs
