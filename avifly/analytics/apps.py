from django.utils.translation import gettext_lazy as _

from avifly.core.modules import AviflyModule
from avifly.core.registry import MenuItem, PermissionSection, Registry


class AnalyticsConfig(AviflyModule):
    default = True  # this module's config (apps.py also imports the AviflyModule base)
    name = "avifly.analytics"
    label = "analytics"
    verbose_name = _("Analytics")
    requires = ("core", "jobs", "customers", "equipment")
    url_prefix = "analytics/"

    def register(self, registry: Registry) -> None:
        registry.add_menu_item(
            MenuItem(
                key="analytics",
                label=_("Analytics"),
                url_name="analytics:index",
                icon="graph-up",
                permission="analytics.view_analytics",
                order=50,
            )
        )
        registry.add_permission_section(
            PermissionSection(
                key="analytics",
                label=_("Analytics"),
                model="analytics.analytics",
                actions=(),
                extra_permissions=(("analytics.view_analytics", _("See analytics")),),
                order=50,
            )
        )
