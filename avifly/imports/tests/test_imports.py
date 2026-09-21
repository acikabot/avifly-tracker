import io
from datetime import date, time
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from avifly.conftest import make_job
from avifly.imports import services
from avifly.imports.base import ImportFileError
from avifly.imports.importers.csv_importer import CsvImporter
from avifly.imports.models import ImportRow
from avifly.jobs.models import Job

pytestmark = pytest.mark.django_db


def parse(text: str, encoding="utf-8"):
    return CsvImporter().parse(io.BytesIO(text.encode(encoding)))


def test_reads_a_simple_csv():
    records = parse("Date,Start,End,Hectares,Serial\n2026-06-18,07:10,19:30,40.5,SN-T50-1\n")
    assert len(records) == 1
    record = records[0]
    assert record.date == date(2026, 6, 18)
    assert record.start_time == time(7, 10)
    assert record.end_time == time(19, 30)
    assert record.hectares == Decimal("40.50")
    assert record.equipment_serial == "SN-T50-1"
    assert record.external_id  # generated when the file has no id column


def test_reads_semicolons_day_first_dates_and_acres():
    records = parse("id;date;takeoff;landing;acres\nA1;18.06.2026;7:10;11:00;10\n")
    assert records[0].external_id == "A1"
    assert records[0].date == date(2026, 6, 18)
    assert records[0].hectares == Decimal("4.05")


def test_date_can_come_from_the_start_time():
    records = parse("start time,end time,area (ha)\n2026-06-19 06:55:00,2026-06-19 12:00:00,12\n")
    assert records[0].date == date(2026, 6, 19)
    assert records[0].start_time == time(6, 55)


def test_windows_cyrillic_files():
    records = parse("date,ha,notes\n2026-06-18,3,Нива кај реката\n", encoding="cp1251")
    assert records[0].raw["notes"] == "Нива кај реката"


def test_rejects_files_without_area():
    with pytest.raises(ImportFileError):
        parse("date,start\n2026-06-18,07:00\n")


def upload(content: str, name="flights.csv"):
    return SimpleUploadedFile(name, content.encode(), content_type="text/csv")


CSV = (
    "id,date,start,end,ha,serial\n"
    "F1,2026-06-18,07:10,19:30,40,SN-T50-1\n"
    "F2,2026-06-19,06:55,12:00,35.5,SN-T50-1\n"
)


def test_apply_fills_a_planned_job(owner, customer, spraying, drone):
    job = make_job(customer, spraying, days=((None, "2026-06-18"),))
    job.days.update(start_time=None, end_time=None)
    batch = services.create_batch(CsvImporter(), upload(CSV), owner)
    days = services.apply_rows(list(batch.rows.all()), job)
    job.refresh_from_db()
    assert len(days) == 2
    assert job.days.count() == 2  # the empty planned day was filled, one added
    assert job.total_hectares == Decimal("75.5")
    assert job.is_multi_day
    assert job.status == Job.Status.DONE
    first = job.days.first()
    assert first.source == "csv"
    assert first.external_id == "F1"
    assert list(first.equipment.all()) == [drone]


def test_importing_the_same_file_twice_marks_duplicates(owner, job):
    batch = services.create_batch(CsvImporter(), upload(CSV), owner)
    services.apply_rows(list(batch.rows.all()), job)
    again = services.create_batch(CsvImporter(), upload(CSV), owner)
    assert set(again.rows.values_list("status", flat=True)) == {ImportRow.Status.DUPLICATE}


def test_upload_and_apply_through_the_pages(owner_client, job):
    response = owner_client.post(reverse("imports:index"), {"importer": "csv", "file": upload(CSV)})
    assert response.status_code == 302
    batch_url = response["Location"]
    rows = list(ImportRow.objects.values_list("pk", flat=True))
    response = owner_client.post(batch_url, {"job": job.pk, "rows": rows})
    assert response.status_code == 302
    job.refresh_from_db()
    assert job.days.count() == 3


def test_bad_files_show_an_error(owner_client):
    response = owner_client.post(
        reverse("imports:index"), {"importer": "csv", "file": upload("hello\n")}
    )
    assert response.status_code == 200
    assert "No area column" in response.content.decode()
