"""Keeps payments in step with their job (listens to the jobs module's events)."""

from django.dispatch import receiver

from avifly.jobs.signals import job_totals_changed
from avifly.money.models import Payment


@receiver(job_totals_changed)
def follow_job_total(sender, job, **kwargs):
    Payment.objects.filter(job=job, follows_job_total=True).exclude(amount=job.total_amount).update(
        amount=job.total_amount
    )
