from __future__ import annotations

from itertools import groupby

from django.contrib import messages
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from avifly.core.mixins import CreatedByMixin, PermissionRequired, SoftDeleteView
from avifly.core.registry import registry
from avifly.equipment.forms import EquipmentForm
from avifly.equipment.models import Equipment

#: Extension point: callables ``(equipment) -> str | None`` that block deletion.
DELETE_BLOCKERS = "equipment.delete_blockers"


class EquipmentListView(PermissionRequired, ListView):
    permission_required = "equipment.view_equipment"
    template_name = "equipment/equipment_list.html"

    def get_queryset(self):
        qs = Equipment.objects.select_related("equipment_type")
        if self.request.GET.get("all") != "1":
            qs = qs.filter(status__in=Equipment.USABLE)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["groups"] = [
            (kind, list(items))
            for kind, items in groupby(context["object_list"], key=lambda e: e.equipment_type)
        ]
        return context


class EquipmentDetailView(PermissionRequired, DetailView):
    permission_required = "equipment.view_equipment"
    model = Equipment
    template_name = "equipment/equipment_detail.html"


class EquipmentFormMixin(PermissionRequired):
    model = Equipment
    form_class = EquipmentForm
    template_name = "equipment/equipment_form.html"

    def form_valid(self, form):
        messages.success(self.request, _("Equipment saved."))
        return super().form_valid(form)


class EquipmentCreateView(EquipmentFormMixin, CreatedByMixin, CreateView):
    permission_required = "equipment.add_equipment"

    def get_initial(self):
        return {"equipment_type": self.request.GET.get("type")}


class EquipmentUpdateView(EquipmentFormMixin, UpdateView):
    permission_required = "equipment.change_equipment"


class EquipmentDeleteView(SoftDeleteView):
    permission_required = "equipment.delete_equipment"
    model = Equipment

    def blocked_reason(self, obj):
        for blocker in registry.extensions(DELETE_BLOCKERS):
            reason = blocker(obj)
            if reason:
                return reason
        return None

    def get_success_url(self):
        return reverse("equipment:list")
