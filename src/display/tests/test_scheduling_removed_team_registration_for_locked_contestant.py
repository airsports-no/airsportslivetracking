"""
Regression test for scheduling finding #8 (2026-08-28 review): the loop in
schedule_and_create_contestants_navigation_tasks that builds solver constraints for
locked/live contestants does an unguarded ContestTeam.objects.get(contest=..., team=...) -
if that team's ContestTeam registration was since removed from the contest (while a
schedule_locked or already-tracking contestant for it still exists), this raises
ContestTeam.DoesNotExist -> an uncaught 500, blocking scheduling for every other
selected team too.
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
class TestSchedulingSkipsLockedContestantWithRemovedTeamRegistration(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.contest = Contest.objects.create(
            name="Removed Registration Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 20, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
        )
        self.navigation_task = NavigationTask.objects.create(
            name="Removed Registration Task",
            contest=self.contest,
            route=Route.objects.create(name="Removed Registration Route", waypoints=[], takeoff_gates=[], landing_gates=[]),
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 20, 0, tzinfo=datetime.timezone.utc),
            wind_speed=0,
            wind_direction=0,
            minutes_to_starting_point=5,
            minutes_to_landing=5,
        )

        self.first_takeoff_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)

        # A locked contestant whose team's ContestTeam registration has since been removed
        # from the contest (e.g. an organizer deregistered the team after it was locked in).
        # The Contestant row (and its lock) still exists - only the ContestTeam is gone.
        orphaned_pilot = Person.objects.create(first_name="Orphaned", last_name="Pilot", email="orphaned-pilot@example.com")
        orphaned_team = Team.objects.create(
            crew=Crew.objects.create(member1=orphaned_pilot), aeroplane=Aeroplane.objects.create(registration="LN-GONE")
        )
        self.locked_contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=orphaned_team,
            contestant_number=1,
            takeoff_time=self.first_takeoff_time + datetime.timedelta(hours=2),
            tracker_start_time=self.first_takeoff_time + datetime.timedelta(hours=1, minutes=50),
            finished_by_time=self.first_takeoff_time + datetime.timedelta(hours=3),
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
            schedule_locked=True,
        )
        # Deliberately no ContestTeam.objects.create(...) for orphaned_team - simulates the
        # team's registration having been removed from the contest after locking.

        new_pilot = Person.objects.create(first_name="New", last_name="Pilot", email="new-pilot-8@example.com")
        new_team = Team.objects.create(
            crew=Crew.objects.create(member1=new_pilot), aeroplane=Aeroplane.objects.create(registration="LN-NEW8")
        )
        self.new_contest_team = ContestTeam.objects.create(contest=self.contest, team=new_team, air_speed=70)

    @patch("display.contestant_scheduling.schedule_contestants._build_default_declaration_payload")
    @patch("display.contestant_scheduling.schedule_contestants.calculate_and_get_relative_gate_times")
    @patch("display.contestant_scheduling.schedule_contestants.Solver")
    def test_scheduling_other_teams_succeeds_instead_of_500ing_on_the_orphaned_locked_contestant(
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
        new_contestant = Contestant.objects.get(navigation_task=self.navigation_task, team=self.new_contest_team.team)
        self.assertIsNotNone(new_contestant)

        # The orphaned locked contestant itself is untouched - only skipped as a solver
        # constraint input, not deleted or otherwise mutated.
        self.locked_contestant.refresh_from_db()
        self.assertTrue(self.locked_contestant.schedule_locked)
