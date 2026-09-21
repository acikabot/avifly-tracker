from django import template
from django.conf import settings

from avifly.accounts import turnstile

register = template.Library()


@register.simple_tag
def turnstile_site_key() -> str:
    """The Turnstile site key, or an empty string when the bot check is off."""
    return settings.AVIFLY_TURNSTILE_SITE_KEY if turnstile.is_enabled() else ""
