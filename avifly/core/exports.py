"""CSV exports that open cleanly in Excel (UTF-8 with BOM, so Cyrillic survives)."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence

from django.http import HttpResponse
from django.utils import timezone


def csv_response(filename: str, header: Sequence[str], rows: Iterable[Sequence]) -> HttpResponse:
    stamp = timezone.localdate().isoformat()
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}-{stamp}.csv"'
    response.write("﻿")
    writer = csv.writer(response)
    writer.writerow(header)
    for row in rows:
        writer.writerow(["" if value is None else value for value in row])
    return response
