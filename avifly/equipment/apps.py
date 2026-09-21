from django.utils.translation import gettext_lazy as _

from avifly.core.modules import AviflyModule
from avifly.core.registry import (
    LookupList,
    MenuItem,
    PermissionSection,
    Registry,
    TrashableModel,
)


class EquipmentConfig(AviflyModule):
    default = True  # this module's config (apps.py also imports the AviflyModule base)
    name = "avifly.equipment"
    label = "equipment"
    verbose_name = _("Equipment")
    requires = ("core",)
    url_prefix = "equipment/"

    def register(self, registry: Registry) -> None:
        from auditlog.registry import auditlog

        from avifly.equipment.models import Equipment, EquipmentType

        auditlog.register(Equipment, exclude_fields=["updated_at"])

        registry.add_menu_item(
            MenuItem(
                key="equipment",
                label=_("Equipment"),
                url_name="equipment:list",
                icon="tools",
                permission="equipment.view_equipment",
                order=40,
            )
        )
        registry.add_permission_section(
            PermissionSection(
                key="equipment", label=_("Equipment"), model="equipment.equipment", order=40
            )
        )
        registry.add_lookup(
            LookupList(
                EquipmentType,
                fields=("name", "show_on_jobs", "allow_multiple", "is_active", "sort_order"),
                list_display=("show_on_jobs", "allow_multiple"),
                description=_("Kinds of equipment, and which ones you pick on each job day."),
                order=40,
            )
        )
        registry.add_trashable(
            TrashableModel(Equipment, permission="equipment.delete_equipment", order=40)
        )
