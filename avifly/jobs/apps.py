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


class JobsConfig(AviflyModule):
    default = True  # this module's config (apps.py also imports the AviflyModule base)
    name = "avifly.jobs"
    label = "jobs"
    verbose_name = _("Jobs")
    requires = ("core", "accounts", "customers", "equipment")
    url_prefix = "jobs/"

    def register(self, registry: Registry) -> None:
        from auditlog.registry import auditlog

        from avifly.customers.views import CUSTOMER_DELETE_BLOCKERS, FIELD_DELETE_BLOCKERS
        from avifly.equipment.views import DELETE_BLOCKERS as EQUIPMENT_DELETE_BLOCKERS
        from avifly.jobs import components
        from avifly.jobs.models import Crop, Job, OperationType

        auditlog.register(Job, exclude_fields=["updated_at", "year", "sequence"])

        registry.add_menu_item(
            MenuItem(
                key="jobs",
                label=_("Jobs"),
                url_name="jobs:list",
                icon="clipboard-check",
                permission="jobs.view_job",
                order=10,
            )
        )
        registry.add_menu_item(
            MenuItem(
                key="new-job",
                label=_("New job"),
                url_name="jobs:add",
                icon="plus-circle",
                permission="jobs.add_job",
                area="quick",
                order=1,
            )
        )
        registry.add_lookup(
            LookupList(
                OperationType,
                fields=("name", "default_rate_per_ha", "is_active", "sort_order"),
                list_display=("default_rate_per_ha",),
                description=_("What you do (spraying, spreading…) and the normal price per ha."),
                order=10,
            )
        )
        registry.add_lookup(LookupList(Crop, description=_("Crops you work on."), order=11))
        registry.add_permission_section(
            PermissionSection(
                key="jobs",
                label=_("Jobs"),
                model="jobs.job",
                scope_permissions=(
                    "jobs.view_all_jobs",
                    "jobs.change_all_jobs",
                    "jobs.delete_all_jobs",
                ),
                order=10,
            )
        )
        registry.add_trashable(TrashableModel(Job, permission="jobs.delete_job", order=10))
        registry.add_media_folder("job_photos/", "jobs.view_job")

        registry.add_component(
            "core.dashboard",
            Component(
                key="jobs.active",
                template_name="jobs/components/dashboard_active.html",
                permission="jobs.view_job",
                get_context=components.active_jobs,
                order=10,
            ),
        )
        registry.add_component(
            "core.dashboard",
            Component(
                key="jobs.summary",
                template_name="jobs/components/dashboard_summary.html",
                permission="jobs.view_job",
                get_context=components.work_summary,
                order=20,
            ),
        )
        registry.add_component(
            "customers.customer_detail",
            Component(
                key="jobs.customer_jobs",
                template_name="jobs/components/customer_jobs.html",
                permission="jobs.view_job",
                get_context=components.customer_jobs,
                order=10,
            ),
        )
        registry.add_component(
            "customers.customer_actions",
            Component(
                key="jobs.new_job_for_customer",
                template_name="jobs/components/customer_new_job.html",
                permission="jobs.add_job",
                order=10,
            ),
        )
        registry.add_component(
            "equipment.equipment_detail",
            Component(
                key="jobs.equipment_usage",
                template_name="jobs/components/equipment_usage.html",
                permission="jobs.view_job",
                get_context=components.equipment_usage,
                order=10,
            ),
        )
        registry.add_extension(CUSTOMER_DELETE_BLOCKERS, components.customer_has_jobs)
        registry.add_extension(FIELD_DELETE_BLOCKERS, components.field_is_used)
        registry.add_extension(EQUIPMENT_DELETE_BLOCKERS, components.equipment_is_used)
