from django.contrib import admin

from avifly.customers.models import Customer, FarmField


class FarmFieldInline(admin.TabularInline):
    model = FarmField
    extra = 0
    fields = ("name", "hectares", "latitude", "longitude", "is_active")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "town", "phone", "is_active")
    search_fields = ("name", "town", "phone")
    inlines = [FarmFieldInline]
