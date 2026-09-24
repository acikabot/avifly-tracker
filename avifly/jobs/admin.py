from django.contrib import admin

from avifly.jobs.models import CrewRole, Crop, ExtraCharge, Job, JobDay, JobDayCrew, OperationType
from avifly.jobs.services import assign_number, recalculate_job


class JobDayInline(admin.StackedInline):
    model = JobDay
    extra = 0
    # "crew" carries a role per person (JobDayCrew), so it is edited on its own page.
    filter_horizontal = ("farm_fields", "equipment")


class ExtraChargeInline(admin.TabularInline):
    model = ExtraCharge
    extra = 0


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "number", "customer", "operation_type", "start_date", "total_hectares",
        "total_amount", "status",
    )  # fmt: skip
    list_filter = ("status", "operation_type")
    search_fields = ("number", "customer__name")
    readonly_fields = (
        "number", "status", "start_date", "end_date", "total_hectares", "work_minutes",
        "base_amount", "extras_amount", "total_amount",
    )  # fmt: skip
    inlines = [JobDayInline, ExtraChargeInline]

    def save_model(self, request, obj, form, change):
        if not obj.number:
            assign_number(obj)
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        recalculate_job(form.instance)


@admin.register(JobDayCrew)
class JobDayCrewAdmin(admin.ModelAdmin):
    list_display = ("job_day", "user", "role")
    list_filter = ("role",)


admin.site.register(OperationType)
admin.site.register(Crop)
admin.site.register(CrewRole)
