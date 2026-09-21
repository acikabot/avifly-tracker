"""Every page renders for an owner, and nothing is visible when signed out."""

import pytest
from django.urls import reverse

from avifly.core.registry import registry

pytestmark = pytest.mark.django_db


def test_pages_render_for_owner(owner_client, job, field, drone):
    urls = [
        reverse("core:dashboard"),
        reverse("core:settings"),
        reverse("core:business_settings"),
        reverse("core:bin"),
        reverse("accounts:profile"),
        reverse("accounts:users"),
        reverse("accounts:roles"),
        reverse("accounts:role_add"),
        reverse("customers:list"),
        reverse("customers:add"),
        reverse("customers:detail", args=[field.customer_id]),
        reverse("customers:field_add", args=[field.customer_id]),
        reverse("customers:field_edit", args=[field.pk]),
        reverse("equipment:list"),
        reverse("equipment:add"),
        reverse("equipment:detail", args=[drone.pk]),
        reverse("jobs:list"),
        reverse("jobs:add"),
        reverse("jobs:detail", args=[job.pk]),
        reverse("jobs:edit", args=[job.pk]),
        reverse("jobs:delete", args=[job.pk]),
    ]
    urls += [reverse("core:lookup_list", args=[lookup.key]) for lookup in registry.lookups()]
    urls += [reverse("core:lookup_add", args=[lookup.key]) for lookup in registry.lookups()]
    if registry.is_enabled("money"):
        urls += [reverse("money:book"), reverse("money:costs"), reverse("money:cost_add")]
    for url in urls:
        response = owner_client.get(url)
        assert response.status_code == 200, url


def test_signed_out_visitors_are_sent_to_login(client, job):
    for url in (reverse("core:dashboard"), reverse("jobs:detail", args=[job.pk])):
        response = client.get(url)
        assert response.status_code == 302
        assert reverse("account_login") in response["Location"]


def test_login_and_signup_pages_are_public(client):
    assert client.get(reverse("account_login")).status_code == 200
    assert client.get(reverse("account_signup")).status_code == 200


def test_healthcheck_is_public(client):
    response = client.get(reverse("core:healthz"))
    assert response.status_code == 200
    assert response.content == b"ok"


def test_security_headers(owner_client):
    response = owner_client.get(reverse("core:dashboard"))
    assert "default-src 'self'" in response["Content-Security-Policy"]
    assert response["X-Frame-Options"] == "DENY"
