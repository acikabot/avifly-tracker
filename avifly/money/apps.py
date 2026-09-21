from django.utils.translation import gettext_lazy as _

from avifly.core.modules import AviflyModule
from avifly.core.registry import (
    Component,
    LookupList,
    MenuItem,
    PermissionSection,
    Registry,
    TrashableModel,
)


class MoneyConfig(AviflyModule):
    default = True  # this module's config (apps.py also imports the AviflyModule base)
    name = "avifly.money"
    label = "money"
    verbose_name = _("Money")
    requires = ("core", "jobs", "equipment", "customers")
    url_prefix = "money/"

    def register(self, registry: Registry) -> None:
        from auditlog.registry import auditlog

        from avifly.jobs.forms import JOB_FORM_SECTIONS
        from avifly.money import components, receivers  # noqa: F401 - connects signal receivers
        from avifly.money.job_section import PaymentSection
        from avifly.money.models import Cost, CostCategory, Payment, PaymentMethod

        auditlog.register(Payment, exclude_fields=["updated_at"])
        auditlog.register(Cost, exclude_fields=["updated_at"])

        registry.add_menu_item(
            MenuItem(
                key="money",
                label=_("Money"),
                url_name="money:book",
                icon="cash-coin",
                permission="money.view_payment",
                order=30,
            )
        )
        registry.add_menu_item(
            MenuItem(
                key="new-cost",
                label=_("Add cost"),
                url_name="money:cost_add",
                icon="receipt",
                permission="money.add_cost",
                area="quick",
                order=2,
            )
        )
        registry.add_lookup(
            LookupList(PaymentMethod, description=_("How customers pay you."), order=30)
        )
        registry.add_lookup(
            LookupList(CostCategory, description=_("Kinds of costs, for the reports."), order=31)
        )
        registry.add_permission_section(
            PermissionSection(key="payments", label=_("Payments"), model="money.payment", order=30)
        )
        registry.add_permission_section(
            PermissionSection(
                key="costs",
                label=_("Costs"),
                model="money.cost",
                scope_permissions=(
                    "money.view_all_costs",
                    "money.change_all_costs",
                    "money.delete_all_costs",
                ),
                order=31,
            )
        )
        registry.add_trashable(TrashableModel(Cost, permission="money.delete_cost", order=30))
        registry.add_media_folder("receipts/", "money.view_cost")
        registry.add_extension(JOB_FORM_SECTIONS, PaymentSection())

        registry.add_component(
            "core.dashboard",
            Component(
                key="money.summary",
                template_name="money/components/dashboard_money.html",
                permission="money.view_payment",
                get_context=components.dashboard_money,
                order=30,
            ),
        )
        registry.add_component(
            "jobs.job_detail",
            Component(
                key="money.payment",
                template_name="money/components/job_payment.html",
                permission="money.view_payment",
                get_context=components.job_payment,
                order=10,
            ),
        )
        registry.add_component(
            "customers.customer_detail",
            Component(
                key="money.customer_payments",
                template_name="money/components/customer_payments.html",
                permission="money.view_payment",
                get_context=components.customer_payments,
                order=20,
            ),
        )
        registry.add_component(
            "equipment.equipment_detail",
            Component(
                key="money.equipment_costs",
                template_name="money/components/equipment_costs.html",
                permission="money.view_cost",
                get_context=components.equipment_costs,
                order=20,
            ),
        )
        registry.add_component(
            "equipment.equipment_actions",
            Component(
                key="money.equipment_add_cost",
                template_name="money/components/equipment_add_cost.html",
                permission="money.add_cost",
                order=10,
            ),
        )
