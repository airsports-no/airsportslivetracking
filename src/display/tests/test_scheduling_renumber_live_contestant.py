"""
Regression test for scheduling finding #2 (2026-08-28 review): the renumbering loop in
schedule_and_create_contestants_navigation_tasks only treated a contestant as "keep its number"
if schedule_locked or already finished before the reschedule point - it never checked
contestanttrack.calculator_started, unlike the freeze-set query just above it in the same
function. A live contestant (calculator started, not schedule_locked) could get renumbered to
collide with a newly-scheduled contestant's number, raising IntegrityError on the
(navigation_task, contestant_number) unique constraint.
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
class TestSchedulingDoesNotRenumberLiveContestant(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.contest = Contest.objects.create(
            name="Renumber Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 20, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
        )
        self.navigation_task = NavigationTask.objects.create(
            name="Renumber Task",
            contest=self.contest,
            route=Route.objects.create(name="Renumber Route", waypoints=[], takeoff_gates=[], landing_gates=[]),
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 20, 0, tzinfo=datetime.timezone.utc),
            wind_speed=0,
            wind_direction=0,
            minutes_to_starting_point=5,
            minutes_to_landing=5,
        )

        self.first_takeoff_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)

        # An existing, LIVE contestant: calculator already started, not schedule_locked,
        # finishing after first_takeoff_time (so it's in the freeze-set's scope) - holds
        # contestant_number=1 and takes off LATER than the newly-scheduled team below.
        live_pilot = Person.objects.create(first_name="Live", last_name="Pilot", email="live-pilot@example.com")
        live_team = Team.objects.create(
            crew=Crew.objects.create(member1=live_pilot), aeroplane=Aeroplane.objects.create(registration="LN-LIVE")
        )
        # schedule_and_create_contestants_navigation_tasks looks up a ContestTeam for every
        # locked/live contestant to build its solver constraints - a real live contestant would
        # always have one from its original registration/scheduling.
        ContestTeam.objects.create(contest=self.contest, team=live_team, air_speed=70)
        self.live_contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=live_team,
            contestant_number=1,
            takeoff_time=self.first_takeoff_time + datetime.timedelta(hours=2),
            tracker_start_time=self.first_takeoff_time + datetime.timedelta(hours=1, minutes=50),
            finished_by_time=self.first_takeoff_time + datetime.timedelta(hours=3),
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
        )
        self.live_contestant.contestanttrack.calculator_started = True
        self.live_contestant.contestanttrack.save()

        new_pilot = Person.objects.create(first_name="New", last_name="Pilot", email="new-pilot@example.com")
        new_team = Team.objects.create(
            crew=Crew.objects.create(member1=new_pilot), aeroplane=Aeroplane.objects.create(registration="LN-NEW")
        )
        self.new_contest_team = ContestTeam.objects.create(contest=self.contest, team=new_team, air_speed=70)

    @patch("display.contestant_scheduling.schedule_contestants._build_default_declaration_payload")
    @patch("display.contestant_scheduling.schedule_contestants.calculate_and_get_relative_gate_times")
    @patch("display.contestant_scheduling.schedule_contestants.Solver")
    def test_reschedule_does_not_renumber_the_live_contestant(self, mock_solver, mock_gate_times, mock_default_payload, *args):
        mock_gate_times.return_value = [("SP", datetime.timedelta()), ("FP", datetime.timedelta(minutes=30))]
        mock_default_payload.return_value = {}
        mock_solver.return_value.optimisation_messages = []
        # The new team takes off BEFORE the live contestant, so it sorts first in the
        # renumbering loop's takeoff_time order - this is exactly the ordering that let the
        # bug's incorrectly-freed number 1 collide with the live contestant's still-unmoved row.
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
        self.live_contestant.refresh_from_db()
        self.assertEqual(self.live_contestant.contestant_number, 1)

        new_contestant = Contestant.objects.get(navigation_task=self.navigation_task, team=self.new_contest_team.team)
        self.assertNotEqual(new_contestant.contestant_number, 1)
