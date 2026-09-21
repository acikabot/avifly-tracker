"""Generic CSV/spreadsheet importer.

Reads any CSV with a header row. Column names are matched loosely (case, spaces and a
few common names), so exports from different apps — or a sheet typed up by hand — work
without changes. Area can be given in hectares, acres or mu.
"""

from __future__ import annotations

import csv
import hashlib
import io
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation

from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from avifly.imports.base import BaseImporter, ImportedRecord, ImportFileError

COLUMNS = {
    "id": ("id", "record id", "flight id", "external id", "task id", "operation id"),
    "date": ("date", "day", "flight date", "operation date"),
    "start": ("start", "start time", "takeoff", "takeoff time", "begin", "from"),
    "end": ("end", "end time", "landing", "landing time", "finish", "to"),
    "hectares": ("hectares", "ha", "area", "area ha", "area (ha)", "sprayed area", "operated area"),
    "acres": ("acres", "area (acres)", "area acres", "ac"),
    "mu": ("mu", "area (mu)", "area mu"),
    "serial": ("serial", "serial number", "sn", "drone", "drone sn", "drone serial", "aircraft sn"),
}
ACRE_HA = Decimal("0.40468564224")
MU_HA = Decimal("0.0666666667")

DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d.%m.%y", "%Y/%m/%d")
TIME_FORMATS = ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M:%S %p")


def _clean(name: str) -> str:
    return " ".join(name.lower().replace("_", " ").replace("﻿", "").split())


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1251", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ImportFileError(_("The file isn't readable text."))


def parse_date(value: str) -> date | None:
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def parse_time(value: str) -> tuple[date | None, time | None]:
    """A clock time, or a full date+time (then the date is returned too)."""
    value = value.strip().replace("T", " ")
    if not value:
        return None, None
    if " " in value and parse_date(value.split(" ", 1)[0]):
        day_part, time_part = value.split(" ", 1)
        return parse_date(day_part), parse_time(time_part)[1]
    for fmt in TIME_FORMATS:
        try:
            return None, datetime.strptime(value.upper(), fmt).time().replace(second=0)
        except ValueError:
            continue
    return None, None


def parse_decimal(value: str) -> Decimal | None:
    value = value.strip().replace(" ", "")
    if not value:
        return None
    if "," in value and "." not in value:
        value = value.replace(",", ".")
    try:
        return Decimal(value.replace(",", ""))
    except InvalidOperation:
        return None


class CsvImporter(BaseImporter):
    key = "csv"
    label = gettext_lazy("CSV / spreadsheet")
    description = gettext_lazy(
        "A CSV file with a header row: date, start, end, hectares (or acres / mu), and "
        "optionally a record id and the drone's serial number. One row per day of work."
    )
    accept = ".csv,.txt"
    order = 100

    def parse(self, upload) -> list[ImportedRecord]:
        text = _decode(upload.read())
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        if not reader.fieldnames:
            raise ImportFileError(_("The file is empty."))
        columns = self._map_columns(reader.fieldnames)
        if "hectares" not in columns and "acres" not in columns and "mu" not in columns:
            raise ImportFileError(_("No area column found (hectares, acres or mu)."))

        records = []
        for number, row in enumerate(reader, start=2):
            record = self._record(row, columns, number)
            if record is not None:
                records.append(record)
        if not records:
            raise ImportFileError(_("No usable rows found."))
        return records

    @staticmethod
    def _map_columns(fieldnames) -> dict[str, str]:
        found = {}
        cleaned = {_clean(name): name for name in fieldnames if name}
        for key, names in COLUMNS.items():
            for name in names:
                if name in cleaned:
                    found[key] = cleaned[name]
                    break
        return found

    def _record(self, row: dict, columns: dict, number: int) -> ImportedRecord | None:
        def get(key):
            return (row.get(columns[key]) or "").strip() if key in columns else ""

        start_date, start = parse_time(get("start"))
        _end_date, end = parse_time(get("end"))
        day = parse_date(get("date")) if get("date") else start_date
        if day is None:
            if any((value or "").strip() for value in row.values()):
                raise ImportFileError(_("Row %(n)d has no readable date.") % {"n": number})
            return None

        hectares = parse_decimal(get("hectares"))
        if hectares is None and get("acres"):
            hectares = (parse_decimal(get("acres")) or 0) * ACRE_HA
        if hectares is None and get("mu"):
            hectares = (parse_decimal(get("mu")) or 0) * MU_HA
        if hectares is not None:
            hectares = hectares.quantize(Decimal("0.01"))

        raw = {key: value for key, value in row.items() if key}
        external_id = (
            get("id")
            or hashlib.sha1(repr(sorted(raw.items())).encode(), usedforsecurity=False).hexdigest()[
                :16
            ]
        )
        return ImportedRecord(
            external_id=external_id,
            date=day,
            start_time=start,
            end_time=end,
            hectares=hectares,
            equipment_serial=get("serial"),
            raw=raw,
        )
