"""
Regression test for scheduling finding #5 (2026-08-28 review):
schedule_and_create_contestants_landing_task assigned brand-new contestants a number by
list position (index + 1) among only the currently-selected teams, ignoring contestant
numbers already in use by teams NOT in the current selection. Any mixed re-run (some
teams already scheduled, some new) could collide with an existing number and raise
IntegrityError on the (navigation_task, contestant_number) unique constraint.
"""

import datetime
from unittest.mock import patch

from django.test import TestCase

from display.contestant_scheduling.schedule_contestants import schedule_and_create_contestants
from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Aeroplane, Contest, ContestTeam, Contestant, Crew, NavigationTask, Person, Route, Scorecard, Team
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestLandingTaskSchedulingContestantNumberCollision(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="Landing")
        self.contest = Contest.objects.create(
            name="Landing Number Collision Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 20, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
        )
        self.navigation_task = NavigationTask.objects.create(
            name="Landing Number Collision Task",
            contest=self.contest,
            route=Route.objects.create(name="Landing Route", waypoints=[], takeoff_gates=[], landing_gates=[]),
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 20, 0, tzinfo=datetime.timezone.utc),
            wind_speed=0,
            wind_direction=0,
            minutes_to_starting_point=5,
            minutes_to_landing=5,
        )
        self.first_takeoff_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)

        # A team already scheduled in a previous run, holding contestant_number=1, and NOT
        # part of the current selection (e.g. it was scheduled separately/earlier).
        existing_pilot = Person.objects.create(first_name="Existing", last_name="Pilot", email="existing-pilot@example.com")
        existing_team = Team.objects.create(
            crew=Crew.objects.create(member1=existing_pilot), aeroplane=Aeroplane.objects.create(registration="LN-EXIST")
        )
        ContestTeam.objects.create(contest=self.contest, team=existing_team, air_speed=70)
        Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=existing_team,
            contestant_number=1,
            takeoff_time=self.first_takeoff_time,
            tracker_start_time=self.first_takeoff_time,
            finished_by_time=self.navigation_task.finish_time,
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
        )

        # A brand-new team being scheduled now - naively assigned index+1 == 1, colliding
        # with the existing contestant above since it's the only item in this selection.
        new_pilot = Person.objects.create(first_name="New", last_name="Pilot", email="new-pilot-landing@example.com")
        new_team = Team.objects.create(
            crew=Crew.objects.create(member1=new_pilot), aeroplane=Aeroplane.objects.create(registration="LN-NEWLAND")
        )
        self.new_contest_team = ContestTeam.objects.create(contest=self.contest, team=new_team, air_speed=70)

    @patch("display.contestant_scheduling.schedule_contestants.ContestantTaskCompiler")
    @patch("display.contestant_scheduling.schedule_contestants._build_default_declaration_payload", return_value={})
    def test_scheduling_a_new_team_does_not_collide_with_an_existing_contestant_number(
        self, mock_default_payload, mock_compiler, *args
    ):
        success, messages = schedule_and_create_contestants(
            navigation_task=self.navigation_task,
            contest_teams_pks=[self.new_contest_team.pk],
            first_takeoff_time=self.first_takeoff_time,
            tracker_leadtime_minutes=15,
            aircraft_switch_time_minutes=30,
            tracker_switch_time=15,
            minimum_start_interval=5,
            minimum_finish_interval=2,
            crew_switch_time=15,
            optimise=False,
        )

        self.assertTrue(success, messages)
        new_contestant = Contestant.objects.get(navigation_task=self.navigation_task, team=self.new_contest_team.team)
        self.assertNotEqual(new_contestant.contestant_number, 1)
