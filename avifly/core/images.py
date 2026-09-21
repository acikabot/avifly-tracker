"""Uploaded photo handling: shrink phone photos before they fill the SD card."""

from __future__ import annotations

import io
from pathlib import PurePath

from django.core.files.uploadedfile import InMemoryUploadedFile, UploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_PIXELS = 1600
JPEG_QUALITY = 82
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".gif"}


def is_image_name(name: str) -> bool:
    return PurePath(name).suffix.lower() in IMAGE_EXTENSIONS


def shrink_image(upload: UploadedFile) -> UploadedFile:
    """Return a resized JPEG copy of an uploaded image (or the upload unchanged).

    Keeps orientation from the phone's EXIF data and strips the rest of the metadata
    (including GPS), which also keeps customer locations out of shared photos.
    """
    try:
        upload.seek(0)
        image = Image.open(upload)
        image = ImageOps.exif_transpose(image)
    except (UnidentifiedImageError, OSError):
        upload.seek(0)
        return upload

    image.thumbnail((MAX_PIXELS, MAX_PIXELS))
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    buffer.seek(0)
    name = str(PurePath(upload.name).with_suffix(".jpg").name)
    return InMemoryUploadedFile(buffer, "file", name, "image/jpeg", buffer.getbuffer().nbytes, None)
