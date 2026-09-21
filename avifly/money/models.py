"""Money: payments received for jobs and costs paid out.

For now all money goes into one account. The hidden ``account`` field on payments and
costs (and the payment ``status``, always "paid" today) are there so that separate
accounts, invoices and part-payments can be added later without reworking old data.
"""

from __future__ import annotations

import uuid
from pathlib import PurePath

from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from avifly.core.formatting import format_date
from avifly.core.models import (
    AliveManager,
    LookupModel,
    SoftDeleteModel,
    SoftDeleteQuerySet,
    TimeStampedModel,
)
from avifly.equipment.models import Equipment
from avifly.jobs.models import Job


class PaymentMethod(LookupModel):
    class Meta(LookupModel.Meta):
        verbose_name = _("payment method")
        verbose_name_plural = _("payment methods")


class CostCategory(LookupModel):
    class Meta(LookupModel.Meta):
        verbose_name = _("cost category")
        verbose_name_plural = _("cost categories")


class MoneyAccount(LookupModel):
    """Where money is kept. Only one ("Main") is used for now."""

    class Meta(LookupModel.Meta):
        verbose_name = _("money account")
        verbose_name_plural = _("money accounts")


def default_account_id() -> int | None:
    return MoneyAccount.objects.order_by("sort_order", "pk").values_list("pk", flat=True).first()


class Payment(TimeStampedModel, SoftDeleteModel):
    """Money received for a job."""

    soft_delete_parents = ("job",)

    class Status(models.TextChoices):
        PAID = "paid", _("Paid")

    job = models.ForeignKey(
        Job, on_delete=models.CASCADE, related_name="payments", verbose_name=_("job")
    )
    method = models.ForeignKey(
        PaymentMethod, on_delete=models.PROTECT, related_name="payments", verbose_name=_("method")
    )
    amount = models.DecimalField(_("amount"), max_digits=12, decimal_places=2)
    date = models.DateField(_("date"), default=timezone.localdate)
    note = models.CharField(
        _("note"), max_length=300, blank=True, help_text=_("e.g. invoice number")
    )
    follows_job_total = models.BooleanField(
        _("same as job total"),
        default=True,
        help_text=_("Keeps the amount equal to the job total, even when the job changes."),
    )
    status = models.CharField(
        _("status"), max_length=20, choices=Status, default=Status.PAID, editable=False
    )
    account = models.ForeignKey(
        MoneyAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        default=default_account_id,
        editable=False,
        related_name="payments",
    )

    class Meta:
        ordering = ["-date", "-pk"]
        verbose_name = _("payment")
        verbose_name_plural = _("payments")

    def __str__(self) -> str:
        return f"{self.job.number} · {self.method}"


class CostQuerySet(SoftDeleteQuerySet):
    def visible_to(self, user, action: str = "view"):
        if user.has_perm(f"money.{action}_all_costs"):
            return self
        return self.filter(created_by=user)


def receipt_path(instance: Cost, filename: str) -> str:
    suffix = PurePath(filename).suffix.lower() or ".jpg"
    day = instance.date or timezone.localdate()
    return f"receipts/{day:%Y/%m}/{uuid.uuid4().hex}{suffix}"


class Cost(TimeStampedModel, SoftDeleteModel):
    """Money paid out: fuel, parts, repairs, the drone itself…"""

    date = models.DateField(_("date"), default=timezone.localdate)
    amount = models.DecimalField(
        _("amount"), max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    category = models.ForeignKey(
        CostCategory, on_delete=models.PROTECT, related_name="costs", verbose_name=_("category")
    )
    description = models.CharField(
        _("what for"), max_length=200, help_text=_("e.g. “New propeller” or “Diesel”")
    )
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="costs",
        verbose_name=_("equipment"),
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="costs",
        verbose_name=_("job"),
    )
    receipt = models.FileField(_("receipt"), upload_to=receipt_path, blank=True)
    notes = models.TextField(_("notes"), blank=True)
    account = models.ForeignKey(
        MoneyAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        default=default_account_id,
        editable=False,
        related_name="costs",
    )

    objects = AliveManager.from_queryset(CostQuerySet)()
    all_objects = models.Manager.from_queryset(CostQuerySet)()

    class Meta:
        ordering = ["-date", "-pk"]
        verbose_name = _("cost")
        verbose_name_plural = _("costs")
        permissions = [
            ("view_all_costs", _("Can view everyone's costs")),
            ("change_all_costs", _("Can edit everyone's costs")),
            ("delete_all_costs", _("Can delete everyone's costs")),
        ]

    def __str__(self) -> str:
        return f"{self.description} ({format_date(self.date)})"

    def get_absolute_url(self) -> str:
        return reverse("money:cost_edit", args=[self.pk])

    @property
    def receipt_url(self) -> str:
        return reverse("core:media", args=[self.receipt.name]) if self.receipt else ""
