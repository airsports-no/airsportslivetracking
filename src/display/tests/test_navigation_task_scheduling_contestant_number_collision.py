"""
Regression test for Sentry PYTHON-DJANGO-17: schedule_and_create_contestants_navigation_tasks
assigned every brand-new contestant a "temporary" number by counting up from 10001
(10000 + new_contestants_created + 1), with no check against numbers already in use on the
task. If a locked/frozen contestant already held a number in that range (from history, or a
manual edit), the very first new contestant collided with it and raised IntegrityError on the
(navigation_task, contestant_number) unique constraint - deterministically, on every retry,
since nothing about a naive retry changes the collision. Mirrors the used_numbers approach
schedule_and_create_contestants_landing_task already uses for an analogous collision.
"""

import datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from display.contestant_scheduling.schedule_contestants import schedule_and_create_contestants
from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Aeroplane, Contest, ContestTeam, Contestant, Crew, NavigationTask, Person, Route, Scorecard, Team
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestNavigationTaskSchedulingContestantNumberCollision(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.contest = Contest.objects.create(
            name="Navigation Task Number Collision Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 20, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
        )
        self.navigation_task = NavigationTask.objects.create(
            name="Navigation Task Number Collision Task",
            contest=self.contest,
            route=Route.objects.create(name="Collision Route", waypoints=[], takeoff_gates=[], landing_gates=[]),
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 20, 0, tzinfo=datetime.timezone.utc),
            wind_speed=0,
            wind_direction=0,
            minutes_to_starting_point=5,
            minutes_to_landing=5,
        )

        self.first_takeoff_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)

        # A locked contestant that already holds a number in the "temporary" range the old
        # scheme always started from (exactly reproducing Sentry's '3498-10001' collision).
        locked_pilot = Person.objects.create(first_name="Locked", last_name="Pilot", email="locked-pilot@example.com")
        locked_team = Team.objects.create(
            crew=Crew.objects.create(member1=locked_pilot), aeroplane=Aeroplane.objects.create(registration="LN-LOCK")
        )
        ContestTeam.objects.create(contest=self.contest, team=locked_team, air_speed=70)
        self.locked_contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=locked_team,
            contestant_number=10001,
            schedule_locked=True,
            takeoff_time=self.first_takeoff_time + datetime.timedelta(hours=2),
            tracker_start_time=self.first_takeoff_time + datetime.timedelta(hours=1, minutes=50),
            finished_by_time=self.first_takeoff_time + datetime.timedelta(hours=3),
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
        )

        new_pilot = Person.objects.create(first_name="New", last_name="Pilot", email="new-pilot-navtask@example.com")
        new_team = Team.objects.create(
            crew=Crew.objects.create(member1=new_pilot), aeroplane=Aeroplane.objects.create(registration="LN-NEWNAV")
        )
        self.new_contest_team = ContestTeam.objects.create(contest=self.contest, team=new_team, air_speed=70)

    @patch("display.contestant_scheduling.schedule_contestants._build_default_declaration_payload")
    @patch("display.contestant_scheduling.schedule_contestants.calculate_and_get_relative_gate_times")
    @patch("display.contestant_scheduling.schedule_contestants.Solver")
    def test_scheduling_a_new_team_does_not_collide_with_a_locked_contestants_number(
        self, mock_solver, mock_gate_times, mock_default_payload, *args
    ):
        mock_gate_times.return_value = [("SP", datetime.timedelta()), ("FP", datetime.timedelta(minutes=30))]
        mock_default_payload.return_value = {}
        mock_solver.return_value.optimisation_messages = []
        mock_solver.return_value.schedule_teams.return_value = [
            SimpleNamespace(
                pk=self.new_contest_team.pk,
                start_time=self.first_takeoff_time,
                flight_time=30,
                frozen=False,
            )
        ]

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
        self.locked_contestant.refresh_from_db()
        self.assertEqual(self.locked_contestant.contestant_number, 10001)

        new_contestant = Contestant.objects.get(navigation_task=self.navigation_task, team=self.new_contest_team.team)
        self.assertNotEqual(new_contestant.contestant_number, 10001)
