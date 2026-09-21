"""Read-only money queries shared by the money pages, dashboard and analytics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum

from avifly.core.periods import Period
from avifly.money.models import Cost, Payment

ZERO = Decimal(0)


def _in_period(qs, period: Period, field: str = "date"):
    if period.start:
        qs = qs.filter(**{f"{field}__gte": period.start})
    if period.end:
        qs = qs.filter(**{f"{field}__lte": period.end})
    return qs


def received(period: Period) -> Decimal:
    return _in_period(Payment.objects.all(), period).aggregate(s=Sum("amount"))["s"] or ZERO


def spent(period: Period) -> Decimal:
    return _in_period(Cost.objects.all(), period).aggregate(s=Sum("amount"))["s"] or ZERO


@dataclass(frozen=True)
class MoneySummary:
    period: Period
    received: Decimal
    spent: Decimal

    @property
    def profit(self) -> Decimal:
        return self.received - self.spent


def summary(period: Period) -> MoneySummary:
    return MoneySummary(period, received(period), spent(period))


@dataclass
class BookRow:
    date: date
    kind: str  # "in" or "out"
    label: str
    detail: str
    amount: Decimal
    url: str
    balance: Decimal = ZERO

    @property
    def signed(self) -> Decimal:
        return self.amount if self.kind == "in" else -self.amount


def money_book(period: Period) -> tuple[Decimal, list[BookRow]]:
    """Opening balance and every payment/cost in the period, oldest first, with balances."""
    opening = ZERO
    if period.start:
        before = Period(None, period.start - timedelta(days=1), "")
        opening = received(before) - spent(before)

    rows: list[BookRow] = []
    payments = _in_period(Payment.objects.select_related("job__customer", "method"), period)
    for p in payments:
        rows.append(
            BookRow(
                date=p.date,
                kind="in",
                label=f"{p.job.number} · {p.job.customer.name}",
                detail=f"{p.method}{' · ' + p.note if p.note else ''}",
                amount=p.amount,
                url=p.job.get_absolute_url(),
            )
        )
    costs = _in_period(Cost.objects.select_related("category", "equipment"), period)
    for c in costs:
        detail = str(c.category) + (f" · {c.equipment}" if c.equipment else "")
        rows.append(
            BookRow(
                date=c.date,
                kind="out",
                label=c.description,
                detail=detail,
                amount=c.amount,
                url=c.get_absolute_url(),
            )
        )
    rows.sort(key=lambda r: (r.date, r.kind != "in"))
    balance = opening
    for row in rows:
        balance += row.signed
        row.balance = balance
    return opening, rows
