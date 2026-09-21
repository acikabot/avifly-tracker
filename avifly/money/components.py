"""Panels the money module adds to other modules' pages."""

from __future__ import annotations

from django.db.models import Sum

from avifly.core.periods import resolve_period
from avifly.money import selectors
from avifly.money.models import Cost, Payment


def dashboard_money(request, obj):
    return {
        "summaries": [
            selectors.summary(resolve_period("this_month")),
            selectors.summary(resolve_period("this_season")),
        ]
    }


def job_payment(request, job):
    costs = list(job.costs.select_related("category"))
    cost_total = sum((c.amount for c in costs), selectors.ZERO)
    return {
        "job": job,
        "payment": job.payments.select_related("method").first(),
        "costs": costs if request.user.has_perm("money.view_cost") else None,
        "cost_total": cost_total,
        "job_profit": job.total_amount - cost_total,
    }


def customer_payments(request, customer):
    payments = Payment.objects.filter(job__customer=customer).select_related("job", "method")
    return {
        "customer": customer,
        "received": payments.aggregate(s=Sum("amount"))["s"] or selectors.ZERO,
        "recent": list(payments[:10]),
    }


def equipment_costs(request, equipment):
    costs = Cost.objects.filter(equipment=equipment).select_related("category")
    return {
        "equipment": equipment,
        "total": costs.aggregate(s=Sum("amount"))["s"] or selectors.ZERO,
        "costs": list(costs[:20]),
    }
