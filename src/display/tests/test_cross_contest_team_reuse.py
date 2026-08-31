"""
Regression test for REST API findings #9 and #10 (2026-08-28 review): both self-registration
(contestant_self_registration) and schedule_contestants accepted a client-supplied ContestTeam id
with no validation that it actually belongs to the target contest - a pilot/organiser could pull
another contest's team registration (and its tracker_device_id/air_speed) into an unrelated task.
"""

import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm

from display.contestant_scheduling.schedule_contestants import schedule_and_create_contestants
from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Aeroplane, Contest, ContestTeam, Contestant, Crew, MyUser, NavigationTask, Person, Route, Team
from utilities.mock_utilities import TraccarMock


def _mock_traccar():
    return TraccarMock


@patch("display.models.contestant.get_traccar_instance", side_effect=_mock_traccar)
@patch("display.signals.get_traccar_instance", side_effect=_mock_traccar)
class TestCrossContestTeamReuse(TestCase):
    @patch("display.models.contestant.get_traccar_instance", side_effect=_mock_traccar)
    @patch("display.signals.get_traccar_instance", side_effect=_mock_traccar)
    def setUp(self, *args):
        now = datetime.datetime.now(datetime.timezone.utc)

        self.own_contest = Contest.objects.create(
            name="Own Contest", is_public=True, start_time=now, finish_time=now + datetime.timedelta(days=1), location="60,11"
        )
        self.foreign_contest = Contest.objects.create(
            name="Foreign Contest", is_public=True, start_time=now, finish_time=now + datetime.timedelta(days=1), location="60,11"
        )

        self.pilot_person = Person.objects.create(first_name="Cross", last_name="Pilot", email="cross-pilot@example.com")
        self.pilot_user = MyUser.objects.create(email=self.pilot_person.email)
        self.pilot_team = Team.objects.create(
            crew=Crew.objects.create(member1=self.pilot_person), aeroplane=Aeroplane.objects.create(registration="LN-XCT")
        )
        # This ContestTeam belongs to the FOREIGN contest, with a real tracker id.
        self.foreign_contest_team = ContestTeam.objects.create(
            contest=self.foreign_contest, team=self.pilot_team, air_speed=123, tracker_device_id="foreign-tracker-id"
        )

        self.own_route = Route.objects.create(name="Own Route")
        self.own_navigation_task = NavigationTask.create(
            name="Own Task",
            original_scorecard=get_default_scorecard(),
            route=self.own_route,
            contest=self.own_contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
            is_public=True,
            allow_self_management=True,
        )

    def test_self_registration_rejects_contest_team_from_another_contest(self, *args):
        self.client.force_login(user=self.pilot_user)
        url = reverse(
            "navigationtasks-contestant-self-registration",
            kwargs={"contest_pk": self.own_contest.pk, "pk": self.own_navigation_task.pk},
        )
        response = self.client.post(
            url,
            data={
                "starting_point_time": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)).isoformat(),
                "contest_team": self.foreign_contest_team.pk,
                "wind_speed": 0,
                "wind_direction": 0,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Contestant.objects.filter(navigation_task=self.own_navigation_task).exists())

    def test_schedule_contestants_ignores_contest_team_from_another_contest(self, *args):
        success, messages = schedule_and_create_contestants(
            navigation_task=self.own_navigation_task,
            contest_teams_pks=[self.foreign_contest_team.pk],
            first_takeoff_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
            tracker_leadtime_minutes=15,
            aircraft_switch_time_minutes=30,
            tracker_switch_time=15,
            minimum_start_interval=5,
            minimum_finish_interval=2,
            crew_switch_time=15,
        )
        # The foreign team is silently excluded (same semantics as an unknown/invalid pk),
        # not scheduled - the foreign contest's tracker_device_id must never be pulled in.
        self.assertFalse(
            Contestant.objects.filter(navigation_task=self.own_navigation_task, tracker_device_id="foreign-tracker-id").exists()
        )
