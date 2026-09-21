"""Job business rules: numbering, prices, totals, status and the start/finish flow."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from avifly.core.formatting import round_money
from avifly.customers.models import Customer
from avifly.jobs.models import ExtraCharge, Job, JobDay, OperationType
from avifly.jobs.signals import job_totals_changed


def resolve_rate(customer: Customer | None, operation_type: OperationType | None) -> Decimal | None:
    """Default price per hectare: the customer's special rate, else the operation's."""
    if customer is not None and customer.special_rate_per_ha is not None:
        return customer.special_rate_per_ha
    if operation_type is not None:
        return operation_type.default_rate_per_ha
    return None


def assign_number(job: Job, work_date: date | None = None) -> None:
    """Give a new job the next number of its year, e.g. ``2026-0042``."""
    year = (work_date or timezone.localdate()).year
    last = Job.all_objects.filter(year=year).aggregate(last=Max("sequence"))["last"] or 0
    job.year = year
    job.sequence = last + 1
    job.number = f"{year}-{job.sequence:04d}"


def compute_duration(start: time | None, end: time | None) -> int | None:
    """Minutes between two clock times (an end before the start means past midnight)."""
    if start is None or end is None:
        return None
    day = date(2000, 1, 1)
    delta = datetime.combine(day, end) - datetime.combine(day, start)
    if delta < timedelta(0):
        delta += timedelta(days=1)
    return int(delta.total_seconds() // 60)


def derive_status(job: Job, days: list[JobDay], hectares: Decimal) -> str:
    if job.is_cancelled:
        return Job.Status.CANCELLED
    if any(day.is_running for day in days):
        return Job.Status.IN_PROGRESS
    if hectares > 0:
        return Job.Status.DONE
    if any(day.start_time for day in days):
        return Job.Status.IN_PROGRESS
    return Job.Status.PLANNED


@transaction.atomic
def recalculate_job(job: Job) -> Job:
    """Refresh a job's totals from its days and extra charges, then announce it."""
    # Always read fresh rows: the job may carry prefetched (now stale) days.
    days = list(JobDay.objects.filter(job=job))
    hectares = sum((day.hectares or Decimal(0) for day in days), Decimal(0))
    extras = sum((c.amount for c in ExtraCharge.objects.filter(job=job)), Decimal(0))
    dates = [day.date for day in days]

    job.total_hectares = hectares
    job.work_minutes = sum(day.duration_minutes or 0 for day in days)
    job.start_date = min(dates) if dates else None
    job.end_date = max(dates) if dates else None
    job.base_amount = round_money(job.rate_per_ha * hectares)
    job.extras_amount = extras
    job.total_amount = job.base_amount + extras
    job.status = derive_status(job, days, hectares)
    # Views re-read the days after this, so drop anything prefetched earlier.
    getattr(job, "_prefetched_objects_cache", {}).pop("days", None)
    getattr(job, "_prefetched_objects_cache", {}).pop("extra_charges", None)
    job.save(
        update_fields=[
            "total_hectares", "work_minutes", "start_date", "end_date", "base_amount",
            "extras_amount", "total_amount", "status", "updated_at",
        ]
    )  # fmt: skip
    job_totals_changed.send(sender=Job, job=job)
    return job


def _now() -> datetime:
    return timezone.localtime().replace(second=0, microsecond=0)


@transaction.atomic
def start_day(day: JobDay, user=None) -> JobDay:
    """Stamp the start time (the day moves to today if it was planned for another date)."""
    now = _now()
    day.date = now.date()
    day.start_time = now.time()
    day.end_time = None
    day.save()
    if user is not None and user.is_active:
        day.crew.add(user)
    recalculate_job(day.job)
    return day


@transaction.atomic
def finish_day(day: JobDay, hectares: Decimal | None = None) -> JobDay:
    day.end_time = _now().time()
    if hectares is not None:
        day.hectares = hectares
    day.save()
    recalculate_job(day.job)
    return day


@transaction.atomic
def start_next_day(job: Job, user=None) -> JobDay:
    """Continue a job on another day, with the same equipment and crew as last time."""
    previous = job.days.last()
    now = _now()
    day = JobDay.objects.create(
        job=job,
        position=(previous.position + 1) if previous else 1,
        date=now.date(),
        start_time=now.time(),
    )
    if previous is not None:
        day.equipment.set(previous.equipment.all())
        day.crew.set(previous.crew.all())
    if user is not None and user.is_active:
        day.crew.add(user)
    job.is_multi_day = True
    job.save(update_fields=["is_multi_day", "updated_at"])
    recalculate_job(job)
    return day


@transaction.atomic
def duplicate_job(job: Job, user) -> Job:
    """A new planned job for the same customer and work (a repeat treatment)."""
    today = timezone.localdate()
    copy = Job(
        customer=job.customer,
        operation_type=job.operation_type,
        crop=job.crop,
        material_note=job.material_note,
        rate_per_ha=job.rate_per_ha,
        created_by=user,
    )
    assign_number(copy, today)
    copy.save()
    source_day = job.days.last()
    day = JobDay.objects.create(job=copy, position=1, date=today)
    if source_day is not None:
        day.farm_fields.set(source_day.farm_fields.all())
        day.equipment.set(source_day.equipment.all())
        day.crew.set(source_day.crew.all())
    recalculate_job(copy)
    return copy


def last_used_equipment(user) -> dict[int, list[int]]:
    """Equipment ids per type from the user's most recent job day (form defaults)."""
    day = (
        JobDay.objects.filter(crew=user, job__deleted_at__isnull=True)
        .order_by("-date", "-pk")
        .prefetch_related("equipment")
        .first()
    )
    result: dict[int, list[int]] = {}
    if day is not None:
        for item in day.equipment.all():
            if item.is_usable:
                result.setdefault(item.equipment_type_id, []).append(item.pk)
    return result
