from django.contrib import admin

from avifly.core.models import BusinessSettings


@admin.register(BusinessSettings)
class BusinessSettingsAdmin(admin.ModelAdmin):
    list_display = ("name", "currency")
