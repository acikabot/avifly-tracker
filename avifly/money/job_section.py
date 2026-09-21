"""The "Payment" section the money module adds to the job form."""

from __future__ import annotations

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from avifly.jobs.forms import JobFormSection
from avifly.jobs.models import Job
from avifly.money.forms import PaymentForm
from avifly.money.models import PaymentMethod


class PaymentSection(JobFormSection):
    key = "payment"
    title = _("Payment")
    template_name = "money/job_form_payment.html"
    order = 10

    def is_available(self, request, job):
        perm = "money.change_payment" if job and job.payments.exists() else "money.add_payment"
        return request.user.has_perm(perm)

    def get_form(self, request, job, data=None, files=None):
        payment = job.payments.first() if job is not None else None
        default_method = PaymentMethod.objects.filter(is_active=True).first()
        initial = {}
        if payment is None:
            initial = {"method": default_method, "follows_job_total": True}
        if data is not None and not any(key.startswith("payment-") for key in data):
            # The form was posted without this section: keep/assume the defaults.
            data = data.copy()
            data["payment-follows_job_total"] = "on"
            if payment is not None:
                data["payment-method"] = payment.method_id
                data["payment-follows_job_total"] = "on" if payment.follows_job_total else ""
                data["payment-amount"] = payment.amount
                data["payment-note"] = payment.note
            elif default_method is not None:
                data["payment-method"] = default_method.pk
        return PaymentForm(data, instance=payment, prefix="payment", initial=initial)

    def save(self, request, form, job: Job) -> None:
        # Money is only recorded once there's work on the job (all jobs count as paid).
        if job.status not in (Job.Status.DONE, Job.Status.IN_PROGRESS):
            return
        payment = form.save(commit=False)
        payment.job = job
        if payment.follows_job_total or payment.amount is None:
            payment.follows_job_total = True
            payment.amount = job.total_amount
        payment.date = form.cleaned_data.get("date") or job.end_date or timezone.localdate()
        if payment.pk is None:
            if payment.amount <= 0:
                return
            payment.created_by = request.user
        payment.save()
