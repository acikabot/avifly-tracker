from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import DetailView, ListView

from avifly.core.exports import csv_response
from avifly.core.images import is_image_name, shrink_image
from avifly.core.mixins import PermissionRequired, SoftDeleteView
from avifly.jobs import services
from avifly.jobs.forms import FinishDayForm, JobFilterForm, JobFormBundle, JobPhotoForm
from avifly.jobs.models import Job, JobDay, JobPhoto


def job_queryset(user, action: str = "view"):
    days = JobDay.objects.prefetch_related("farm_fields", "equipment", "crew")
    return (
        Job.objects.visible_to(user, action)
        .select_related("customer", "operation_type", "crop")
        .prefetch_related(Prefetch("days", queryset=days))
    )


class JobListView(PermissionRequired, ListView):
    permission_required = "jobs.view_job"
    template_name = "jobs/job_list.html"
    paginate_by = 30

    def get_queryset(self):
        self.filters = JobFilterForm(self.request.GET or None)
        return self.filters.filter(job_queryset(self.request.user))

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") == "csv":
            return self.export()
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return super().get_context_data(filters=self.filters, **kwargs)

    def export(self):
        header = [
            "Job", "Status", "First day", "Last day", "Days", "Customer", "Operation", "Crop",
            "Fields", "Material", "Hectares", "Work minutes", "Rate per ha", "Hectares x rate",
            "Extra charges", "Total", "Notes",
        ]  # fmt: skip
        rows = []
        for job in self.get_queryset():
            fields = sorted({f.name for day in job.days.all() for f in day.farm_fields.all()})
            rows.append(
                [
                    job.number, job.get_status_display(), job.start_date, job.end_date,
                    job.day_count, job.customer.name, job.operation_type.name,
                    job.crop.name if job.crop else "", ", ".join(fields), job.material_note,
                    job.total_hectares, job.work_minutes, job.rate_per_ha, job.base_amount,
                    job.extras_amount, job.total_amount, job.notes,
                ]
            )  # fmt: skip
        return csv_response("jobs", header, rows)


class JobDetailView(PermissionRequired, DetailView):
    permission_required = "jobs.view_job"
    template_name = "jobs/job_detail.html"

    def get_queryset(self):
        return job_queryset(self.request.user).prefetch_related("extra_charges", "photos")

    def get_context_data(self, **kwargs):
        user = self.request.user
        job = self.object
        can_edit = (
            user.has_perm("jobs.change_job")
            and Job.objects.visible_to(user, "change").filter(pk=job.pk).exists()
        )
        return super().get_context_data(
            can_edit=can_edit,
            finish_form=FinishDayForm(),
            photo_form=JobPhotoForm(),
            **kwargs,
        )


class JobEditView(PermissionRequired, View):
    """Create or edit a job. Also handles the "add day" / "add charge" buttons."""

    template_name = "jobs/job_form.html"

    def get_permission_required(self):
        return ["jobs.change_job"] if "pk" in self.kwargs else ["jobs.add_job"]

    def get_job(self) -> Job | None:
        if "pk" not in self.kwargs:
            return None
        return get_object_or_404(job_queryset(self.request.user, "change"), pk=self.kwargs["pk"])

    def initial(self) -> dict:
        customer = self.request.GET.get("customer")
        return {"job": {"customer": customer}} if customer else {}

    def get(self, request, *args, **kwargs):
        bundle = JobFormBundle(request, self.get_job(), initial=self.initial())
        return self.render(bundle)

    def post(self, request, *args, **kwargs):
        job = self.get_job()
        action = request.POST.get("action", "save")
        if action == "add_day":
            data = JobFormBundle.with_extra_day(request.POST)
            return self.render(JobFormBundle(request, job, data, request.FILES).without_errors())
        if action == "add_charge":
            data = JobFormBundle.with_extra_charge(request.POST)
            return self.render(JobFormBundle(request, job, data, request.FILES).without_errors())

        bundle = JobFormBundle(request, job, request.POST, request.FILES)
        if bundle.is_valid():
            saved = bundle.save()
            messages.success(request, _("Job %(number)s saved.") % {"number": saved.number})
            return redirect(saved)
        messages.error(request, _("Please check the highlighted fields."))
        return self.render(bundle)

    def render(self, bundle: JobFormBundle):
        return render(self.request, self.template_name, {"bundle": bundle, "job": bundle.job})


class JobDeleteView(SoftDeleteView):
    permission_required = "jobs.delete_job"
    model = Job

    def get_queryset(self):
        return Job.objects.visible_to(self.request.user, "delete")

    def get_success_url(self):
        return reverse("jobs:list")


class JobActionView(PermissionRequired, View):
    """Base for the one-tap buttons on the job page (POST only)."""

    permission_required = "jobs.change_job"

    def get_job(self) -> Job:
        return get_object_or_404(job_queryset(self.request.user, "change"), pk=self.kwargs["pk"])

    def get_day(self, job: Job) -> JobDay:
        return get_object_or_404(job.days.all(), pk=self.kwargs["day_pk"])


class StartDayView(JobActionView):
    def post(self, request, pk, day_pk):
        job = self.get_job()
        day = services.start_day(self.get_day(job), request.user)
        messages.success(
            request, _("Started at %(time)s.") % {"time": day.start_time.strftime("%H:%M")}
        )
        return redirect(job)


class FinishDayView(JobActionView):
    def post(self, request, pk, day_pk):
        job = self.get_job()
        form = FinishDayForm(request.POST)
        if not form.is_valid():
            messages.error(request, _("Enter a valid number of hectares."))
            return redirect(job)
        day = services.finish_day(self.get_day(job), form.cleaned_data["hectares"])
        messages.success(
            request, _("Finished at %(time)s.") % {"time": day.end_time.strftime("%H:%M")}
        )
        return redirect(job)


class NextDayView(JobActionView):
    def post(self, request, pk):
        job = self.get_job()
        services.start_next_day(job, request.user)
        messages.success(request, _("New day started. Pick today's field on the job."))
        return redirect(job)


class DuplicateJobView(PermissionRequired, View):
    permission_required = "jobs.add_job"

    def post(self, request, pk):
        job = get_object_or_404(job_queryset(request.user), pk=pk)
        copy = services.duplicate_job(job, request.user)
        messages.success(
            request,
            _("Planned job %(number)s created — check the details.") % {"number": copy.number},
        )
        return redirect("jobs:edit", pk=copy.pk)


class PhotoUploadView(JobActionView):
    def post(self, request, pk):
        job = self.get_job()
        added = 0
        for upload in request.FILES.getlist("photos"):
            if not is_image_name(upload.name):
                messages.error(request, _("%(name)s isn't a photo.") % {"name": upload.name})
                continue
            JobPhoto.objects.create(job=job, image=shrink_image(upload), created_by=request.user)
            added += 1
        if added:
            messages.success(request, _("%(count)d photo(s) added.") % {"count": added})
        return HttpResponseRedirect(job.get_absolute_url() + "#photos")


class PhotoDeleteView(JobActionView):
    def post(self, request, pk, photo_pk):
        job = self.get_job()
        photo = get_object_or_404(job.photos.all(), pk=photo_pk)
        if not request.user.has_perm("jobs.delete_job"):
            raise PermissionDenied
        photo.image.delete(save=False)
        photo.delete()
        messages.success(request, _("Photo deleted."))
        return HttpResponseRedirect(job.get_absolute_url() + "#photos")
