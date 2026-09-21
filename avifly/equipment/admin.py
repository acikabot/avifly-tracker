from django.contrib import admin

from avifly.equipment.models import Equipment, EquipmentType


@admin.register(EquipmentType)
class EquipmentTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "show_on_jobs", "allow_multiple", "is_active", "sort_order")


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ("name", "equipment_type", "serial_number", "status")
    list_filter = ("equipment_type", "status")
