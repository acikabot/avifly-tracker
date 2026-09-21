from __future__ import annotations

from pathlib import PurePath

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

RECEIPT_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".gif", ".pdf")


def validate_upload(upload, extensions=RECEIPT_EXTENSIONS) -> None:
    """Reject files of the wrong type or that are too large."""
    if not upload:
        return
    suffix = PurePath(upload.name).suffix.lower()
    if suffix not in extensions:
        raise ValidationError(
            _("Please upload a photo or PDF (%(types)s).") % {"types": ", ".join(extensions)}
        )
    limit = settings.AVIFLY_MAX_UPLOAD_MB * 1024 * 1024
    if upload.size and upload.size > limit:
        raise ValidationError(
            _("The file is too big (max %(mb)d MB).") % {"mb": settings.AVIFLY_MAX_UPLOAD_MB}
        )
