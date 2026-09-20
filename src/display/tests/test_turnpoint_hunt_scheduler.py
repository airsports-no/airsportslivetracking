"""
Tests for schedule_and_create_contestants_navigation_tasks' flight-duration computation for task
types with no route backbone (2.A6 Turnpoint hunt / 2.B2 Limited fuel turnpoint hunt explicitly
forbid one - see cima_task_type_definitions.py). calculate_and_get_relative_gate_times correctly
returns [] for such a route (route.waypoints is empty), but the scheduler used to assume
gate_times was always non-empty and crashed with IndexError on gate_times[-1].
"""

import datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from display.contestant_scheduling.schedule_contestants import schedule_and_create_contestants
from display.default_scorecards.create_scorecards import create_scorecards
from display.models import (
    Aeroplane,
    Contest,
    ContestTeam,
    Contestant,
    Crew,
    NavigationTask,
    Person,
    Route,
    Scorecard,
    Team,
)
from display.utilities.cima_task_type_definitions import TURNPOINT_HUNT
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestTurnpointHuntScheduler(TestCase):
    def setUp(self):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.contest = Contest.objects.create(
            name="Turnpoint Hunt Scheduler Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
        )
        # No route backbone: an empty-waypoints Route, matching what a real 2.A6 route (built
        # from standalone known_time_gate/catalogue_turnpoint markers, never route_waypoint
        # features) compiles down to on the legacy Route model.
        self.navigation_task = NavigationTask.objects.create(
            name="Scheduled Turnpoint Hunt Task",
            contest=self.contest,
            route=Route.objects.create(name="Backbone-less Route", waypoints=[], takeoff_gates=[], landing_gates=[]),
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype=TURNPOINT_HUNT,
            wind_speed=0,
            wind_direction=0,
            minutes_to_starting_point=5,
            minutes_to_landing=5,
        )
        self.navigation_task.editable_route = None
        self.navigation_task.save(update_fields=["editable_route"])

        pilot = Person.objects.create(first_name="Pilot", last_name="Hunt", email="turnpoint-hunt@example.com")
        team = Team.objects.create(
            crew=Crew.objects.create(member1=pilot),
            aeroplane=Aeroplane.objects.create(registration="LN-HUNT"),
        )
        self.contest_team = ContestTeam.objects.create(contest=self.contest, team=team, air_speed=70)

    def _schedule(self, first_takeoff_time):
        with patch("display.contestant_scheduling.schedule_contestants.Solver") as mock_solver:
            mock_solver.return_value.optimisation_messages = []
            mock_solver.return_value.schedule_teams.return_value = [
                SimpleNamespace(
                    pk=self.contest_team.pk,
                    start_time=first_takeoff_time,
                    flight_time=30,
                    frozen=False,
                )
            ]
            return schedule_and_create_contestants(
                navigation_task=self.navigation_task,
                contest_teams_pks=[self.contest_team.pk],
                first_takeoff_time=first_takeoff_time,
                tracker_leadtime_minutes=15,
                aircraft_switch_time_minutes=30,
                tracker_switch_time=15,
                minimum_start_interval=5,
                minimum_finish_interval=2,
                crew_switch_time=15,
                optimise=False,
            )

    def test_scheduling_uses_scorecard_maximum_task_duration_when_there_is_no_route_backbone(self, *_args):
        # NavigationTask.scorecard is its own per-task copy of original_scorecard (so overrides
        # don't mutate the shared template) - update that copy, not self.scorecard. Also a
        # ConfigField (backed by a JSON config blob, not a concrete column), so it can't be
        # targeted with save(update_fields=[...]).
        scorecard = self.navigation_task.scorecard
        scorecard.maximum_task_duration_minutes = 45
        scorecard.save()
        first_takeoff_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)

        success, messages = self._schedule(first_takeoff_time)

        self.assertTrue(success, messages)
        contestant = Contestant.objects.get(navigation_task=self.navigation_task, team=self.contest_team.team)
        # finished_by_time = start_time (tracking_finish_time base) is derived inside the
        # scheduler from takeoff_time/flight_time/tracker timings, not directly asserted here -
        # the key regression check is simply that scheduling succeeded at all instead of raising
        # IndexError on the empty gate_times list.
        self.assertIsNotNone(contestant.finished_by_time)

    def test_scheduling_raises_a_clear_error_when_maximum_task_duration_is_not_configured(self, *_args):
        self.assertIsNone(self.navigation_task.scorecard.maximum_task_duration_minutes)
        first_takeoff_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)

        with self.assertRaises(ValueError):
            self._schedule(first_takeoff_time)
