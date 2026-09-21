from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse

from avifly import __version__
from avifly.core.models import get_business_settings
from avifly.core.registry import MenuItem, registry


@dataclass(frozen=True)
class NavLink:
    item: MenuItem
    url: str
    active: bool
    badge: int | None


def menu_links(request, area: str) -> list[NavLink]:
    user = request.user
    match = getattr(request, "resolver_match", None)
    namespace = match.namespace if match else ""
    links = []
    for item in registry.menu(user, area):
        badge = item.badge(user) if item.badge else None
        links.append(
            NavLink(
                item=item,
                url=reverse(item.url_name),
                active=namespace == (item.namespace or item.key),
                badge=badge or None,
            )
        )
    return links


def avifly(request):
    authenticated = request.user.is_authenticated
    return {
        "business": get_business_settings(),
        "nav_links": menu_links(request, "main") if authenticated else [],
        "settings_links": menu_links(request, "settings") if authenticated else [],
        "avifly_version": __version__,
    }
