from django.utils.translation import gettext_lazy as _

from avifly.core.modules import AviflyModule
from avifly.core.registry import MenuItem, PermissionSection, Registry


class ImportsConfig(AviflyModule):
    default = True  # this module's config (apps.py also imports the AviflyModule base)
    name = "avifly.imports"
    label = "imports"
    verbose_name = _("Imports")
    requires = ("core", "jobs", "equipment")
    url_prefix = "imports/"

    def register(self, registry: Registry) -> None:
        from avifly.imports.base import IMPORTERS
        from avifly.imports.importers.csv_importer import CsvImporter

        registry.add_extension(IMPORTERS, CsvImporter())
        registry.add_menu_item(
            MenuItem(
                key="imports",
                label=_("Import flight records"),
                url_name="imports:index",
                icon="cloud-upload",
                permission="imports.add_importbatch",
                area="settings",
                order=40,
            )
        )
        registry.add_permission_section(
            PermissionSection(
                key="imports",
                label=_("Imports"),
                model="imports.importbatch",
                actions=(),
                extra_permissions=(("imports.add_importbatch", _("Import files into jobs")),),
                order=60,
            )
        )
        registry.add_media_folder("imports/", "imports.add_importbatch")
