"""Cloudflare Turnstile verification (the bot check on the sign-up form)."""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def is_enabled() -> bool:
    return bool(settings.AVIFLY_TURNSTILE_SITE_KEY and settings.AVIFLY_TURNSTILE_SECRET_KEY)


def verify(token: str, remote_ip: str | None = None) -> bool:
    """Ask Cloudflare whether the Turnstile token from the browser is genuine."""
    if not token:
        return False
    payload = {"secret": settings.AVIFLY_TURNSTILE_SECRET_KEY, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip
    data = urllib.parse.urlencode(payload).encode()
    try:
        with urllib.request.urlopen(VERIFY_URL, data=data, timeout=10) as response:
            result = json.load(response)
    except (OSError, ValueError) as exc:
        logger.warning("Turnstile verification failed: %s", exc)
        return False
    return bool(result.get("success"))
