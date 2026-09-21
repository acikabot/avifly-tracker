"""Middleware for running safely behind Cloudflare, plus security headers."""

from __future__ import annotations

import logging

import jwt
from django.conf import settings
from django.http import HttpResponseForbidden

logger = logging.getLogger(__name__)


class CloudflareRealIPMiddleware:
    """Use the visitor's IP from ``CF-Connecting-IP`` instead of cloudflared's.

    Only trusted when the request comes from a trusted proxy address (cloudflared on
    this machine), so nobody on the network can fake their IP with the header. Login
    lockouts and the change history then see real visitor addresses.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.AVIFLY_TRUST_CLOUDFLARE:
            real_ip = request.META.get("HTTP_CF_CONNECTING_IP")
            if real_ip and request.META.get("REMOTE_ADDR") in settings.AVIFLY_TRUSTED_PROXIES:
                request.META["REMOTE_ADDR"] = real_ip.strip()
        return self.get_response(request)


class CloudflareAccessMiddleware:
    """Reject requests that did not pass Cloudflare Access (when it's configured).

    Cloudflare Access signs every request it lets through with a JWT in the
    ``Cf-Access-Jwt-Assertion`` header. Checking it here means that even a mistake in
    the tunnel configuration can't expose the app without Access in front of it.
    """

    EXEMPT_PATHS = ("/healthz",)

    def __init__(self, get_response):
        self.get_response = get_response
        self.team_domain = settings.AVIFLY_CF_ACCESS_TEAM_DOMAIN.strip().rstrip("/")
        self.audience = settings.AVIFLY_CF_ACCESS_AUD.strip()
        self.enabled = bool(self.team_domain and self.audience)
        self._jwks_client = None
        if self.enabled and not self.team_domain.startswith("https://"):
            self.team_domain = f"https://{self.team_domain}"

    @property
    def jwks_client(self) -> jwt.PyJWKClient:
        if self._jwks_client is None:
            self._jwks_client = jwt.PyJWKClient(
                f"{self.team_domain}/cdn-cgi/access/certs", cache_keys=True, lifespan=3600
            )
        return self._jwks_client

    def __call__(self, request):
        if self.enabled and request.path not in self.EXEMPT_PATHS:
            token = request.headers.get("Cf-Access-Jwt-Assertion", "")
            if not token or not self.verify(token):
                return HttpResponseForbidden("Access denied.")
        return self.get_response(request)

    def verify(self, token: str) -> bool:
        try:
            key = self.jwks_client.get_signing_key_from_jwt(token).key
            jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.team_domain,
            )
        except jwt.PyJWTError as exc:
            logger.warning("Rejected Cloudflare Access token: %s", exc)
            return False
        return True


class SecurityHeadersMiddleware:
    """Adds a Content-Security-Policy and a restrictive Permissions-Policy."""

    def __init__(self, get_response):
        self.get_response = get_response
        policy = settings.AVIFLY_CONTENT_SECURITY_POLICY
        self.csp = "; ".join(f"{name} {' '.join(values)}" for name, values in policy.items())

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("Content-Security-Policy", self.csp)
        # Location is used to pin fields; camera for photos; nothing else.
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(self), camera=(self), microphone=()"
        )
        return response
