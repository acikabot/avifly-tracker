"""Shared pytest fixtures: users with different access, and quick data builders."""

from __future__ import annotations

from datetime import time
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, Permission
from django.utils import timezone

from avifly.accounts.models import User
from avifly.customers.models import Customer, FarmField
from avifly.equipment.models import Equipment, EquipmentType
from avifly.jobs import services
from avifly.jobs.models import Job, JobDay, OperationType


@pytest.fixture(autouse=True)
def _media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"


def make_user(username: str, *, owner: bool = False, active: bool = True, perms=()) -> User:
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="correct horse battery staple",
        is_active=active,
        is_superuser=owner,
        is_staff=owner,
        approved_at=timezone.now() if active else None,
    )
    if perms:
        role = Group.objects.create(name=f"role-{username}")
        for perm in perms:
            app_label, codename = perm.split(".")
            role.permissions.add(
                Permission.objects.get(content_type__app_label=app_label, codename=codename)
            )
        user.groups.add(role)
    return user


@pytest.fixture
def owner(db):
    return make_user("owner", owner=True)


@pytest.fixture
def owner_client(client, owner):
    client.force_login(owner)
    return client


@pytest.fixture
def spraying(db):
    op = OperationType.objects.get(name="Spraying")
    op.default_rate_per_ha = Decimal("900")
    op.save()
    return op


@pytest.fixture
def customer(db):
    return Customer.objects.create(name="Goran Petrovski", town="Kumanovo", phone="+389 70 123 456")


@pytest.fixture
def field(customer):
    return FarmField.objects.create(
        customer=customer,
        name="Near the river",
        hectares=Decimal("12.40"),
        latitude=Decimal("42.13"),
        longitude=Decimal("21.71"),
    )


@pytest.fixture
def drone(db):
    return Equipment.objects.create(
        name="T50 #1",
        equipment_type=EquipmentType.objects.get(name="Drone"),
        serial_number="SN-T50-1",
    )


def make_job(customer, operation, *, days=((Decimal("10"), "2026-06-01"),), rate=None, user=None):
    """Create a job with the given (hectares, date) days and recalculate it."""
    job = Job(customer=customer, operation_type=operation, rate_per_ha=rate or Decimal("900"))
    services.assign_number(job)
    job.created_by = user
    job.save()
    for position, (hectares, day) in enumerate(days, start=1):
        JobDay.objects.create(
            job=job,
            position=position,
            date=day,
            hectares=hectares,
            start_time=time(8, 0),
            end_time=time(12, 30),
        )
    services.recalculate_job(job)
    return job


@pytest.fixture
def job(customer, spraying, owner):
    return make_job(customer, spraying, user=owner)
