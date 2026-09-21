from __future__ import annotations

from django.contrib import messages
from django.core.files.uploadedfile import UploadedFile
from django.db.models import Sum
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from avifly.core.exports import csv_response
from avifly.core.forms import PeriodForm
from avifly.core.images import is_image_name, shrink_image
from avifly.core.mixins import PermissionRequired, SoftDeleteView
from avifly.core.periods import resolve_period
from avifly.money import selectors
from avifly.money.forms import CostFilterForm, CostForm
from avifly.money.models import Cost


class MoneyBookView(PermissionRequired, TemplateView):
    permission_required = ("money.view_payment", "money.view_cost")
    template_name = "money/book.html"

    def get(self, request, *args, **kwargs):
        self.period_form = PeriodForm(request.GET or None, default="this_month")
        self.period = self.period_form.get_period()
        if request.GET.get("export") == "csv":
            return self.export()
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        opening, rows = selectors.money_book(self.period)
        total_in = sum((r.amount for r in rows if r.kind == "in"), selectors.ZERO)
        total_out = sum((r.amount for r in rows if r.kind == "out"), selectors.ZERO)
        return super().get_context_data(
            period_form=self.period_form,
            period=self.period,
            opening=opening,
            rows=list(reversed(rows)),
            total_in=total_in,
            total_out=total_out,
            closing=opening + total_in - total_out,
            month=selectors.summary(resolve_period("this_month")),
            season=selectors.summary(resolve_period("this_season")),
            **kwargs,
        )

    def export(self):
        opening, rows = selectors.money_book(self.period)
        header = ["Date", "In/Out", "What", "Details", "Amount", "Balance"]
        lines = [["", "", "Opening balance", "", "", opening]]
        lines += [[r.date, r.kind, r.label, r.detail, r.signed, r.balance] for r in rows]
        return csv_response("money-book", header, lines)


class CostListView(PermissionRequired, ListView):
    permission_required = "money.view_cost"
    template_name = "money/cost_list.html"
    paginate_by = 50

    def get_queryset(self):
        self.period_form = PeriodForm(self.request.GET or None, default="this_season")
        self.period = self.period_form.get_period()
        self.filters = CostFilterForm(self.request.GET or None)
        qs = Cost.objects.visible_to(self.request.user).select_related(
            "category", "equipment", "job"
        )
        if self.period.start:
            qs = qs.filter(date__gte=self.period.start)
        if self.period.end:
            qs = qs.filter(date__lte=self.period.end)
        if self.filters.is_valid():
            if self.filters.cleaned_data["category"]:
                qs = qs.filter(category=self.filters.cleaned_data["category"])
            if self.filters.cleaned_data["equipment"]:
                qs = qs.filter(equipment=self.filters.cleaned_data["equipment"])
        return qs

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") == "csv":
            header = ["Date", "Category", "What for", "Equipment", "Job", "Amount", "Notes"]
            rows = [
                [
                    c.date,
                    c.category,
                    c.description,
                    c.equipment or "",
                    c.job.number if c.job else "",
                    c.amount,
                    c.notes,
                ]
                for c in self.get_queryset()
            ]
            return csv_response("costs", header, rows)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        qs = self.object_list
        by_category = qs.values("category__name").annotate(total=Sum("amount")).order_by("-total")
        return super().get_context_data(
            period_form=self.period_form,
            period=self.period,
            filters=self.filters,
            total=qs.aggregate(s=Sum("amount"))["s"] or 0,
            by_category=by_category,
            **kwargs,
        )


class CostFormMixin(PermissionRequired):
    model = Cost
    form_class = CostForm
    template_name = "money/cost_form.html"

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}

    def form_valid(self, form):
        receipt = form.cleaned_data.get("receipt")
        if isinstance(receipt, UploadedFile) and is_image_name(receipt.name):
            form.instance.receipt = shrink_image(receipt)
        messages.success(self.request, _("Cost saved."))
        return super().form_valid(form)

    def get_success_url(self):
        return self.request.GET.get("next") or reverse("money:costs")


class CostCreateView(CostFormMixin, CreateView):
    permission_required = "money.add_cost"

    def get_initial(self):
        return {
            key: self.request.GET.get(key)
            for key in ("equipment", "job", "category")
            if self.request.GET.get(key)
        }

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class CostUpdateView(CostFormMixin, UpdateView):
    permission_required = "money.change_cost"

    def get_queryset(self):
        return Cost.objects.visible_to(self.request.user, "change")


class CostDeleteView(SoftDeleteView):
    permission_required = "money.delete_cost"
    model = Cost

    def get_queryset(self):
        return Cost.objects.visible_to(self.request.user, "delete")

    def get_success_url(self):
        return reverse("money:costs")
