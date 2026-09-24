"""Crew is recorded per role (Pilot, Ground crew…) instead of one flat list.

The people already on a day keep their place: they are copied into the new link
table under the first role, so nothing is lost.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

ROLES = [("Pilot", 10), ("Ground crew", 20)]


def create_roles_and_copy_crew(apps, schema_editor):
    CrewRole = apps.get_model("jobs", "CrewRole")
    JobDayCrew = apps.get_model("jobs", "JobDayCrew")
    JobDay = apps.get_model("jobs", "JobDay")

    for name, order in ROLES:
        CrewRole.objects.get_or_create(
            name=name, defaults={"sort_order": order, "allow_multiple": True}
        )
    first = CrewRole.objects.order_by("sort_order", "name").first()
    if first is None:
        return
    JobDayCrew.objects.bulk_create(
        [
            JobDayCrew(job_day_id=link.jobday_id, user_id=link.user_id, role_id=first.pk)
            for link in JobDay.crew.through.objects.all()
        ],
        ignore_conflicts=True,
    )


def copy_crew_back(apps, schema_editor):
    JobDay = apps.get_model("jobs", "JobDay")
    JobDayCrew = apps.get_model("jobs", "JobDayCrew")
    through = JobDay.crew.through
    seen = set()
    rows = []
    for link in JobDayCrew.objects.all():
        pair = (link.job_day_id, link.user_id)
        if pair not in seen:  # several roles collapse back into one entry
            seen.add(pair)
            rows.append(through(jobday_id=link.job_day_id, user_id=link.user_id))
    through.objects.bulk_create(rows, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0002_default_lists"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CrewRole",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=100, unique=True, verbose_name="name")),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Inactive entries are hidden from new forms.",
                        verbose_name="active",
                    ),
                ),
                ("sort_order", models.PositiveIntegerField(default=100, verbose_name="sort order")),
                (
                    "allow_multiple",
                    models.BooleanField(
                        default=True,
                        help_text="Allow picking more than one person for this role on a day.",
                        verbose_name="several per day",
                    ),
                ),
            ],
            options={
                "verbose_name": "crew role",
                "verbose_name_plural": "crew roles",
                "ordering": ["sort_order", "name"],
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="JobDayCrew",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "job_day",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="crew_links",
                        to="jobs.jobday",
                    ),
                ),
                (
                    "role",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="crew_links",
                        to="jobs.crewrole",
                        verbose_name="role",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="job_day_crew",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "crew member",
                "verbose_name_plural": "crew",
                "ordering": ["role__sort_order", "role__name", "pk"],
            },
        ),
        migrations.AddConstraint(
            model_name="jobdaycrew",
            constraint=models.UniqueConstraint(
                fields=("job_day", "user", "role"), name="jobdaycrew_unique_person_per_role"
            ),
        ),
        # Copy the existing crew across before the old table goes.
        migrations.RunPython(create_roles_and_copy_crew, copy_crew_back),
        migrations.RemoveField(model_name="jobday", name="crew"),
        migrations.AddField(
            model_name="jobday",
            name="crew",
            field=models.ManyToManyField(
                blank=True,
                related_name="job_days",
                through="jobs.JobDayCrew",
                to=settings.AUTH_USER_MODEL,
                verbose_name="crew",
            ),
        ),
    ]
