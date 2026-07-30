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
from display.utilities.cima_task_type_definitions import CONTRACT_NAVIGATION_TIME_CONTROLS
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestContractNavigationScheduler(TestCase):
    def setUp(self):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.contest = Contest.objects.create(
            name="Scheduler Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
        )
        self.navigation_task = NavigationTask.objects.create(
            name="Scheduled Contract Task",
            contest=self.contest,
            route=Route.objects.create(name="Scheduled Route", waypoints=[], takeoff_gates=[], landing_gates=[]),
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype=CONTRACT_NAVIGATION_TIME_CONTROLS,
            task_config={"contract_time_seconds": 600},
            wind_speed=0,
            wind_direction=0,
            minutes_to_starting_point=5,
            minutes_to_landing=5,
        )
        self.navigation_task.editable_route = None
        self.navigation_task.save(update_fields=["editable_route"])

        pilot = Person.objects.create(first_name="Pilot", last_name="Scheduled", email="scheduled@example.com")
        team = Team.objects.create(
            crew=Crew.objects.create(member1=pilot),
            aeroplane=Aeroplane.objects.create(registration="LN-SCHED"),
        )
        self.contest_team = ContestTeam.objects.create(contest=self.contest, team=team, air_speed=70)

    @patch("display.contestant_scheduling.schedule_contestants._build_default_declaration_payload")
    @patch("display.contestant_scheduling.schedule_contestants.calculate_and_get_relative_gate_times")
    @patch("display.contestant_scheduling.schedule_contestants.Solver")
    def test_scheduler_creates_contract_configuration_for_new_contestant(
        self,
        mock_solver,
        mock_gate_times,
        mock_default_payload,
        *_args,
    ):
        first_takeoff_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)
        mock_gate_times.return_value = [("SP", datetime.timedelta()), ("FP", datetime.timedelta(minutes=30))]
        mock_default_payload.return_value = {"declared_sequence": ["A", "MP", "C", "FP"], "declared_t_seconds": 600}
        mock_solver.return_value.optimisation_messages = []
        mock_solver.return_value.schedule_teams.return_value = [
            SimpleNamespace(
                pk=self.contest_team.pk,
                start_time=first_takeoff_time,
                flight_time=30,
                frozen=False,
            )
        ]

        success, messages = schedule_and_create_contestants(
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

        self.assertTrue(success)
        self.assertEqual([], messages)
        contestant = Contestant.objects.get(navigation_task=self.navigation_task, team=self.contest_team.team)
        self.assertEqual(
            contestant.contestanttaskconfiguration.declaration_payload,
            {"declared_sequence": ["A", "MP", "C", "FP"], "declared_t_seconds": 600},
        )

    @patch("display.contestant_scheduling.schedule_contestants._build_default_declaration_payload")
    @patch("display.contestant_scheduling.schedule_contestants.calculate_and_get_relative_gate_times")
    @patch("display.contestant_scheduling.schedule_contestants.Solver")
    def test_scheduler_reuses_existing_contestant_and_refreshes_configuration(
        self,
        mock_solver,
        mock_gate_times,
        mock_default_payload,
        *_args,
    ):
        first_takeoff_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)
        existing = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.contest_team.team,
            contestant_number=1,
            takeoff_time=first_takeoff_time + datetime.timedelta(minutes=1),
            tracker_start_time=first_takeoff_time - datetime.timedelta(minutes=9),
            finished_by_time=first_takeoff_time + datetime.timedelta(hours=1),
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
        )
        mock_gate_times.return_value = [("SP", datetime.timedelta()), ("FP", datetime.timedelta(minutes=30))]
        mock_default_payload.return_value = {"declared_sequence": ["B", "MP", "D", "FP"], "declared_t_seconds": 600}
        mock_solver.return_value.optimisation_messages = []
        mock_solver.return_value.schedule_teams.return_value = [
            SimpleNamespace(
                pk=self.contest_team.pk,
                start_time=first_takeoff_time,
                flight_time=30,
                frozen=False,
            )
        ]

        success, _messages = schedule_and_create_contestants(
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

        self.assertTrue(success)
        existing.refresh_from_db()
        self.assertEqual(
            existing.contestanttaskconfiguration.declaration_payload,
            {"declared_sequence": ["B", "MP", "D", "FP"], "declared_t_seconds": 600},
        )
