import os
import stat
from decimal import Decimal

import pytest
from django.urls import reverse

from avifly.conftest import make_job
from avifly.core.periods import Period
from avifly.jobs import services
from avifly.money import selectors
from avifly.money.models import Cost, CostCategory, Payment, PaymentMethod

pytestmark = pytest.mark.django_db


def post_job_with_payment(client, customer, operation, *, payment):
    data = {
        "job-customer": customer.pk,
        "job-operation_type": operation.pk,
        "days-TOTAL_FORMS": "1",
        "days-INITIAL_FORMS": "0",
        "days-MIN_NUM_FORMS": "1",
        "days-MAX_NUM_FORMS": "1000",
        "days-0-date": "2026-06-01",
        "days-0-hectares": "10",
        "charges-TOTAL_FORMS": "0",
        "charges-INITIAL_FORMS": "0",
        "charges-MIN_NUM_FORMS": "0",
        "charges-MAX_NUM_FORMS": "1000",
    }
    data.update({f"payment-{k}": v for k, v in payment.items()})
    return client.post(reverse("jobs:add"), data)


def test_payment_defaults_to_the_job_total(owner_client, customer, spraying):
    cash = PaymentMethod.objects.get(name="Cash")
    response = post_job_with_payment(
        owner_client, customer, spraying, payment={"method": cash.pk, "follows_job_total": "on"}
    )
    assert response.status_code == 302
    payment = Payment.objects.get()
    assert payment.amount == Decimal("9000")
    assert payment.status == Payment.Status.PAID
    assert payment.date.isoformat() == "2026-06-01"
    assert payment.account.name == "Main"


def test_payment_follows_later_changes_to_the_job(owner_client, customer, spraying):
    cash = PaymentMethod.objects.get(name="Cash")
    post_job_with_payment(
        owner_client, customer, spraying, payment={"method": cash.pk, "follows_job_total": "on"}
    )
    payment = Payment.objects.get()
    day = payment.job.days.get()
    services.finish_day(day, Decimal("12"))
    payment.refresh_from_db()
    assert payment.amount == Decimal("10800")


def test_custom_payment_amount_stays(owner_client, customer, spraying):
    invoice = PaymentMethod.objects.get(name="Invoice")
    post_job_with_payment(
        owner_client,
        customer,
        spraying,
        payment={"method": invoice.pk, "amount": "8500", "note": "INV-12"},
    )
    payment = Payment.objects.get()
    assert payment.amount == Decimal("8500")
    services.finish_day(payment.job.days.get(), Decimal("12"))
    payment.refresh_from_db()
    assert payment.amount == Decimal("8500")


def test_planned_jobs_have_no_payment_yet(owner_client, customer, spraying):
    cash = PaymentMethod.objects.get(name="Cash")
    data = {"method": cash.pk, "follows_job_total": "on"}
    response = post_job_with_payment(owner_client, customer, spraying, payment=data)
    assert response.status_code == 302
    Payment.objects.all().delete()
    # A job with no hectares and no start is planned: nothing is recorded.
    job = make_job(customer, spraying, days=((None, "2026-07-01"),))
    job.days.update(start_time=None, end_time=None)
    services.recalculate_job(job)
    assert not Payment.objects.filter(job=job).exists()


def test_money_book_balances(customer, spraying, owner):
    job = make_job(customer, spraying)
    Payment.objects.create(
        job=job, method=PaymentMethod.objects.first(), amount=9000, date="2026-06-01"
    )
    fuel = CostCategory.objects.get(name="Generator fuel")
    Cost.objects.create(date="2026-05-20", amount=1500, category=fuel, description="Petrol")
    Cost.objects.create(date="2026-06-02", amount=500, category=fuel, description="Petrol")
    opening, rows = selectors.money_book(Period(None, None, ""))
    assert opening == 0
    assert [r.balance for r in rows] == [Decimal("-1500"), Decimal("7500"), Decimal("7000")]
    june = Period(start=rows[1].date, end=rows[2].date, label="")
    opening, rows = selectors.money_book(june)
    assert opening == Decimal("-1500")
    assert selectors.summary(june).profit == Decimal("8500")


def test_payments_disappear_with_their_job(customer, spraying, owner):
    job = make_job(customer, spraying)
    Payment.objects.create(job=job, method=PaymentMethod.objects.first(), amount=9000)
    job.soft_delete(owner)
    assert not Payment.objects.exists()
    job.restore()
    assert Payment.objects.count() == 1


def test_add_cost_with_receipt(owner_client, drone):
    from django.core.files.uploadedfile import SimpleUploadedFile

    category = CostCategory.objects.get(name="Spare parts")
    receipt = SimpleUploadedFile("receipt.pdf", b"%PDF-1.4 test", content_type="application/pdf")
    response = owner_client.post(
        reverse("money:cost_add"),
        {
            "date": "2026-06-03",
            "amount": "500",
            "category": category.pk,
            "description": "New propeller",
            "equipment": drone.pk,
            "receipt": receipt,
        },
    )
    assert response.status_code == 302, response.content.decode()[:1500]
    cost = Cost.objects.get()
    assert cost.equipment == drone
    assert cost.receipt.name.startswith("receipts/2026/06/")
    # On disk, only the service account and its group can read it.
    assert stat.S_IMODE(os.stat(cost.receipt.path).st_mode) == 0o640
    # The receipt is only served to people who can see costs.
    assert owner_client.get(cost.receipt_url).status_code == 200


def test_receipts_are_private(client, owner_client, drone):
    from avifly.conftest import make_user

    category = CostCategory.objects.first()
    from django.core.files.uploadedfile import SimpleUploadedFile

    owner_client.post(
        reverse("money:cost_add"),
        {
            "date": "2026-06-03",
            "amount": "10",
            "category": category.pk,
            "description": "Fuel",
            "receipt": SimpleUploadedFile("r.pdf", b"%PDF", content_type="application/pdf"),
        },
    )
    cost = Cost.objects.get()
    outsider = make_user("outsider")
    client.force_login(outsider)
    assert client.get(cost.receipt_url).status_code == 404
