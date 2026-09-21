import pytest
from django.contrib.auth.models import Group
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse

from avifly.accounts import services
from avifly.accounts.forms import RoleForm
from avifly.accounts.models import User
from avifly.conftest import make_user

pytestmark = pytest.mark.django_db

SIGNUP = {
    "first_name": "Marko",
    "last_name": "Trajkovski",
    "email": "marko@example.com",
    "username": "marko",
    "password1": "a-long enough passphrase 42",
    "password2": "a-long enough passphrase 42",
}


def test_signup_creates_a_pending_account_and_tells_owners(client, owner):
    response = client.post(reverse("account_signup"), SIGNUP)
    assert response.status_code == 302
    assert response["Location"] == reverse("account_inactive")
    user = User.objects.get(username="marko")
    assert not user.is_active
    assert user.is_pending
    assert user.get_full_name() == "Marko Trajkovski"
    assert any("waiting for approval" in m.subject for m in mail.outbox)


def test_pending_user_cannot_sign_in(client, owner):
    client.post(reverse("account_signup"), SIGNUP)
    client.logout()
    response = client.post(
        reverse("account_login"), {"login": "marko", "password": SIGNUP["password1"]}
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("account_inactive")
    assert "_auth_user_id" not in client.session


def test_owner_approves_with_a_role(owner_client, owner):
    pending = make_user("newbie", active=False)
    role = Group.objects.create(name="Pilot")
    response = owner_client.post(
        reverse("accounts:approve", args=[pending.pk]), {f"u{pending.pk}-role": role.pk}
    )
    assert response.status_code == 302
    pending.refresh_from_db()
    assert pending.is_active
    assert pending.approved_by == owner
    assert list(pending.groups.all()) == [role]


def test_reject_deletes_the_signup(owner_client):
    pending = make_user("spammer", active=False)
    owner_client.post(reverse("accounts:reject", args=[pending.pk]))
    assert not User.objects.filter(pk=pending.pk).exists()


def test_last_owner_cannot_be_removed(owner):
    with pytest.raises(ValidationError):
        services.update_access(owner, by=owner, role=None, make_owner=False, active=True)
    second = make_user("cousin", owner=True)
    services.update_access(owner, by=second, role=None, make_owner=False, active=True)
    owner.refresh_from_db()
    assert not owner.is_superuser


def test_only_owners_can_create_owners(owner):
    manager = make_user("manager", perms=["accounts.manage_users"])
    pending = make_user("someone", active=False)
    with pytest.raises(ValidationError):
        services.approve_user(pending, by=manager, role=None, make_owner=True)


def test_users_page_needs_permission(client):
    worker = make_user("worker")
    client.force_login(worker)
    assert client.get(reverse("accounts:users")).status_code == 403


def test_role_editor_grants_ticked_permissions():
    form = RoleForm(
        {
            "name": "Pilot",
            "jobs__add": "on",
            "jobs__change": "on",
            "jobs__scope": "own",
            "customers__view": "on",
        }
    )
    assert form.is_valid(), form.errors
    role = form.save()
    granted = {f"{p.content_type.app_label}.{p.codename}" for p in role.permissions.all()}
    # Adding/editing implies seeing; "own" scope doesn't grant everyone's jobs.
    assert {
        "jobs.view_job",
        "jobs.add_job",
        "jobs.change_job",
        "customers.view_customer",
    } <= granted
    assert "jobs.view_all_jobs" not in granted
    assert "jobs.delete_job" not in granted


def test_role_editor_everyones_scope():
    form = RoleForm({"name": "Office", "jobs__view": "on", "jobs__scope": "all"})
    assert form.is_valid(), form.errors
    role = form.save()
    assert role.permissions.filter(codename="view_all_jobs").exists()


def test_makeowner_command():
    user = make_user("founder", active=False)
    call_command("makeowner", "founder")
    user.refresh_from_db()
    assert user.is_active
    assert user.is_superuser
