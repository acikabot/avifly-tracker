from __future__ import annotations

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from avifly.core.models import LookupModel, SoftDeleteModel, TimeStampedModel


class EquipmentType(LookupModel):
    """A kind of equipment (Drone, Generator, Battery…), defined by the owners."""

    show_on_jobs = models.BooleanField(
        _("pick on jobs"),
        default=False,
        help_text=_("Show a dropdown for this type on every job day."),
    )
    allow_multiple = models.BooleanField(
        _("several per day"),
        default=False,
        help_text=_("Allow picking more than one per day (e.g. batteries)."),
    )

    class Meta(LookupModel.Meta):
        verbose_name = _("equipment type")
        verbose_name_plural = _("equipment types")


class Equipment(TimeStampedModel, SoftDeleteModel):
    class Status(models.TextChoices):
        ACTIVE = "active", _("In use")
        SPARE = "spare", _("Spare")
        RETIRED = "retired", _("Retired")
        SOLD = "sold", _("Sold")

    #: Statuses that can still be picked on new jobs.
    USABLE = (Status.ACTIVE, Status.SPARE)

    name = models.CharField(_("name"), max_length=100, help_text=_("e.g. “T50 #1”"))
    equipment_type = models.ForeignKey(
        EquipmentType, on_delete=models.PROTECT, related_name="items", verbose_name=_("type")
    )
    model_name = models.CharField(_("model"), max_length=100, blank=True)
    serial_number = models.CharField(
        _("serial number"),
        max_length=100,
        blank=True,
        db_index=True,
        help_text=_("Used to match imported flight records to this item."),
    )
    purchase_date = models.DateField(_("bought on"), null=True, blank=True)
    status = models.CharField(_("status"), max_length=20, choices=Status, default=Status.ACTIVE)
    notes = models.TextField(_("notes"), blank=True)

    class Meta:
        ordering = ["equipment_type__sort_order", "equipment_type__name", "name"]
        verbose_name = _("equipment")
        verbose_name_plural = _("equipment")

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("equipment:detail", args=[self.pk])

    @property
    def is_usable(self) -> bool:
        return self.status in self.USABLE
