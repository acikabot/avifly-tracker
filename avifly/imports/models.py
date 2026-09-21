from __future__ import annotations

import uuid
from pathlib import PurePath

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from avifly.core.models import TimeStampedModel
from avifly.jobs.models import JobDay


def import_path(instance: ImportBatch, filename: str) -> str:
    suffix = PurePath(filename).suffix.lower()
    return f"imports/{uuid.uuid4().hex}{suffix}"


class ImportBatch(TimeStampedModel):
    """One uploaded file and the records read from it."""

    importer_key = models.CharField(_("importer"), max_length=50)
    original_name = models.CharField(_("file"), max_length=255)
    file = models.FileField(upload_to=import_path)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("import")
        verbose_name_plural = _("imports")

    def __str__(self) -> str:
        return self.original_name

    def get_absolute_url(self) -> str:
        return reverse("imports:batch", args=[self.pk])


class ImportRow(models.Model):
    class Status(models.TextChoices):
        NEW = "new", _("New")
        DUPLICATE = "duplicate", _("Already imported")
        APPLIED = "applied", _("Added to a job")
        SKIPPED = "skipped", _("Skipped")

    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="rows")
    external_id = models.CharField(max_length=200)
    date = models.DateField(_("date"))
    start_time = models.TimeField(_("start"), null=True, blank=True)
    end_time = models.TimeField(_("end"), null=True, blank=True)
    hectares = models.DecimalField(
        _("hectares"), max_digits=10, decimal_places=2, null=True, blank=True
    )
    equipment_serial = models.CharField(_("serial number"), max_length=100, blank=True)
    raw = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=Status, default=Status.NEW)
    job_day = models.ForeignKey(
        JobDay, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["date", "start_time", "pk"]

    def __str__(self) -> str:
        return f"{self.batch} · {self.external_id}"
