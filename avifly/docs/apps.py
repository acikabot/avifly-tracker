from django.utils.translation import gettext_lazy as _

from avifly.core.modules import AviflyModule
from avifly.core.registry import MenuItem, Registry


class DocsConfig(AviflyModule):
    default = True  # this module's config (apps.py also imports the AviflyModule base)
    name = "avifly.docs"
    label = "docs"
    verbose_name = _("Documentation")
    requires = ("core",)
    url_prefix = "docs/"

    def register(self, registry: Registry) -> None:
        registry.add_menu_item(
            MenuItem(
                key="docs",
                label=_("Documentation"),
                url_name="docs:index",
                icon="book",
                area="settings",
                order=95,
            )
        )
