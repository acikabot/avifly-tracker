from __future__ import annotations

from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from avifly.core.exports import csv_response
from avifly.core.mixins import CreatedByMixin, PermissionRequired, SoftDeleteView
from avifly.core.registry import registry
from avifly.customers.forms import CustomerForm, FarmFieldForm, QuickCustomerForm, QuickFieldForm
from avifly.customers.models import Customer, FarmField

#: Extension point: callables ``(customer) -> str | None`` explaining why a customer
#: can't be deleted (e.g. the jobs module blocks deleting customers that have jobs).
CUSTOMER_DELETE_BLOCKERS = "customers.customer_delete_blockers"
#: Same for fields: ``(field) -> str | None``.
FIELD_DELETE_BLOCKERS = "customers.field_delete_blockers"


def _first_block(point: str, obj) -> str | None:
    for blocker in registry.extensions(point):
        reason = blocker(obj)
        if reason:
            return reason
    return None


class CustomerListView(PermissionRequired, ListView):
    permission_required = "customers.view_customer"
    template_name = "customers/customer_list.html"
    paginate_by = 30

    def get_queryset(self):
        qs = Customer.objects.annotate(
            field_count=Count("farm_fields", filter=Q(farm_fields__deleted_at__isnull=True))
        ).order_by("name")
        if self.request.GET.get("inactive") != "1":
            qs = qs.filter(is_active=True)
        query = self.request.GET.get("q", "").strip()
        return qs.search(query) if query else qs

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") == "csv":
            return self.export()
        return super().get(request, *args, **kwargs)

    def export(self):
        rows = (
            (
                c.name, c.company_name, c.phone, c.phone_alt, c.email, c.town, c.address,
                c.tax_number, c.special_rate_per_ha, c.notes,
            )
            for c in self.get_queryset()
        )  # fmt: skip
        header = [
            "Name", "Company", "Phone", "Other phone", "E-mail", "Town", "Address",
            "Tax number", "Special rate per ha", "Notes",
        ]  # fmt: skip
        return csv_response("customers", header, rows)


class CustomerDetailView(PermissionRequired, DetailView):
    permission_required = "customers.view_customer"
    model = Customer
    template_name = "customers/customer_detail.html"

    def get_context_data(self, **kwargs):
        fields = list(self.object.farm_fields.all())
        points = [f.as_map_point(f"{f.hectares or '?'} ha") for f in fields if f.has_location]
        return super().get_context_data(farm_fields=fields, map_points=points, **kwargs)


class CustomerCreateView(PermissionRequired, CreatedByMixin, CreateView):
    permission_required = "customers.add_customer"
    model = Customer
    form_class = CustomerForm
    template_name = "customers/customer_form.html"

    def form_valid(self, form):
        messages.success(self.request, _("Customer saved."))
        return super().form_valid(form)


class CustomerUpdateView(PermissionRequired, UpdateView):
    permission_required = "customers.change_customer"
    model = Customer
    form_class = CustomerForm
    template_name = "customers/customer_form.html"

    def form_valid(self, form):
        messages.success(self.request, _("Customer saved."))
        return super().form_valid(form)


class CustomerDeleteView(SoftDeleteView):
    permission_required = "customers.delete_customer"
    model = Customer

    def blocked_reason(self, obj):
        return _first_block(CUSTOMER_DELETE_BLOCKERS, obj)

    def get_success_url(self):
        return reverse("customers:list")


# -- fields --------------------------------------------------------------------------------
class FarmFieldMixin(PermissionRequired):
    permission_required = "customers.change_customer"
    model = FarmField
    form_class = FarmFieldForm
    template_name = "customers/field_form.html"

    def get_success_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):
        messages.success(self.request, _("Field saved."))
        return super().form_valid(form)


class FarmFieldCreateView(FarmFieldMixin, CreatedByMixin, CreateView):
    def dispatch(self, request, *args, **kwargs):
        self.customer = get_object_or_404(Customer, pk=kwargs["customer_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return {"name": _("Field %(number)s") % {"number": self.customer.farm_fields.count() + 1}}

    def form_valid(self, form):
        form.instance.customer = self.customer
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        return super().get_context_data(customer=self.customer, **kwargs)


class FarmFieldUpdateView(FarmFieldMixin, UpdateView):
    def get_context_data(self, **kwargs):
        return super().get_context_data(customer=self.object.customer, **kwargs)


class FarmFieldDeleteView(SoftDeleteView):
    permission_required = "customers.change_customer"
    model = FarmField

    def blocked_reason(self, obj):
        return _first_block(FIELD_DELETE_BLOCKERS, obj)

    def get_success_url(self):
        return reverse("customers:detail", args=[self.get_object().customer_id])


# -- JSON endpoints used by the job form ------------------------------------------------------
class CustomerSearchView(PermissionRequired, View):
    permission_required = "customers.view_customer"

    def get(self, request):
        query = request.GET.get("q", "").strip()
        qs = Customer.objects.filter(is_active=True)
        qs = qs.search(query) if query else qs
        results = [
            {"value": c.pk, "text": f"{c.name} · {c.town}" if c.town else c.name} for c in qs[:30]
        ]
        return JsonResponse({"results": results})


class CustomerJobDataView(PermissionRequired, View):
    """A customer's special rate and fields, for filling in the job form."""

    permission_required = "customers.view_customer"

    def get(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk)
        fields = [
            {"value": f.pk, "text": f.name, "hectares": str(f.hectares or "")}
            for f in customer.farm_fields.filter(is_active=True)
        ]
        rate = customer.special_rate_per_ha
        return JsonResponse(
            {"special_rate": str(rate) if rate is not None else None, "fields": fields}
        )


class QuickAddCustomerView(PermissionRequired, View):
    permission_required = "customers.add_customer"

    def post(self, request):
        form = QuickCustomerForm(request.POST)
        if not form.is_valid():
            return JsonResponse({"errors": form.errors}, status=400)
        form.instance.created_by = request.user
        customer = form.save()
        return JsonResponse({"value": customer.pk, "text": customer.name}, status=201)


class QuickAddFieldView(PermissionRequired, View):
    permission_required = "customers.change_customer"

    def post(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk)
        form = QuickFieldForm(request.POST)
        if not form.is_valid():
            return JsonResponse({"errors": form.errors}, status=400)
        form.instance.customer = customer
        form.instance.created_by = request.user
        field = form.save()
        return JsonResponse(
            {"value": field.pk, "text": field.name, "hectares": str(field.hectares or "")},
            status=201,
        )
