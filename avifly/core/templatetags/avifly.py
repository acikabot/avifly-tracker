"""Template tags and filters shared by every module: ``{% load avifly %}``."""

from __future__ import annotations

from django import template
from django.forms import (
    CheckboxInput,
    CheckboxSelectMultiple,
    ClearableFileInput,
    FileInput,
    RadioSelect,
    Select,
    SelectMultiple,
)
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from avifly.core import formatting
from avifly.core.registry import registry

register = template.Library()


# -- formatting ------------------------------------------------------------------------
@register.filter
def money(value, currency=""):
    """``{{ amount|money }}`` → ``12,160 MKD``; ``{{ amount|money:None }}`` → ``12,160``."""
    return formatting.format_money(value, currency)


@register.filter
def number(value, places=0):
    return formatting.format_number(value, int(places))


@register.filter
def hectares(value):
    return formatting.format_hectares(value)


@register.filter
def duration(minutes):
    return formatting.format_duration(minutes)


# -- slots -------------------------------------------------------------------------------
@register.simple_tag(takes_context=True)
def render_slot(context, name, obj=None):
    """Render every component other modules registered for the slot ``name``."""
    request = context["request"]
    parts = []
    for component in registry.components(name, request):
        extra = {}
        if component.get_context is not None:
            extra = component.get_context(request, obj)
            if extra is None:
                continue
        ctx = {"object": obj, "slot_name": name, **extra}
        parts.append(render_to_string(component.template_name, ctx, request=request))
    return mark_safe("".join(parts))  # each part was rendered by the template engine


@register.simple_tag(takes_context=True)
def slot_has_content(context, name):
    return bool(registry.components(name, context["request"]))


@register.simple_tag
def module_enabled(label):
    return registry.is_enabled(label)


# -- forms ---------------------------------------------------------------------------------
@register.simple_tag
def render_widget(field, extra_class=""):
    """Render a bound field's widget with the right Bootstrap class."""
    widget = field.field.widget
    if isinstance(widget, CheckboxInput):
        css = "form-check-input"
    elif isinstance(widget, RadioSelect | CheckboxSelectMultiple):
        css = ""
    elif isinstance(widget, Select | SelectMultiple):
        css = "form-select"
    elif isinstance(widget, ClearableFileInput | FileInput):
        css = "form-control"
    else:
        css = "form-control"
    if field.errors:
        css += " is-invalid"
    existing = widget.attrs.get("class", "")
    classes = " ".join(c for c in (existing, css, extra_class) if c)
    return field.as_widget(attrs={"class": classes})


@register.filter
def is_checkbox(field):
    return isinstance(field.field.widget, CheckboxInput)


@register.filter
def is_multi_choice(field):
    return isinstance(field.field.widget, RadioSelect | CheckboxSelectMultiple)


# -- URLs ------------------------------------------------------------------------------------
@register.simple_tag(takes_context=True)
def query(context, **kwargs):
    """Current query string with some parameters replaced: ``?{% query page=2 %}``."""
    params = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value is None or value == "":
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode()


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


# -- change history ----------------------------------------------------------------------
@register.inclusion_tag("core/partials/history.html", takes_context=True)
def history(context, obj, limit=15):
    """Recent changes to ``obj`` (for users allowed to see the change history)."""
    request = context["request"]
    if obj is None or not request.user.has_perm("core.view_history"):
        return {"entries": None}
    from auditlog.models import LogEntry

    entries = LogEntry.objects.get_for_object(obj).select_related("actor")[: int(limit)]
    return {"entries": list(entries)}


# -- allauth element styling -------------------------------------------------------------
_BUTTON_COLOURS = ("danger", "secondary", "success", "warning", "link")


@register.filter
def btn_class(tags) -> str:
    """Bootstrap button classes for allauth's element ``tags`` (e.g. outline,primary)."""
    tags = set(tags or [])
    colour = next((c for c in _BUTTON_COLOURS if c in tags), "primary")
    if colour == "link":
        return "btn btn-link"
    css = f"btn btn-{'outline-' if 'outline' in tags else ''}{colour}"
    return css + (" btn-sm" if "minor" in tags else "")


@register.filter
def badge_class(tags) -> str:
    tags = set(tags or [])
    colour = next((c for c in ("success", "warning", "danger") if c in tags), "secondary")
    return f"badge text-bg-{colour}"
