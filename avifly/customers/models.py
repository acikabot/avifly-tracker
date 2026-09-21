from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from avifly.core.models import AliveManager, SoftDeleteModel, SoftDeleteQuerySet, TimeStampedModel
from avifly.core.text import digits_only, normalize_search, search_terms


class CustomerQuerySet(SoftDeleteQuerySet):
    def search(self, query: str):
        """Match every word of ``query`` in any spelling (Cyrillic or Latin)."""
        qs = self
        for term in search_terms(query):
            qs = qs.filter(search_text__contains=term)
        return qs


class Customer(TimeStampedModel, SoftDeleteModel):
    name = models.CharField(_("name"), max_length=200)
    company_name = models.CharField(_("company"), max_length=200, blank=True)
    phone = models.CharField(_("phone"), max_length=50, blank=True)
    phone_alt = models.CharField(_("other phone"), max_length=50, blank=True)
    email = models.EmailField(_("e-mail"), blank=True)
    town = models.CharField(_("town / village"), max_length=100, blank=True)
    address = models.CharField(_("address"), max_length=300, blank=True)
    tax_number = models.CharField(_("tax number"), max_length=50, blank=True)
    special_rate_per_ha = models.DecimalField(
        _("special rate per ha"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=_("Leave empty to use the normal rate for the operation."),
    )
    notes = models.TextField(_("notes"), blank=True)
    is_active = models.BooleanField(
        _("active"), default=True, help_text=_("Inactive customers are hidden from new jobs.")
    )
    search_text = models.TextField(editable=False, blank=True)

    objects = AliveManager.from_queryset(CustomerQuerySet)()
    all_objects = models.Manager.from_queryset(CustomerQuerySet)()

    class Meta:
        ordering = ["name"]
        verbose_name = _("customer")
        verbose_name_plural = _("customers")

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        parts = [self.name, self.company_name, self.town, self.email, self.phone, self.phone_alt]
        phones = [digits_only(self.phone), digits_only(self.phone_alt)]
        self.search_text = " ".join(filter(None, [normalize_search(" ".join(parts)), *phones]))
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("customers:detail", args=[self.pk])

    @property
    def phone_link(self) -> str:
        return "".join(c for c in self.phone if c.isdigit() or c == "+")


class FarmField(TimeStampedModel, SoftDeleteModel):
    """A customer's field (parcel), pinned by its coordinates."""

    soft_delete_parents = ("customer",)

    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="farm_fields", verbose_name=_("customer")
    )
    name = models.CharField(_("name"), max_length=200)
    hectares = models.DecimalField(
        _("size (ha)"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    latitude = models.DecimalField(
        _("latitude"),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        _("longitude"),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    notes = models.TextField(
        _("notes"), blank=True, help_text=_("Obstacles, power lines, beehives, access…")
    )
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("field")
        verbose_name_plural = _("fields")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(latitude__isnull=True)
                | models.Q(latitude__gte=-90, latitude__lte=90),
                name="farmfield_latitude_range",
            ),
            models.CheckConstraint(
                condition=models.Q(longitude__isnull=True)
                | models.Q(longitude__gte=-180, longitude__lte=180),
                name="farmfield_longitude_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.customer.name})"

    def get_absolute_url(self) -> str:
        return reverse("customers:detail", args=[self.customer_id]) + f"#field-{self.pk}"

    @property
    def has_location(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def navigation_url(self) -> str:
        """Opens the field in the phone's maps app for directions."""
        if not self.has_location:
            return ""
        return (
            f"https://www.google.com/maps/dir/?api=1&destination={self.latitude},{self.longitude}"
        )

    def as_map_point(self, detail: str = "") -> dict:
        return {
            "lat": float(self.latitude),
            "lng": float(self.longitude),
            "label": self.name,
            "detail": detail,
            "url": self.get_absolute_url(),
        }
