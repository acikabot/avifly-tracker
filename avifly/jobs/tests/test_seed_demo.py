import pytest
from django.core.management import call_command

from avifly.customers.models import Customer
from avifly.jobs.models import Job
from avifly.money.models import Cost, Payment

pytestmark = pytest.mark.django_db


def test_demo_data_can_be_added_and_removed(owner):
    real = Customer.objects.create(name="A real customer")
    call_command("seed_demo")
    assert Job.objects.count() > 50
    assert Payment.objects.exists()
    assert Cost.objects.exists()
    assert Job.objects.done().exists()

    call_command("seed_demo", "--remove")
    assert not Job.all_objects.exists()
    assert not Cost.all_objects.exists()
    assert list(Customer.all_objects.all()) == [real]
