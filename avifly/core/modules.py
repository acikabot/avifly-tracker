"""Base class for Avifly modules."""

from __future__ import annotations

from django.apps import AppConfig

from avifly.core.registry import Registry, registry


class AviflyModule(AppConfig):
    """``AppConfig`` base class for every Avifly module.

    A module declares which other modules it needs (``requires``, checked at start-up
    by ``avifly.core.checks``) and contributes its features to the registry in
    :meth:`register`. Its URLs are mounted at ``url_prefix``.

    Subclasses must set ``default = True``: their ``apps.py`` also imports this base
    class, and without the flag Django wouldn't know which config to use.
    """

    default_auto_field = "django.db.models.BigAutoField"

    #: App labels of the modules this module cannot work without.
    requires: tuple[str, ...] = ()
    #: Where this module's ``urls.py`` is mounted (``None`` = no pages).
    url_prefix: str | None = None

    def ready(self) -> None:
        registry.add_module(self)
        self.register(registry)

    def register(self, registry: Registry) -> None:
        """Contribute menu items, components, lists, permissions, … (override)."""
