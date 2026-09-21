"""Jobs: one visit to one customer, made of one or more work days.

Every job has at least one :class:`JobDay`; a multi-day job simply has several. Each
day records its own field(s), equipment, crew, hectares and start/end times, so the
same structure serves a quick single-day job and a week away from home — and file
imports (e.g. DJI flight records) can fill in days one by one.

The totals on :class:`Job` (hectares, amounts, dates, status) are derived from the
days and extra charges by :func:`avifly.jobs.services.recalculate_job`.
"""

from __future__ import annotations

import uuid
from pathlib import PurePath

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from avifly.core.formatting import format_date
from avifly.core.models import (
    AliveManager,
    LookupModel,
    SoftDeleteModel,
    SoftDeleteQuerySet,
    TimeStampedModel,
)
from avifly.customers.models import Customer, FarmField
from avifly.equipment.models import Equipment


class OperationType(LookupModel):
    """Spraying, spreading, … each with its own default price per hectare."""

    default_rate_per_ha = models.DecimalField(
        _("default rate per ha"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    class Meta(LookupModel.Meta):
        verbose_name = _("operation type")
        verbose_name_plural = _("operation types")


class Crop(LookupModel):
    class Meta(LookupModel.Meta):
        verbose_name = _("crop")
        verbose_name_plural = _("crops")


class JobQuerySet(SoftDeleteQuerySet):
    def visible_to(self, user, action: str = "view"):
        """Jobs ``user`` may ``action`` (view/change/delete).

        Roles without the "everyone's jobs" permission only get jobs they created or
        worked on as crew.
        """
        if user.has_perm(f"jobs.{action}_all_jobs"):
            return self
        return self.filter(Q(created_by=user) | Q(days__crew=user)).distinct()

    def done(self):
        return self.filter(status=Job.Status.DONE)

    def worked(self):
        """Jobs with work in them (done or in progress)."""
        return self.filter(status__in=[Job.Status.DONE, Job.Status.IN_PROGRESS])


class Job(TimeStampedModel, SoftDeleteModel):
    class Status(models.TextChoices):
        PLANNED = "planned", _("Planned")
        IN_PROGRESS = "in_progress", _("In progress")
        DONE = "done", _("Done")
        CANCELLED = "cancelled", _("Cancelled")

    year = models.PositiveSmallIntegerField(editable=False)
    sequence = models.PositiveIntegerField(editable=False)
    number = models.CharField(_("job number"), max_length=20, unique=True, editable=False)

    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="jobs", verbose_name=_("customer")
    )
    operation_type = models.ForeignKey(
        OperationType, on_delete=models.PROTECT, related_name="jobs", verbose_name=_("operation")
    )
    crop = models.ForeignKey(
        Crop,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="jobs",
        verbose_name=_("crop"),
    )
    material_note = models.CharField(
        _("material"),
        max_length=500,
        blank=True,
        help_text=_("What was sprayed or spread (supplied by the customer)."),
    )
    rate_per_ha = models.DecimalField(
        _("rate per ha"), max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    is_multi_day = models.BooleanField(_("multi-day job"), default=False)
    is_cancelled = models.BooleanField(_("cancelled"), default=False)
    notes = models.TextField(_("notes"), blank=True)

    # Derived from the days and extra charges (see services.recalculate_job).
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status,
        default=Status.PLANNED,
        editable=False,
        db_index=True,
    )
    start_date = models.DateField(_("first day"), null=True, editable=False, db_index=True)
    end_date = models.DateField(_("last day"), null=True, editable=False, db_index=True)
    total_hectares = models.DecimalField(
        _("hectares"), max_digits=10, decimal_places=2, default=0, editable=False
    )
    work_minutes = models.PositiveIntegerField(_("work time (min)"), default=0, editable=False)
    base_amount = models.DecimalField(
        _("hectares × rate"), max_digits=12, decimal_places=2, default=0, editable=False
    )
    extras_amount = models.DecimalField(
        _("extra charges"), max_digits=12, decimal_places=2, default=0, editable=False
    )
    total_amount = models.DecimalField(
        _("total"), max_digits=12, decimal_places=2, default=0, editable=False
    )

    objects = AliveManager.from_queryset(JobQuerySet)()
    all_objects = models.Manager.from_queryset(JobQuerySet)()

    class Meta:
        ordering = ["-start_date", "-year", "-sequence"]
        verbose_name = _("job")
        verbose_name_plural = _("jobs")
        constraints = [
            models.UniqueConstraint(fields=["year", "sequence"], name="job_unique_year_sequence")
        ]
        permissions = [
            ("view_all_jobs", _("Can view everyone's jobs")),
            ("change_all_jobs", _("Can edit everyone's jobs")),
            ("delete_all_jobs", _("Can delete everyone's jobs")),
        ]

    def __str__(self) -> str:
        return f"{self.number} · {self.customer.name}"

    def get_absolute_url(self) -> str:
        return reverse("jobs:detail", args=[self.pk])

    @property
    def day_count(self) -> int:
        return len(self.days.all())

    @property
    def length_label(self) -> str:
        """“2-day job” for multi-day jobs, empty otherwise."""
        count = self.day_count
        if count < 2:
            return ""
        return ngettext("%(count)d-day job", "%(count)d-day job", count) % {"count": count}

    @property
    def current_day(self) -> JobDay | None:
        days = list(self.days.all())
        return days[-1] if days else None


class JobDay(models.Model):
    """One day of work on a job."""

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="days")
    position = models.PositiveSmallIntegerField(_("day"), default=1)
    date = models.DateField(_("date"))
    start_time = models.TimeField(_("start"), null=True, blank=True)
    end_time = models.TimeField(_("end"), null=True, blank=True)
    hectares = models.DecimalField(
        _("hectares"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    farm_fields = models.ManyToManyField(
        FarmField, blank=True, related_name="job_days", verbose_name=_("fields")
    )
    equipment = models.ManyToManyField(
        Equipment, blank=True, related_name="job_days", verbose_name=_("equipment")
    )
    crew = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="job_days", verbose_name=_("crew")
    )
    notes = models.CharField(_("notes"), max_length=300, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True, editable=False)

    # Where the numbers came from: "manual", or the key of an importer. Imported days
    # keep the importer's record id (prevents double imports) and the raw record.
    source = models.CharField(_("source"), max_length=50, default="manual", editable=False)
    external_id = models.CharField(max_length=200, blank=True, editable=False)
    raw_data = models.JSONField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["position", "date", "pk"]
        verbose_name = _("job day")
        verbose_name_plural = _("job days")
        constraints = [
            models.UniqueConstraint(
                fields=["source", "external_id"],
                condition=~Q(external_id=""),
                name="jobday_unique_external_record",
            )
        ]

    def __str__(self) -> str:
        return f"{self.job.number} — {format_date(self.date)}"

    def save(self, *args, **kwargs):
        from avifly.jobs.services import compute_duration

        self.duration_minutes = compute_duration(self.start_time, self.end_time)
        super().save(*args, **kwargs)

    @property
    def is_running(self) -> bool:
        return self.start_time is not None and self.end_time is None

    @property
    def is_imported(self) -> bool:
        return self.source != "manual"


class ExtraCharge(models.Model):
    """An extra line on the price, with a note explaining it (negative = discount)."""

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="extra_charges")
    note = models.CharField(_("what for"), max_length=200)
    amount = models.DecimalField(_("amount"), max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["pk"]
        verbose_name = _("extra charge")
        verbose_name_plural = _("extra charges")

    def __str__(self) -> str:
        return self.note


def job_photo_path(instance: JobPhoto, filename: str) -> str:
    suffix = PurePath(filename).suffix.lower() or ".jpg"
    return f"job_photos/{instance.job.year}/{instance.job.number}/{uuid.uuid4().hex}{suffix}"


class JobPhoto(TimeStampedModel):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(_("photo"), upload_to=job_photo_path)
    caption = models.CharField(_("caption"), max_length=200, blank=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = _("job photo")
        verbose_name_plural = _("job photos")

    def __str__(self) -> str:
        return self.caption or PurePath(self.image.name).name

    @property
    def url(self) -> str:
        return reverse("core:media", args=[self.image.name])
