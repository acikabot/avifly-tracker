from django.db import models
from django.utils.translation import gettext_lazy as _


class Analytics(models.Model):
    """Holds the analytics permission; there is no table behind it."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [("view_analytics", _("Can view analytics"))]

    def __str__(self) -> str:
        return "analytics"
