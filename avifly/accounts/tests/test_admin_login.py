"""The Django admin signs people in through the app's own login (lockout + two-step)."""

import pytest
from django.urls import reverse

from avifly.conftest import make_user

pytestmark = pytest.mark.django_db


def test_admin_login_sends_visitors_to_the_app_login(client):
    response = client.get(reverse("admin:login"))
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("account_login"))


def test_admin_login_form_cannot_be_used_directly(client, owner):
    response = client.post(
        reverse("admin:login"),
        {"username": owner.username, "password": "correct horse battery staple"},
    )
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("account_login"))
    assert "_auth_user_id" not in client.session


def test_owner_still_reaches_the_admin(owner_client):
    assert owner_client.get(reverse("admin:index")).status_code == 200


def test_signed_in_non_staff_is_refused(client):
    client.force_login(make_user("crew"))
    assert client.get(reverse("admin:login")).status_code == 403
