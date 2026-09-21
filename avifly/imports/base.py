"""The importer plug-in interface.

An importer turns an uploaded file (from the DJI controller, SmartFarm, AirData, a
spreadsheet…) into :class:`ImportedRecord` objects — one per day of work. Records are
reviewed on screen and then added to a job as job days, keeping the original record.

To support a new file format, write a :class:`BaseImporter` subclass and register an
instance from any module's ``register()`` hook::

    registry.add_extension(IMPORTERS, MyImporter())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from decimal import Decimal

IMPORTERS = "imports.importers"


class ImportFileError(Exception):
    """The file can't be read by this importer (the message is shown to the user)."""


@dataclass
class ImportedRecord:
    external_id: str
    date: date
    start_time: time | None = None
    end_time: time | None = None
    hectares: Decimal | None = None
    equipment_serial: str = ""
    raw: dict = field(default_factory=dict)


class BaseImporter:
    #: Stored on imported job days as their ``source`` — keep it stable.
    key = ""
    label = ""
    description = ""
    #: File types offered in the upload dialog, e.g. ".csv,.txt".
    accept = ""
    order = 100

    def parse(self, upload) -> list[ImportedRecord]:
        raise NotImplementedError
