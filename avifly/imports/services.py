"""Turning uploaded files into job days."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Max

from avifly.core.registry import registry
from avifly.equipment.models import Equipment
from avifly.imports.base import IMPORTERS, BaseImporter
from avifly.imports.models import ImportBatch, ImportRow
from avifly.jobs.models import Job, JobDay
from avifly.jobs.services import recalculate_job


def importers() -> list[BaseImporter]:
    return registry.extensions(IMPORTERS)


def get_importer(key: str) -> BaseImporter | None:
    return next((i for i in importers() if i.key == key), None)


@transaction.atomic
def create_batch(importer: BaseImporter, upload, user) -> ImportBatch:
    """Read the file (raises ImportFileError) and store its records for review."""
    records = importer.parse(upload)
    upload.seek(0)
    batch = ImportBatch.objects.create(
        importer_key=importer.key, original_name=upload.name, file=upload, created_by=user
    )
    existing = set(
        JobDay.objects.filter(
            source=importer.key, external_id__in=[r.external_id for r in records]
        ).values_list("external_id", flat=True)
    )
    ImportRow.objects.bulk_create(
        ImportRow(
            batch=batch,
            external_id=record.external_id,
            date=record.date,
            start_time=record.start_time,
            end_time=record.end_time,
            hectares=record.hectares,
            equipment_serial=record.equipment_serial,
            raw=record.raw,
            status=(
                ImportRow.Status.DUPLICATE
                if record.external_id in existing
                else ImportRow.Status.NEW
            ),
        )
        for record in records
    )
    return batch


def _empty_day(job: Job) -> JobDay | None:
    """A planned day with nothing filled in yet, which an import can take over."""
    for day in job.days.all():
        if not day.hectares and not day.start_time and not day.is_imported:
            return day
    return None


@transaction.atomic
def apply_rows(rows: list[ImportRow], job: Job) -> list[JobDay]:
    """Add the chosen records to a job as days (the first may fill a planned day)."""
    batch_source = rows[0].batch.importer_key if rows else "manual"
    created = []
    for row in rows:
        if row.status != ImportRow.Status.NEW:
            continue
        day = _empty_day(job)
        if day is None:
            last = job.days.aggregate(last=Max("position"))["last"] or 0
            day = JobDay(job=job, position=last + 1)
        day.date = row.date
        day.start_time = row.start_time
        day.end_time = row.end_time
        day.hectares = row.hectares
        day.source = batch_source
        day.external_id = row.external_id
        day.raw_data = row.raw
        day.save()
        if row.equipment_serial:
            matches = Equipment.objects.filter(serial_number__iexact=row.equipment_serial)
            day.equipment.add(*matches)
        row.status = ImportRow.Status.APPLIED
        row.job_day = day
        row.save(update_fields=["status", "job_day"])
        created.append(day)
    if job.days.count() > 1 and not job.is_multi_day:
        job.is_multi_day = True
        job.save(update_fields=["is_multi_day", "updated_at"])
    recalculate_job(job)
    return created
