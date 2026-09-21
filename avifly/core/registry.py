"""The module registry: how Avifly modules plug into each other.

Every Avifly module is a Django app whose ``AppConfig`` subclasses
:class:`avifly.core.modules.AviflyModule`. When Django starts, each module's
``register()`` hook tells this registry what it contributes:

* **menu items** for the navigation, the settings page and the dashboard's quick actions
* **components**: small templates rendered into named *slots* on other modules' pages
  (e.g. the money module puts a "Payment" panel into the ``jobs.job_detail`` slot)
* **editable lists** (operation types, crops, cost categories, …)
* **permission sections** shown in the role editor
* **extensions**: plug-in objects for extension points defined by other modules
  (e.g. job form sections, file importers)
* **protected media folders** and the permission needed to open files in them
* **restorable models** listed in the bin

Pages only ever ask the registry what is there, so switching a module off (dropping
it from ``AVIFLY_MODULES``) removes everything it contributed without touching the
rest of the code.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.db.models import Model
    from django.http import HttpRequest

    from avifly.core.modules import AviflyModule


@dataclass(frozen=True)
class MenuItem:
    """A link contributed to one of the menu *areas*.

    Areas: ``"main"`` (top navigation), ``"settings"`` (settings page) and
    ``"quick"`` (dashboard quick-action buttons).
    """

    key: str
    label: str
    url_name: str
    icon: str = "circle"
    permission: str | None = None
    order: int = 100
    area: str = "main"
    #: Optional callable ``(user) -> int | None`` shown as a badge (e.g. pending users).
    badge: Callable[[Any], int | None] | None = None
    #: URL namespace that marks this item as active (defaults to ``key``).
    namespace: str | None = None

    def is_visible(self, user) -> bool:
        if not user.is_authenticated:
            return False
        return self.permission is None or user.has_perm(self.permission)


@dataclass(frozen=True)
class Component:
    """A template rendered into a named slot on another page."""

    key: str
    template_name: str
    order: int = 100
    permission: str | None = None
    #: Optional ``(request, obj) -> dict`` providing extra template context.
    #: Returning ``None`` hides the component for this request.
    get_context: Callable[[HttpRequest, Any], dict | None] | None = None

    def is_visible(self, request: HttpRequest) -> bool:
        return self.permission is None or request.user.has_perm(self.permission)


@dataclass(frozen=True)
class LookupList:
    """A user-editable list of choices (a :class:`~avifly.core.models.LookupModel`)."""

    model: type[Model]
    fields: tuple[str, ...] = ("name", "is_active", "sort_order")
    list_display: tuple[str, ...] = ()
    description: str = ""
    order: int = 100

    @property
    def key(self) -> str:
        return self.model._meta.label_lower

    @property
    def label(self) -> str:
        return str(self.model._meta.verbose_name_plural).capitalize()


@dataclass(frozen=True)
class PermissionSection:
    """One row of the role editor.

    ``model`` is ``"app_label.model_name"``; ticking an action grants the model's
    standard ``<action>_<model>`` permission. ``scope_permissions`` are granted when
    the role may see *everyone's* records rather than only its own.
    """

    key: str
    label: str
    model: str
    actions: tuple[str, ...] = ("view", "add", "change", "delete")
    scope_permissions: tuple[str, ...] = ()
    extra_permissions: tuple[tuple[str, str], ...] = ()
    order: int = 100


@dataclass(frozen=True)
class TrashableModel:
    """A soft-deletable model whose deleted records are listed in the bin."""

    model: type[Model]
    permission: str
    order: int = 100

    @property
    def key(self) -> str:
        return self.model._meta.label_lower

    @property
    def label(self) -> str:
        return str(self.model._meta.verbose_name_plural).capitalize()


class Registry:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._modules: dict[str, AviflyModule] = {}
        self._menu: list[MenuItem] = []
        self._components: dict[str, list[Component]] = defaultdict(list)
        self._lookups: list[LookupList] = []
        self._permission_sections: list[PermissionSection] = []
        self._extensions: dict[str, list[Any]] = defaultdict(list)
        self._media: dict[str, str] = {}
        self._trash: list[TrashableModel] = []

    # -- modules -----------------------------------------------------------------------
    def add_module(self, module: AviflyModule) -> None:
        self._modules[module.label] = module

    def enabled_modules(self) -> list[AviflyModule]:
        return list(self._modules.values())

    def is_enabled(self, label: str) -> bool:
        return label in self._modules

    # -- menus ---------------------------------------------------------------------------
    def add_menu_item(self, item: MenuItem) -> None:
        self._menu = [m for m in self._menu if m.key != item.key or m.area != item.area]
        self._menu.append(item)

    def menu(self, user, area: str = "main") -> list[MenuItem]:
        items = [m for m in self._menu if m.area == area and m.is_visible(user)]
        return sorted(items, key=lambda m: (m.order, m.label))

    # -- components ------------------------------------------------------------------------
    def add_component(self, slot: str, component: Component) -> None:
        self._components[slot] = [c for c in self._components[slot] if c.key != component.key]
        self._components[slot].append(component)

    def components(self, slot: str, request: HttpRequest) -> list[Component]:
        visible = [c for c in self._components.get(slot, []) if c.is_visible(request)]
        return sorted(visible, key=lambda c: (c.order, c.key))

    # -- editable lists --------------------------------------------------------------------
    def add_lookup(self, lookup: LookupList) -> None:
        self._lookups = [lk for lk in self._lookups if lk.key != lookup.key]
        self._lookups.append(lookup)

    def lookups(self) -> list[LookupList]:
        return sorted(self._lookups, key=lambda lk: (lk.order, lk.label))

    def get_lookup(self, key: str) -> LookupList | None:
        return next((lk for lk in self._lookups if lk.key == key), None)

    # -- permissions -----------------------------------------------------------------------
    def add_permission_section(self, section: PermissionSection) -> None:
        self._permission_sections = [s for s in self._permission_sections if s.key != section.key]
        self._permission_sections.append(section)

    def permission_sections(self) -> list[PermissionSection]:
        return sorted(self._permission_sections, key=lambda s: (s.order, s.label))

    # -- extension points ------------------------------------------------------------------
    def add_extension(self, point: str, extension: Any) -> None:
        self._extensions[point].append(extension)

    def extensions(self, point: str) -> list[Any]:
        return sorted(self._extensions.get(point, []), key=lambda e: getattr(e, "order", 100))

    # -- protected media ---------------------------------------------------------------------
    def add_media_folder(self, prefix: str, permission: str) -> None:
        self._media[prefix.strip("/") + "/"] = permission

    def media_permission(self, path: str) -> str | None:
        """Permission needed to open an uploaded file, or ``None`` if unknown."""
        matches = [p for p in self._media if path.startswith(p)]
        return self._media[max(matches, key=len)] if matches else None

    # -- bin -----------------------------------------------------------------------------
    def add_trashable(self, trashable: TrashableModel) -> None:
        self._trash = [t for t in self._trash if t.key != trashable.key]
        self._trash.append(trashable)

    def trashables(self) -> list[TrashableModel]:
        return sorted(self._trash, key=lambda t: (t.order, t.label))

    def get_trashable(self, key: str) -> TrashableModel | None:
        return next((t for t in self._trash if t.key == key), None)


#: The single registry instance used by the whole app.
registry = Registry()
