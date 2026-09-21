from datetime import time
from decimal import Decimal

import pytest

from avifly.conftest import make_job, make_user
from avifly.customers.models import Customer
from avifly.jobs import services
from avifly.jobs.models import Job, JobDay

pytestmark = pytest.mark.django_db


def test_totals_are_rate_times_hectares_plus_extras(job):
    assert job.total_hectares == Decimal("10")
    assert job.base_amount == Decimal("9000")
    job.extra_charges.create(note="Far field", amount=Decimal("1000"))
    job.extra_charges.create(note="Discount", amount=Decimal("-500"))
    services.recalculate_job(job)
    assert job.extras_amount == Decimal("500")
    assert job.total_amount == Decimal("9500")


def test_amounts_round_to_whole_denars(customer, spraying):
    job = make_job(
        customer, spraying, days=((Decimal("12.37"), "2026-06-01"),), rate=Decimal("950")
    )
    assert job.base_amount == Decimal("11752")  # 11751.50 rounds half up


def test_multi_day_job_adds_up_days(customer, spraying):
    job = make_job(
        customer,
        spraying,
        days=((Decimal("40"), "2026-06-18"), (Decimal("35.5"), "2026-06-19")),
    )
    assert job.total_hectares == Decimal("75.5")
    assert job.total_amount == Decimal("67950")
    assert job.start_date.isoformat() == "2026-06-18"
    assert job.end_date.isoformat() == "2026-06-19"
    assert job.length_label == "2-day job"
    assert job.work_minutes == 2 * 270


def test_job_numbers_count_per_year(customer, spraying):
    first = Job(customer=customer, operation_type=spraying, rate_per_ha=1)
    services.assign_number(first)
    first.save()
    second = Job(customer=customer, operation_type=spraying, rate_per_ha=1)
    services.assign_number(second)
    assert second.sequence == first.sequence + 1
    assert second.number.endswith(f"-{second.sequence:04d}")


def test_duration_across_midnight():
    assert services.compute_duration(time(22, 30), time(1, 0)) == 150
    assert services.compute_duration(time(8, 0), None) is None


def test_status_follows_the_work(customer, spraying):
    job = make_job(customer, spraying, days=((None, "2026-07-01"),))
    JobDay.objects.filter(job=job).update(start_time=None, end_time=None)
    services.recalculate_job(job)
    assert job.status == Job.Status.PLANNED

    day = job.days.get()
    services.start_day(day)
    job.refresh_from_db()
    assert job.status == Job.Status.IN_PROGRESS

    services.finish_day(day, Decimal("8"))
    job.refresh_from_db()
    assert job.status == Job.Status.DONE
    assert job.total_hectares == Decimal("8")

    job.is_cancelled = True
    job.save()
    services.recalculate_job(job)
    assert job.status == Job.Status.CANCELLED


def test_next_day_copies_equipment_and_crew(job, drone, owner):
    first = job.days.get()
    first.equipment.add(drone)
    first.crew.add(owner)
    day = services.start_next_day(job, owner)
    assert day.position == 2
    assert list(day.equipment.all()) == [drone]
    assert list(day.crew.all()) == [owner]
    job.refresh_from_db()
    assert job.is_multi_day
    assert job.status == Job.Status.IN_PROGRESS


def test_rate_prefers_the_customers_special_rate(customer, spraying):
    assert services.resolve_rate(customer, spraying) == Decimal("900")
    customer.special_rate_per_ha = Decimal("800")
    assert services.resolve_rate(customer, spraying) == Decimal("800")


def test_duplicate_makes_a_planned_copy(job, field, owner):
    job.days.get().farm_fields.add(field)
    copy = services.duplicate_job(job, owner)
    assert copy.status == Job.Status.PLANNED
    assert copy.number != job.number
    assert list(copy.days.get().farm_fields.all()) == [field]


def test_restricted_users_only_see_their_own_jobs(job, customer, spraying):
    pilot = make_user("pilot", perms=["jobs.view_job"])
    theirs = make_job(customer, spraying, user=pilot)
    crewed = make_job(customer, spraying)
    crewed.days.get().crew.add(pilot)
    visible = set(Job.objects.visible_to(pilot))
    assert visible == {theirs, crewed}


def test_customer_search_ignores_the_alphabet():
    Customer.objects.create(name="Горан Петровски", town="Куманово")
    Customer.objects.create(name="Živko Stojanov", town="Strumica")
    assert Customer.objects.search("petrovski").count() == 1
    assert Customer.objects.search("kumanovo goran").count() == 1
    assert Customer.objects.search("живко").count() == 1
    assert Customer.objects.search("zivko").count() == 1
