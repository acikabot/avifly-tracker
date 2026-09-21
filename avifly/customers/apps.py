from django.utils.translation import gettext_lazy as _

from avifly.core.modules import AviflyModule
from avifly.core.registry import MenuItem, PermissionSection, Registry, TrashableModel


class CustomersConfig(AviflyModule):
    default = True  # this module's config (apps.py also imports the AviflyModule base)
    name = "avifly.customers"
    label = "customers"
    verbose_name = _("Customers")
    requires = ("core",)
    url_prefix = "customers/"

    def register(self, registry: Registry) -> None:
        from auditlog.registry import auditlog

        from avifly.customers.models import Customer, FarmField

        auditlog.register(Customer, exclude_fields=["search_text", "updated_at"])
        auditlog.register(FarmField, exclude_fields=["updated_at"])

        registry.add_menu_item(
            MenuItem(
                key="customers",
                label=_("Customers"),
                url_name="customers:list",
                icon="person-lines-fill",
                permission="customers.view_customer",
                order=20,
            )
        )
        registry.add_permission_section(
            PermissionSection(
                key="customers",
                label=_("Customers & fields"),
                model="customers.customer",
                order=20,
            )
        )
        registry.add_trashable(
            TrashableModel(Customer, permission="customers.delete_customer", order=20)
        )
        registry.add_trashable(
            TrashableModel(FarmField, permission="customers.change_customer", order=21)
        )
