from decimal import Decimal
from unittest import mock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from avifly.core import formatting
from avifly.core.checks import check_module_dependencies
from avifly.core.middleware import CloudflareAccessMiddleware, CloudflareRealIPMiddleware
from avifly.core.registry import MenuItem, Registry, registry
from avifly.core.text import normalize_search


@pytest.mark.parametrize(
    ("typed", "stored"),
    [
        ("petrovski", "Петровски"),
        ("gjorgjievski", "Ѓорѓиевски"),
        ("gorgievski", "Ѓорѓиевски"),
        ("đorđievski", "Ѓорѓиевски"),
        ("zivko", "Живко"),
        ("živko", "Живко"),
        ("kocani", "Кочани"),
    ],
)
def test_search_matches_across_alphabets(typed, stored):
    assert normalize_search(typed) in normalize_search(stored)


def test_money_formatting():
    assert formatting.format_money(Decimal("12160"), "MKD") == "12,160 MKD"
    assert formatting.format_money(Decimal("12160.5"), "MKD") == "12,160.50 MKD"
    assert formatting.format_money(None) == "—"
    assert formatting.format_hectares(Decimal("12.4")) == "12.40 ha"
    assert formatting.format_duration(320) == "5 h 20 min"


def test_menu_respects_permissions():
    reg = Registry()
    reg.add_menu_item(MenuItem("a", "A", "core:dashboard", permission="jobs.view_job"))
    reg.add_menu_item(MenuItem("b", "B", "core:dashboard"))
    user = mock.Mock(is_authenticated=True)
    user.has_perm.side_effect = lambda perm: False
    assert [m.key for m in reg.menu(user)] == ["b"]


def test_missing_module_dependency_is_reported():
    module = mock.Mock(label="invoices", requires=("money", "nonexistent"))
    with mock.patch.object(registry, "_modules", {**registry._modules, "invoices": module}):
        errors = check_module_dependencies(None)
    assert [e.id for e in errors] == ["avifly.E001"]
    assert "nonexistent" in errors[0].msg


def test_all_default_modules_are_registered():
    for label in (
        "core",
        "accounts",
        "customers",
        "equipment",
        "jobs",
        "money",
        "analytics",
        "imports",
    ):
        assert registry.is_enabled(label)
    assert check_module_dependencies(None) == []


# -- Cloudflare ---------------------------------------------------------------------------
def ok(request):
    return HttpResponse(request.META["REMOTE_ADDR"])


@override_settings(AVIFLY_TRUST_CLOUDFLARE=True, AVIFLY_TRUSTED_PROXIES=["127.0.0.1"])
def test_real_ip_only_trusted_from_cloudflared():
    middleware = CloudflareRealIPMiddleware(ok)
    factory = RequestFactory()
    trusted = factory.get("/", REMOTE_ADDR="127.0.0.1", HTTP_CF_CONNECTING_IP="203.0.113.7")
    assert middleware(trusted).content == b"203.0.113.7"
    spoofed = factory.get("/", REMOTE_ADDR="192.168.1.50", HTTP_CF_CONNECTING_IP="203.0.113.7")
    assert middleware(spoofed).content == b"192.168.1.50"


@override_settings(
    AVIFLY_CF_ACCESS_TEAM_DOMAIN="avifly.cloudflareaccess.com", AVIFLY_CF_ACCESS_AUD="aud-tag"
)
def test_cloudflare_access_token_is_required():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    middleware = CloudflareAccessMiddleware(ok)
    signing_key = mock.Mock(key=key.public_key())
    middleware._jwks_client = mock.Mock(
        get_signing_key_from_jwt=mock.Mock(return_value=signing_key)
    )
    factory = RequestFactory()

    def token(aud="aud-tag", issuer="https://avifly.cloudflareaccess.com"):
        return jwt.encode({"aud": aud, "iss": issuer, "email": "a@b.c"}, key, algorithm="RS256")

    assert middleware(factory.get("/")).status_code == 403
    good = factory.get("/", HTTP_CF_ACCESS_JWT_ASSERTION=token())
    assert middleware(good).status_code == 200
    wrong_app = factory.get("/", HTTP_CF_ACCESS_JWT_ASSERTION=token(aud="other"))
    assert middleware(wrong_app).status_code == 403
    assert middleware(factory.get("/healthz")).status_code == 200
