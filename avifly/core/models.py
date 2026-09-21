"""Shared model building blocks and business-wide settings."""

from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    """Records when a row was created/changed and who created it."""

    created_at = models.DateTimeField(_("created"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated"), auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
        verbose_name=_("created by"),
    )

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(**self.model.alive_filter())

    def deleted(self):
        return self.filter(deleted_at__isnull=False)


class AliveManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Default manager: hides deleted rows (and rows whose parent was deleted)."""

    def get_queryset(self):
        return super().get_queryset().filter(**self.model.alive_filter())


class SoftDeleteModel(models.Model):
    """Rows are moved to the bin instead of being deleted, and can be restored.

    ``soft_delete_parents`` lists foreign keys whose deletion also hides this row
    (e.g. a payment disappears with its job and comes back when the job is restored).
    """

    soft_delete_parents: tuple[str, ...] = ()

    deleted_at = models.DateTimeField(
        _("deleted"), null=True, blank=True, editable=False, db_index=True
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
        verbose_name=_("deleted by"),
    )

    # Related-object access (e.g. ``job.customer``) uses Django's plain base manager,
    # so records that point at something in the bin keep working.
    objects = AliveManager()
    all_objects = models.Manager.from_queryset(SoftDeleteQuerySet)()

    class Meta:
        abstract = True

    @classmethod
    def alive_filter(cls) -> dict:
        lookups = {"deleted_at__isnull": True}
        for parent in cls.soft_delete_parents:
            lookups[f"{parent}__deleted_at__isnull"] = True
        return lookups

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self, user=None) -> None:
        self.deleted_at = timezone.now()
        self.deleted_by = user if user and user.is_authenticated else None
        self.save(update_fields=["deleted_at", "deleted_by"])

    def restore(self) -> None:
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=["deleted_at", "deleted_by"])


class LookupModel(models.Model):
    """A user-editable list of choices, e.g. crops or cost categories.

    Entries are never hardcoded: modules seed sensible defaults in a data migration
    and owners edit them under Settings → Lists.
    """

    name = models.CharField(_("name"), max_length=100, unique=True)
    is_active = models.BooleanField(
        _("active"), default=True, help_text=_("Inactive entries are hidden from new forms.")
    )
    sort_order = models.PositiveIntegerField(_("sort order"), default=100)

    class Meta:
        abstract = True
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name

    @classmethod
    def choices_for(cls, current=None):
        """Active entries, plus ``current`` even if it has been deactivated since."""
        qs = cls.objects.filter(is_active=True)
        if current is not None:
            qs = cls.objects.filter(models.Q(is_active=True) | models.Q(pk=current.pk))
        return qs


BUSINESS_SETTINGS_CACHE_KEY = "avifly:business-settings"


class BusinessSettings(models.Model):
    """Business-wide settings (a single row), editable under Settings."""

    name = models.CharField(_("business name"), max_length=200, default="Avifly")
    currency = models.CharField(
        _("currency"), max_length=10, default="MKD", help_text=_("Shown after amounts, e.g. MKD.")
    )
    address = models.CharField(_("address"), max_length=300, blank=True)
    phone = models.CharField(_("phone"), max_length=50, blank=True)
    email = models.EmailField(_("email"), blank=True)
    tax_number = models.CharField(_("tax number"), max_length=50, blank=True)
    bank_account = models.CharField(_("bank account"), max_length=100, blank=True)

    class Meta:
        verbose_name = _("business settings")
        verbose_name_plural = _("business settings")
        permissions = [
            ("manage_settings", _("Can edit business settings and lists")),
            ("view_history", _("Can view change history")),
            ("use_bin", _("Can restore deleted items")),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(BUSINESS_SETTINGS_CACHE_KEY)

    @classmethod
    def load(cls) -> BusinessSettings:
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj


def get_business_settings() -> BusinessSettings:
    """The business settings row, cached (shared by all server processes)."""
    obj = cache.get(BUSINESS_SETTINGS_CACHE_KEY)
    if obj is None:
        obj = BusinessSettings.load()
        cache.set(BUSINESS_SETTINGS_CACHE_KEY, obj, 300)
    return obj
