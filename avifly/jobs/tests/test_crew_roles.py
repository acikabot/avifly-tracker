"""Crew is recorded per role: one dropdown per role, several people allowed in each."""

import pytest
from django.urls import reverse

from avifly.conftest import make_user
from avifly.jobs import services
from avifly.jobs.forms import JobDayForm
from avifly.jobs.models import CrewRole, Job, JobDayCrew
from avifly.jobs.tests.test_job_form import job_post

pytestmark = pytest.mark.django_db


def test_the_day_form_has_one_dropdown_per_role(pilot_role, ground_role):
    form = JobDayForm()
    assert form.crew_field_names == [f"crew_{pilot_role.pk}", f"crew_{ground_role.pk}"]
    assert [field.label for field in form.crew_fields] == ["Pilot", "Ground crew"]


def test_several_people_can_share_a_role(
    owner_client, owner, customer, spraying, pilot_role, ground_role
):
    second_pilot = make_user("pilot2")
    helper = make_user("helper")
    day = {
        "date": "2026-06-01",
        "hectares": "12",
        f"crew_{pilot_role.pk}": [owner.pk, second_pilot.pk],
        f"crew_{ground_role.pk}": [helper.pk],
    }
    response = owner_client.post(reverse("jobs:add"), job_post(customer, spraying, [day]))
    assert response.status_code == 302, response.content.decode()[:1500]

    job_day = Job.objects.get().days.get()
    by_role = {role.name: people for role, people in job_day.crew_by_role()}
    assert by_role["Pilot"] == [owner, second_pilot]
    assert by_role["Ground crew"] == [helper]
    # The flat relation still answers "who worked that day", for the own-jobs rule.
    assert set(job_day.crew.all()) == {owner, second_pilot, helper}


def test_a_role_can_be_limited_to_one_person(owner, customer, spraying, pilot_role):
    pilot_role.allow_multiple = False
    pilot_role.save()
    form = JobDayForm()
    field = form.fields[f"crew_{pilot_role.pk}"]
    assert not getattr(field, "widget", None).allow_multiple_selected


def test_continuing_to_another_day_keeps_the_roles(job, owner, pilot_role, ground_role):
    helper = make_user("helper2")
    services.set_day_crew(job.days.get(), [(owner, pilot_role), (helper, ground_role)])

    day = services.start_next_day(job, owner)

    assert {(link.user, link.role) for link in day.crew_links.all()} == {
        (owner, pilot_role),
        (helper, ground_role),
    }


def test_starting_work_puts_you_in_the_first_role(job, owner, pilot_role):
    services.start_day(job.days.get(), owner)
    link = JobDayCrew.objects.get(job_day=job.days.get())
    assert (link.user, link.role) == (owner, pilot_role)


def test_repeating_a_job_keeps_the_roles(job, owner, ground_role):
    services.set_day_crew(job.days.get(), [(owner, ground_role)])
    copy = services.duplicate_job(job, owner)
    link = copy.days.get().crew_links.get()
    assert (link.user, link.role) == (owner, ground_role)


def test_a_switched_off_role_leaves_new_forms_but_keeps_its_people(job, owner, ground_role):
    services.set_day_crew(job.days.get(), [(owner, ground_role)])
    ground_role.is_active = False
    ground_role.save()

    assert f"crew_{ground_role.pk}" not in JobDayForm().crew_field_names
    # The day itself still shows who worked, so nothing disappears from history.
    assert [role.name for role, _people in job.days.get().crew_by_role()] == ["Ground crew"]


def test_a_role_in_use_cannot_be_deleted(job, owner, pilot_role):
    from django.db.models import ProtectedError

    services.set_day_crew(job.days.get(), [(owner, pilot_role)])
    with pytest.raises(ProtectedError):
        pilot_role.delete()


def test_the_roles_are_an_editable_list_in_settings(owner_client):
    response = owner_client.get(reverse("core:settings"))
    assert "Crew roles" in response.content.decode()
    assert CrewRole.objects.filter(is_active=True).count() == 2
