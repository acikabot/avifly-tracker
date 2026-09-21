from __future__ import annotations

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views.generic import TemplateView

from avifly.core.mixins import PermissionRequired
from avifly.imports import services
from avifly.imports.base import ImportFileError
from avifly.imports.forms import ApplyForm, UploadForm
from avifly.imports.models import ImportBatch, ImportRow


class ImportIndexView(PermissionRequired, TemplateView):
    permission_required = "imports.add_importbatch"
    template_name = "imports/index.html"

    def get_context_data(self, **kwargs):
        kwargs.setdefault("form", UploadForm())
        return super().get_context_data(
            importers=services.importers(),
            batches=ImportBatch.objects.select_related("created_by")[:30],
            **kwargs,
        )

    def post(self, request):
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            importer = services.get_importer(form.cleaned_data["importer"])
            try:
                batch = services.create_batch(importer, form.cleaned_data["file"], request.user)
            except ImportFileError as exc:
                form.add_error("file", str(exc))
            else:
                messages.success(
                    request,
                    _("Read %(n)d record(s). Choose where they go.") % {"n": batch.rows.count()},
                )
                return redirect(batch)
        return self.render_to_response(self.get_context_data(form=form))


class BatchView(PermissionRequired, TemplateView):
    permission_required = "imports.add_importbatch"
    template_name = "imports/batch.html"

    def get_batch(self) -> ImportBatch:
        return get_object_or_404(ImportBatch, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        batch = self.get_batch()
        kwargs.setdefault("form", ApplyForm(batch=batch, user=self.request.user))
        rows = batch.rows.select_related("job_day__job__customer")
        return super().get_context_data(batch=batch, rows=rows, **kwargs)

    def post(self, request, pk):
        batch = self.get_batch()
        form = ApplyForm(request.POST, batch=batch, user=request.user)
        if not form.is_valid():
            messages.error(request, _("Pick a job and at least one record."))
            return self.render_to_response(self.get_context_data(form=form))
        rows = list(
            batch.rows.filter(pk__in=form.cleaned_data["rows"], status=ImportRow.Status.NEW)
        )
        job = form.cleaned_data["job"]
        days = services.apply_rows(rows, job)
        messages.success(
            request, _("Added %(n)d day(s) to job %(job)s.") % {"n": len(days), "job": job.number}
        )
        return redirect(job)
