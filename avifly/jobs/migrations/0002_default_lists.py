"""Starter entries for the editable lists (change them under Settings → Lists)."""

from django.db import migrations

OPERATIONS = ["Spraying", "Spreading"]
CROPS = [
    "Wheat",
    "Barley",
    "Maize",
    "Sunflower",
    "Rapeseed",
    "Alfalfa",
    "Rice",
    "Tobacco",
    "Vineyard",
    "Orchard",
    "Vegetables",
    "Other",
]


def create(apps, schema_editor):
    OperationType = apps.get_model("jobs", "OperationType")
    Crop = apps.get_model("jobs", "Crop")
    for order, name in enumerate(OPERATIONS, start=1):
        OperationType.objects.get_or_create(name=name, defaults={"sort_order": order * 10})
    for order, name in enumerate(CROPS, start=1):
        Crop.objects.get_or_create(name=name, defaults={"sort_order": order * 10})


class Migration(migrations.Migration):
    dependencies = [("jobs", "0001_initial")]
    operations = [migrations.RunPython(create, migrations.RunPython.noop)]
