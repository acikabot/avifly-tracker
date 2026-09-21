from django.utils.translation import gettext_lazy as _

from avifly.core.modules import AviflyModule
from avifly.core.registry import MenuItem, PermissionSection, Registry


class CoreConfig(AviflyModule):
    default = True  # this module's config (apps.py also imports the AviflyModule base)
    name = "avifly.core"
    label = "core"
    verbose_name = _("Core")
    url_prefix = ""

    def ready(self) -> None:
        from avifly.core import checks  # noqa: F401 - registers the system checks

        super().ready()

    def register(self, registry: Registry) -> None:
        registry.add_menu_item(
            MenuItem(
                key="business",
                label=_("Business details"),
                url_name="core:business_settings",
                icon="building",
                permission="core.manage_settings",
                area="settings",
                order=10,
            )
        )
        registry.add_menu_item(
            MenuItem(
                key="bin",
                label=_("Bin"),
                url_name="core:bin",
                icon="trash3",
                permission="core.use_bin",
                area="settings",
                order=90,
            )
        )
        registry.add_permission_section(
            PermissionSection(
                key="administration",
                label=_("Administration"),
                model="core.businesssettings",
                actions=(),
                extra_permissions=(
                    ("core.manage_settings", _("Edit business details and lists")),
                    ("core.view_history", _("See change history")),
                    ("core.use_bin", _("Restore deleted items")),
                ),
                order=900,
            )
        )
