from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from avifly.accounts.models import User


@admin.register(User)
class AviflyUserAdmin(UserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "is_active", "is_superuser")
    fieldsets = (*UserAdmin.fieldsets, ("Approval", {"fields": ("approved_at", "approved_by")}))
