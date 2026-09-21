from __future__ import annotations

from django.views.generic import TemplateView

from avifly.analytics import selectors
from avifly.analytics.forms import AnalyticsFilterForm
from avifly.core.mixins import PermissionRequired
from avifly.equipment.models import EquipmentType


class AnalyticsView(PermissionRequired, TemplateView):
    permission_required = "analytics.view_analytics"
    template_name = "analytics/analytics.html"

    def get_context_data(self, **kwargs):
        form = AnalyticsFilterForm(self.request.GET or None)
        filters = selectors.Filters(
            period=form.get_period(),
            operation=form.value("operation"),
            crop=form.value("crop"),
            customer=form.value("customer"),
            equipment=form.value("equipment"),
        )
        equipment_type = (
            form.value("equipment_type")
            or EquipmentType.objects.filter(show_on_jobs=True, is_active=True).first()
        )
        charts = selectors.all_charts(filters, equipment_type)
        return super().get_context_data(
            period_form=form,
            period=filters.period,
            filters=filters,
            kpis=selectors.kpis(filters),
            charts=charts,
            chart_data={chart.key: chart.as_json() for chart in charts},
            map_points=selectors.field_points(filters),
            **kwargs,
        )
