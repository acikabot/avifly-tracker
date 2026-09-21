"""View mixins shared by modules."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Model
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from django.views.generic import TemplateView


class PermissionRequired(PermissionRequiredMixin):
    """Permission check that answers 403 instead of redirecting a signed-in user."""

    raise_exception = True


class CreatedByMixin:
    """Stamp ``created_by`` on objects created through a ModelForm view."""

    def form_valid(self, form):
        if form.instance.pk is None and hasattr(form.instance, "created_by_id"):
            form.instance.created_by = self.request.user
        return super().form_valid(form)


class SoftDeleteView(PermissionRequired, TemplateView):
    """Confirm page (GET) + move to bin (POST) for a soft-deletable object."""

    model: type[Model]
    template_name = "core/confirm_delete.html"
    success_url: str = "/"

    def get_queryset(self):
        return self.model.objects.all()

    def get_object(self):
        if not hasattr(self, "_object"):
            self._object = get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
        return self._object

    def blocked_reason(self, obj) -> str | None:
        """Return a message explaining why ``obj`` can't be deleted, or ``None``."""
        return None

    def get_success_url(self) -> str:
        return self.success_url

    def get_context_data(self, **kwargs):
        obj = self.get_object()
        return super().get_context_data(
            object=obj,
            blocked_reason=self.blocked_reason(obj),
            cancel_url=obj.get_absolute_url() if hasattr(obj, "get_absolute_url") else "/",
            **kwargs,
        )

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        reason = self.blocked_reason(obj)
        if reason:
            messages.error(request, reason)
            return self.get(request, *args, **kwargs)
        obj.soft_delete(request.user)
        messages.success(
            request,
            _("%(object)s moved to the bin. You can restore it from Settings → Bin.")
            % {"object": obj},
        )
        return HttpResponseRedirect(self.get_success_url())
