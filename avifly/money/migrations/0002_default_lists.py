"""Starter payment methods, cost categories and the single money account."""

from django.db import migrations

METHODS = ["Cash", "Invoice", "Other"]
CATEGORIES = [
    "Generator fuel",
    "Vehicle fuel",
    "Spare parts",
    "Repairs & maintenance",
    "Batteries",
    "Equipment purchase",
    "Accommodation & food",
    "Insurance & registration",
    "Phone & internet",
    "Software & subscriptions",
    "Other",
]


def create(apps, schema_editor):
    PaymentMethod = apps.get_model("money", "PaymentMethod")
    CostCategory = apps.get_model("money", "CostCategory")
    MoneyAccount = apps.get_model("money", "MoneyAccount")
    for order, name in enumerate(METHODS, start=1):
        PaymentMethod.objects.get_or_create(name=name, defaults={"sort_order": order * 10})
    for order, name in enumerate(CATEGORIES, start=1):
        CostCategory.objects.get_or_create(name=name, defaults={"sort_order": order * 10})
    MoneyAccount.objects.get_or_create(name="Main", defaults={"sort_order": 10})


class Migration(migrations.Migration):
    dependencies = [("money", "0001_initial")]
    operations = [migrations.RunPython(create, migrations.RunPython.noop)]
