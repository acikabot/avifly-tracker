from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from avifly.analytics import selectors
from avifly.conftest import make_job, make_user
from avifly.core.periods import Period
from avifly.money.models import Cost, CostCategory, Payment, PaymentMethod

pytestmark = pytest.mark.django_db

JUNE = Period(date(2026, 6, 1), date(2026, 6, 30), "June")


@pytest.fixture
def season(customer, spraying):
    small = make_job(customer, spraying, days=((Decimal("2"), "2026-06-03"),), rate=Decimal("1500"))
    big = make_job(
        customer,
        spraying,
        days=((Decimal("40"), "2026-06-10"), (Decimal("38"), "2026-06-11")),
        rate=Decimal("900"),
    )
    cash = PaymentMethod.objects.get(name="Cash")
    for job in (small, big):
        Payment.objects.create(job=job, method=cash, amount=job.total_amount, date=job.end_date)
    Cost.objects.create(
        date=date(2026, 6, 12),
        amount=Decimal("6000"),
        category=CostCategory.objects.get(name="Generator fuel"),
        description="Petrol",
    )
    return small, big


def by_key(items):
    return {item.key: item for item in items}


def test_headline_numbers(season):
    kpis = by_key(selectors.kpis(selectors.Filters(JUNE)))
    assert kpis["hectares"].value == Decimal("80")
    assert kpis["jobs"].value == 2
    assert kpis["charged"].value == Decimal("3000") + Decimal("70200")
    assert kpis["costs"].value == Decimal("6000")
    assert kpis["profit"].value == Decimal("67200")
    # Area-weighted: (3,000 + 70,200) / 80 ha, not the mean of 1,500 and 900.
    assert kpis["price_per_ha"].value == Decimal("915")
    assert kpis["job_size"].value == Decimal("40")


def test_filters_leave_costs_out(season, spraying):
    filters = selectors.Filters(JUNE, operation=spraying)
    kpis = by_key(selectors.kpis(filters))
    assert kpis["costs"].value is None
    assert kpis["costs"].note


def test_charts_have_tables(season):
    charts = {c.key: c for c in selectors.all_charts(selectors.Filters(JUNE), None)}
    assert charts["top_customers"].table_rows[0][0] == "Goran Petrovski"
    assert charts["money_months"].table_rows == [
        ["Jun 2026", "73,200 MKD", "6,000 MKD", "67,200 MKD"]
    ]
    assert len(charts["calendar"].table_rows) == 3  # three working days


def test_page_renders_with_data(owner_client, season):
    response = owner_client.get(
        reverse("analytics:index"), {"period": "custom", "start": "2026-06-01", "end": "2026-06-30"}
    )
    assert response.status_code == 200
    assert "chart-data" in response.content.decode()


def test_page_needs_permission(client):
    worker = make_user("worker", perms=["jobs.view_job"])
    client.force_login(worker)
    assert client.get(reverse("analytics:index")).status_code == 403
