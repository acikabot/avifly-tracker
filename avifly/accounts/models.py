from __future__ import annotations

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class AviflyUserManager(UserManager):
    def usable(self):
        """People who can sign in (and be picked as crew)."""
        return self.filter(is_active=True)

    def pending(self):
        """Signed up, waiting for an owner to approve them."""
        return self.filter(is_active=False, approved_at__isnull=True, is_superuser=False)

    def owners(self):
        return self.filter(is_active=True, is_superuser=True)


class User(AbstractUser):
    """A person who can sign in.

    *Owners* are superusers: they can do everything, including approving new
    sign-ups and deciding roles. Everyone else gets permissions from their role
    (a Django group). New sign-ups are inactive until an owner approves them.
    """

    approved_at = models.DateTimeField(_("approved"), null=True, blank=True)
    approved_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("approved by"),
    )

    objects = AviflyUserManager()

    class Meta(AbstractUser.Meta):
        swappable = "AUTH_USER_MODEL"
        ordering = ["first_name", "last_name", "username"]
        permissions = [("manage_users", _("Can approve users and manage roles"))]

    def __str__(self) -> str:
        return self.display_name

    @property
    def display_name(self) -> str:
        return self.get_full_name() or self.username

    @property
    def is_owner(self) -> bool:
        return self.is_active and self.is_superuser

    @property
    def is_pending(self) -> bool:
        return not self.is_active and self.approved_at is None and not self.is_superuser

    @property
    def role(self):
        """The user's role (first group), or ``None``."""
        groups = list(self.groups.all())
        return groups[0] if groups else None

    @property
    def role_label(self) -> str:
        if self.is_superuser:
            return str(_("Owner"))
        role = self.role
        return role.name if role else str(_("No role"))
