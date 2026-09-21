from __future__ import annotations

import mimetypes
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.core.exceptions import PermissionDenied, SuspiciousFileOperation
from django.db.models import ProtectedError
from django.forms import modelform_factory
from django.http import FileResponse, Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils._os import safe_join
from django.utils.translation import gettext as _
from django.views import View
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from avifly.core.context_processors import menu_links
from avifly.core.forms import BusinessSettingsForm
from avifly.core.mixins import PermissionRequired
from avifly.core.models import BusinessSettings
from avifly.core.registry import registry


class DashboardView(TemplateView):
    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(quick_links=menu_links(self.request, "quick"), **kwargs)


class SettingsView(TemplateView):
    template_name = "core/settings.html"

    def get_context_data(self, **kwargs):
        user = self.request.user
        return super().get_context_data(
            can_manage=user.has_perm("core.manage_settings"),
            lookups=registry.lookups(),
            can_use_bin=user.has_perm("core.use_bin"),
            **kwargs,
        )


class BusinessSettingsView(PermissionRequired, TemplateView):
    permission_required = "core.manage_settings"
    template_name = "core/business_settings.html"

    def get_context_data(self, **kwargs):
        kwargs.setdefault("form", BusinessSettingsForm(instance=BusinessSettings.load()))
        return super().get_context_data(**kwargs)

    def post(self, request):
        form = BusinessSettingsForm(request.POST, instance=BusinessSettings.load())
        if form.is_valid():
            form.save()
            messages.success(request, _("Business details saved."))
            return redirect("core:settings")
        return self.render_to_response(self.get_context_data(form=form))


# -- editable lists ------------------------------------------------------------------------
class LookupMixin(PermissionRequired):
    permission_required = "core.manage_settings"

    def dispatch(self, request, *args, **kwargs):
        self.lookup = registry.get_lookup(kwargs["key"])
        if self.lookup is None:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    @property
    def model(self):
        return self.lookup.model

    def list_url(self) -> str:
        return reverse("core:lookup_list", args=[self.lookup.key])


class LookupListView(LookupMixin, TemplateView):
    template_name = "core/lookup_list.html"

    def get_context_data(self, **kwargs):
        columns = self.lookup.list_display
        objects = self.model.objects.all()
        rows = [(obj, [getattr(obj, c) for c in columns]) for obj in objects]
        headers = [self.model._meta.get_field(c).verbose_name for c in columns]
        return super().get_context_data(lookup=self.lookup, rows=rows, headers=headers, **kwargs)


class LookupEditView(LookupMixin, TemplateView):
    template_name = "core/lookup_form.html"

    def get_object(self):
        pk = self.kwargs.get("pk")
        return get_object_or_404(self.model, pk=pk) if pk else None

    def get_form(self, data=None):
        form_class = modelform_factory(self.model, fields=self.lookup.fields)
        return form_class(data, instance=self.get_object())

    def get(self, request, *args, **kwargs):
        return self.render_to_response(self.context(self.get_form()))

    def post(self, request, *args, **kwargs):
        form = self.get_form(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Saved."))
            return HttpResponseRedirect(self.list_url())
        return self.render_to_response(self.context(form))

    def context(self, form):
        return self.get_context_data(lookup=self.lookup, form=form, object=form.instance)


class LookupDeleteView(LookupMixin, View):
    def post(self, request, key, pk):
        obj = get_object_or_404(self.model, pk=pk)
        try:
            obj.delete()
        except ProtectedError:
            messages.error(
                request,
                _("“%(name)s” is in use, so it can't be deleted. Untick “active” instead.")
                % {"name": obj},
            )
        else:
            messages.success(request, _("Deleted “%(name)s”.") % {"name": obj})
        return HttpResponseRedirect(self.list_url())


# -- bin ---------------------------------------------------------------------------------
class BinView(PermissionRequired, TemplateView):
    permission_required = "core.use_bin"
    template_name = "core/bin.html"

    def get_context_data(self, **kwargs):
        user = self.request.user
        sections = []
        for trashable in registry.trashables():
            if not user.has_perm(trashable.permission):
                continue
            items = trashable.model.all_objects.deleted().order_by("-deleted_at")[:200]
            sections.append((trashable, list(items)))
        return super().get_context_data(sections=sections, **kwargs)


class BinActionView(PermissionRequired, View):
    permission_required = "core.use_bin"

    def get_object(self):
        trashable = registry.get_trashable(self.kwargs["key"])
        if trashable is None:
            raise Http404
        if not self.request.user.has_perm(trashable.permission):
            raise PermissionDenied
        return get_object_or_404(trashable.model.all_objects.deleted(), pk=self.kwargs["pk"])


class RestoreView(BinActionView):
    def post(self, request, key, pk):
        obj = self.get_object()
        obj.restore()
        messages.success(request, _("Restored %(object)s.") % {"object": obj})
        return redirect("core:bin")


class PurgeView(BinActionView):
    """Delete permanently — owners only."""

    def post(self, request, key, pk):
        if not request.user.is_superuser:
            raise PermissionDenied
        obj = self.get_object()
        label = str(obj)
        try:
            obj.delete()
        except ProtectedError:
            messages.error(
                request, _("%(object)s is still referenced elsewhere.") % {"object": label}
            )
        else:
            messages.success(request, _("Deleted %(object)s permanently.") % {"object": label})
        return redirect("core:bin")


# -- files ---------------------------------------------------------------------------------
@require_GET
def protected_media(request, path: str):
    """Serve an uploaded file to signed-in users allowed to see what it belongs to."""
    permission = registry.media_permission(path)
    if permission is None or not request.user.has_perm(permission):
        raise Http404
    try:
        full_path = Path(safe_join(settings.MEDIA_ROOT, path))
    except SuspiciousFileOperation as exc:
        raise Http404 from exc
    if not full_path.is_file():
        raise Http404
    content_type, _encoding = mimetypes.guess_type(full_path.name)
    response = FileResponse(full_path.open("rb"), content_type=content_type)
    response["Cache-Control"] = "private, max-age=3600"
    return response


@login_not_required
@require_GET
def healthz(request):
    return HttpResponse("ok", content_type="text/plain")
