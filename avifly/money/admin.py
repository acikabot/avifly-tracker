from django.contrib import admin

from avifly.money.models import Cost, CostCategory, MoneyAccount, Payment, PaymentMethod


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("job", "date", "method", "amount", "follows_job_total")
    list_filter = ("method",)


@admin.register(Cost)
class CostAdmin(admin.ModelAdmin):
    list_display = ("date", "description", "category", "amount", "equipment", "job")
    list_filter = ("category",)
    search_fields = ("description",)


admin.site.register(PaymentMethod)
admin.site.register(CostCategory)
admin.site.register(MoneyAccount)
