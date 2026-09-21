"""Starter equipment types (change them under Settings → Lists → Equipment types)."""

from django.db import migrations

TYPES = [
    # name, pick on jobs, several per day
    ("Drone", True, False),
    ("Generator", True, False),
    ("Battery", False, True),
    ("Charger", False, False),
    ("Vehicle", False, False),
    ("Other", False, True),
]


def create(apps, schema_editor):
    EquipmentType = apps.get_model("equipment", "EquipmentType")
    for order, (name, show, multiple) in enumerate(TYPES, start=1):
        EquipmentType.objects.get_or_create(
            name=name,
            defaults={"show_on_jobs": show, "allow_multiple": multiple, "sort_order": order * 10},
        )


class Migration(migrations.Migration):
    dependencies = [("equipment", "0001_initial")]
    operations = [migrations.RunPython(create, migrations.RunPython.noop)]
