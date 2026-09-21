"""Panels the jobs module contributes to other pages (dashboard, customer, equipment)."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Sum
from django.utils.translation import gettext as _

from avifly.core.periods import resolve_period
from avifly.jobs.models import Job, JobDay
from avifly.jobs.views import job_queryset


def _price_per_ha(amount, hectares) -> Decimal | None:
    """Area-weighted average price, in whole denars."""
    return (amount / hectares).quantize(Decimal(1)) if hectares else None


def active_jobs(request, obj):
    jobs = job_queryset(request.user)
    return {
        "in_progress": list(jobs.filter(status=Job.Status.IN_PROGRESS).order_by("start_date")[:10]),
        "planned": list(jobs.filter(status=Job.Status.PLANNED).order_by("start_date")[:10]),
    }


def work_summary(request, obj):
    periods = []
    for key in ("this_month", "this_season"):
        period = resolve_period(key)
        totals = (
            Job.objects.visible_to(request.user)
            .worked()
            .filter(end_date__gte=period.start, end_date__lte=period.end)
            .aggregate(
                jobs=Count("pk"),
                hectares=Sum("total_hectares"),
                minutes=Sum("work_minutes"),
                charged=Sum("total_amount"),
            )
        )
        totals["price_per_ha"] = _price_per_ha(totals["charged"], totals["hectares"])
        periods.append(
            {"label": _("This month") if key == "this_month" else period.label, **totals}
        )
    return {"periods": periods}


def customer_jobs(request, customer):
    jobs = job_queryset(request.user).filter(customer=customer)
    totals = jobs.worked().aggregate(
        count=Count("pk"), hectares=Sum("total_hectares"), charged=Sum("total_amount")
    )
    totals["price_per_ha"] = _price_per_ha(totals["charged"], totals["hectares"])
    return {"jobs": list(jobs[:25]), "totals": totals, "customer": customer}


def equipment_usage(request, equipment):
    days = JobDay.objects.filter(equipment=equipment, job__deleted_at__isnull=True)
    totals = days.aggregate(
        days=Count("pk"),
        jobs=Count("job", distinct=True),
        hectares=Sum("hectares"),
        minutes=Sum("duration_minutes"),
    )
    recent = days.select_related("job", "job__customer").order_by("-date", "-pk")[:15]
    return {"totals": totals, "recent_days": list(recent)}


# -- delete blockers ---------------------------------------------------------------------------
def customer_has_jobs(customer) -> str | None:
    count = Job.objects.filter(customer=customer).count()
    if count:
        return _(
            "%(name)s has %(count)d job(s), so they can't be deleted. Mark them inactive instead."
        ) % {"name": customer.name, "count": count}
    return None


def field_is_used(field) -> str | None:
    if JobDay.objects.filter(farm_fields=field, job__deleted_at__isnull=True).exists():
        return _("This field is used on jobs, so it can't be deleted. Mark it inactive instead.")
    return None


def equipment_is_used(equipment) -> str | None:
    if JobDay.objects.filter(equipment=equipment, job__deleted_at__isnull=True).exists():
        return _(
            "This equipment was used on jobs, so it can't be deleted. "
            "Set its status to retired or sold instead."
        )
    return None
