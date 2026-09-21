from datetime import timedelta

from django import forms
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from avifly.core.validators import validate_upload
from avifly.imports.services import importers
from avifly.jobs.models import Job


class UploadForm(forms.Form):
    importer = forms.ChoiceField(label=_("File type"))
    file = forms.FileField(label=_("File"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["importer"].choices = [(i.key, i.label) for i in importers()]

    def clean_file(self):
        upload = self.cleaned_data["file"]
        validate_upload(upload, extensions=(".csv", ".txt", ".kml", ".xml", ".json", ".xlsx"))
        return upload


class ApplyForm(forms.Form):
    job = forms.ModelChoiceField(
        label=_("Add to job"), queryset=Job.objects.none(), empty_label=_("Choose a job…")
    )
    rows = forms.MultipleChoiceField(choices=[], widget=forms.MultipleHiddenInput)

    def __init__(self, *args, batch, user, **kwargs):
        super().__init__(*args, **kwargs)
        recent = timezone.localdate() - timedelta(days=120)
        self.fields["job"].queryset = (
            Job.objects.visible_to(user, "change")
            .filter(
                Q(start_date__gte=recent)
                | Q(status__in=[Job.Status.PLANNED, Job.Status.IN_PROGRESS])
            )
            .select_related("customer")
            .order_by("-start_date")
        )
        self.fields["job"].widget.attrs["data-tom"] = ""
        self.fields["rows"].choices = [(str(r.pk), r.pk) for r in batch.rows.all()]
