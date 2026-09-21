"""The job form, end to end through the view (as the phone would post it)."""

from decimal import Decimal

import pytest
from django.urls import reverse

from avifly.customers.models import FarmField
from avifly.equipment.models import EquipmentType
from avifly.jobs.models import Job

pytestmark = pytest.mark.django_db


def job_post(customer, operation, days, *, multi=False, charges=(), extra=None):
    data = {
        "job-customer": customer.pk,
        "job-operation_type": operation.pk,
        "job-material_note": "Customer's herbicide",
        "job-rate_per_ha": "",
        "days-TOTAL_FORMS": str(len(days)),
        "days-INITIAL_FORMS": "0",
        "days-MIN_NUM_FORMS": "1",
        "days-MAX_NUM_FORMS": "1000",
        "charges-TOTAL_FORMS": str(len(charges)),
        "charges-INITIAL_FORMS": "0",
        "charges-MIN_NUM_FORMS": "0",
        "charges-MAX_NUM_FORMS": "1000",
        "action": "save",
    }
    if multi:
        data["job-is_multi_day"] = "on"
    for i, day in enumerate(days):
        for key, value in day.items():
            data[f"days-{i}-{key}"] = value
    for i, (note, amount) in enumerate(charges):
        data[f"charges-{i}-note"] = note
        data[f"charges-{i}-amount"] = amount
    data.update(extra or {})
    return data


def test_create_single_day_job(owner_client, owner, customer, field, spraying, drone):
    drone_type = EquipmentType.objects.get(name="Drone")
    day = {
        "date": "2026-06-01",
        "farm_fields": [field.pk],
        "hectares": "12.40",
        "start_time": "07:42",
        "end_time": "11:00",
        "crew": [owner.pk],
        f"equipment_{drone_type.pk}": drone.pk,
    }
    data = job_post(customer, spraying, [day], charges=[("Far field, extra travel", "1000")])
    response = owner_client.post(reverse("jobs:add"), data)
    assert response.status_code == 302, response.content.decode()[:2000]
    job = Job.objects.get()
    assert job.rate_per_ha == Decimal("900")  # from the operation's normal rate
    assert job.total_amount == Decimal("12160")
    assert job.status == Job.Status.DONE
    day = job.days.get()
    assert list(day.equipment.all()) == [drone]
    assert list(day.farm_fields.all()) == [field]
    assert day.duration_minutes == 198


def test_create_multi_day_job_with_different_fields(owner_client, owner, customer, field, spraying):
    hill = FarmField.objects.create(customer=customer, name="Hill")
    days = [
        {"date": "2026-06-18", "farm_fields": [field.pk], "hectares": "40", "crew": [owner.pk]},
        {"date": "2026-06-19", "farm_fields": [hill.pk], "hectares": "35.5", "crew": [owner.pk]},
    ]
    response = owner_client.post(
        reverse("jobs:add"), job_post(customer, spraying, days, multi=True)
    )
    assert response.status_code == 302
    job = Job.objects.get()
    assert job.is_multi_day
    assert [list(d.farm_fields.all()) for d in job.days.all()] == [[field], [hill]]
    assert job.total_hectares == Decimal("75.5")


def test_add_day_button_keeps_what_was_typed(owner_client, owner, customer, spraying, drone):
    drone_type = EquipmentType.objects.get(name="Drone")
    day = {
        "date": "2026-06-18",
        "hectares": "40",
        "crew": [owner.pk],
        f"equipment_{drone_type.pk}": drone.pk,
    }
    data = job_post(customer, spraying, [day], extra={"action": "add_day"})
    response = owner_client.post(reverse("jobs:add"), data)
    assert response.status_code == 200
    assert not Job.objects.exists()
    days = response.context["bundle"].days
    assert days.total_form_count() == 2
    new_day = days.forms[1]
    assert new_day["date"].value() == "2026-06-19"
    assert str(new_day[f"equipment_{drone_type.pk}"].value()) == str(drone.pk)
    assert "This field is required" not in response.content.decode()


def test_fields_must_belong_to_the_customer(owner_client, customer, spraying):
    from avifly.customers.models import Customer

    other = Customer.objects.create(name="Someone else")
    their_field = FarmField.objects.create(customer=other, name="Not yours")
    day = {"date": "2026-06-01", "farm_fields": [their_field.pk], "hectares": "5"}
    response = owner_client.post(reverse("jobs:add"), job_post(customer, spraying, [day]))
    assert response.status_code == 200
    assert not Job.objects.exists()


def test_rate_is_required_when_there_is_no_normal_rate(owner_client, customer):
    from avifly.jobs.models import OperationType

    spreading = OperationType.objects.get(name="Spreading")
    day = {"date": "2026-06-01", "hectares": "5"}
    response = owner_client.post(reverse("jobs:add"), job_post(customer, spreading, [day]))
    assert response.status_code == 200
    assert "enter the rate" in response.content.decode()


def test_edit_job_removes_a_day(owner_client, customer, spraying):
    from avifly.conftest import make_job

    job = make_job(
        customer, spraying, days=((Decimal("10"), "2026-06-01"), (Decimal("5"), "2026-06-02"))
    )
    days = list(job.days.all())
    data = {
        "job-customer": customer.pk,
        "job-operation_type": spraying.pk,
        "job-rate_per_ha": "900",
        "job-is_multi_day": "on",
        "days-TOTAL_FORMS": "2",
        "days-INITIAL_FORMS": "2",
        "days-MIN_NUM_FORMS": "1",
        "days-MAX_NUM_FORMS": "1000",
        "days-0-id": days[0].pk,
        "days-0-date": "2026-06-01",
        "days-0-hectares": "10",
        "days-1-id": days[1].pk,
        "days-1-date": "2026-06-02",
        "days-1-hectares": "5",
        "days-1-DELETE": "on",
        "charges-TOTAL_FORMS": "0",
        "charges-INITIAL_FORMS": "0",
        "charges-MIN_NUM_FORMS": "0",
        "charges-MAX_NUM_FORMS": "1000",
    }
    response = owner_client.post(reverse("jobs:edit", args=[job.pk]), data)
    assert response.status_code == 302
    job.refresh_from_db()
    assert job.days.count() == 1
    assert job.total_hectares == Decimal("10")


def test_start_and_finish_buttons(owner_client, customer, spraying):
    from avifly.conftest import make_job

    job = make_job(customer, spraying, days=((None, "2026-06-01"),))
    day = job.days.get()
    day.start_time = day.end_time = None
    day.save()
    owner_client.post(reverse("jobs:start_day", args=[job.pk, day.pk]))
    day.refresh_from_db()
    assert day.start_time is not None
    owner_client.post(reverse("jobs:finish_day", args=[job.pk, day.pk]), {"hectares": "7.5"})
    job.refresh_from_db()
    assert job.status == Job.Status.DONE
    assert job.total_hectares == Decimal("7.5")


def test_delete_moves_job_to_bin_and_restore(owner_client, job):
    owner_client.post(reverse("jobs:delete", args=[job.pk]))
    assert not Job.objects.filter(pk=job.pk).exists()
    assert Job.all_objects.filter(pk=job.pk).exists()
    owner_client.post(reverse("core:restore", args=["jobs.job", job.pk]))
    assert Job.objects.filter(pk=job.pk).exists()


def test_extra_charge_needs_both_parts(owner_client, customer, spraying):
    day = {"date": "2026-06-01", "hectares": "5"}
    only_note = job_post(customer, spraying, [day], charges=[("Far field", "")])
    response = owner_client.post(reverse("jobs:add"), only_note)
    assert response.status_code == 200
    assert "Enter the amount" in response.content.decode()
    blank_row = job_post(customer, spraying, [day], charges=[("", "")])
    assert owner_client.post(reverse("jobs:add"), blank_row).status_code == 302
    assert Job.objects.get().extras_amount == 0
