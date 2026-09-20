"""
Regression coverage for `manage.py backfill_passed_starting_gate`. display.calculators.
orchestrator.Orchestrator.handle_event only started calling set_passed_starting_gate() on
StartingLinePassedEvent in this session's fix - every ContestantTrack row from before that fix
stays permanently passed_starting_gate=False otherwise, since nothing else derives it
retroactively. This command backfills it from ActualGateTime records already on disk.
"""

import datetime
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import ActualGateTime, Aeroplane, Contest, Contestant, Crew, EditableRoute, NavigationTask, Person, Scorecard, Team
from utilities.mock_utilities import TraccarMock


class TestBackfillPassedStartingGate(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Backfill test", file.readlines()[1:])
            self.route = editable_route.create_precision_route(True, self.scorecard)
        self.contest = Contest.objects.create(
            name="Backfill starting gate contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            time_zone="Europe/Oslo",
        )
        self.navigation_task = NavigationTask.create(
            name="Backfill starting gate task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
        )

    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def _make_contestant(self, number, *args):
        crew = Crew.objects.create(
            member1=Person.objects.create(first_name="Pilot", last_name=str(number), email=f"backfill-pilot-{number}@example.com")
        )
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration=f"LN-BF{number}"))
        start_time = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc)
        return Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id=f"backfill-test-{number}",
            contestant_number=number,
            minutes_to_starting_point=6,
            air_speed=75,
            wind_direction=165,
            wind_speed=8,
        )

    def test_backfills_contestants_with_a_recorded_sp_crossing(self):
        crossed_sp = self._make_contestant(1)
        ActualGateTime.objects.create(
            contestant=crossed_sp, gate="SP", time=datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc)
        )
        never_started = self._make_contestant(2)

        out = StringIO()
        call_command("backfill_passed_starting_gate", stdout=out)

        crossed_sp.contestanttrack.refresh_from_db()
        never_started.contestanttrack.refresh_from_db()
        self.assertTrue(crossed_sp.contestanttrack.passed_starting_gate)
        self.assertFalse(never_started.contestanttrack.passed_starting_gate)
        self.assertIn("Updated 1.", out.getvalue())

    def test_dry_run_reports_but_does_not_write(self):
        crossed_sp = self._make_contestant(1)
        ActualGateTime.objects.create(
            contestant=crossed_sp, gate="SP", time=datetime.datetime(2020, 8, 1, 8, 10, tzinfo=datetime.timezone.utc)
        )

        out = StringIO()
        call_command("backfill_passed_starting_gate", "--dry-run", stdout=out)

        crossed_sp.contestanttrack.refresh_from_db()
        self.assertFalse(crossed_sp.contestanttrack.passed_starting_gate)
        self.assertIn("Would update 1.", out.getvalue())

    def test_already_set_rows_are_not_reconsidered(self):
        # The command's own queryset filters to passed_starting_gate=False, so a row already
        # correctly set (by live tracking, post-fix) is never touched or double-counted.
        already_set = self._make_contestant(1)
        already_set.contestanttrack.passed_starting_gate = True
        already_set.contestanttrack.save(update_fields=["passed_starting_gate"])

        out = StringIO()
        call_command("backfill_passed_starting_gate", stdout=out)

        self.assertIn("Checked 0 contestant(s)", out.getvalue())

    def test_a_gate_crossing_for_a_different_gate_than_start_does_not_count(self):
        # TP1 exists on this route's waypoint list, but it isn't the first real gate - only an
        # actual crossing of SP itself should count as having passed the starting gate.
        only_crossed_tp1 = self._make_contestant(1)
        ActualGateTime.objects.create(
            contestant=only_crossed_tp1, gate="TP1", time=datetime.datetime(2020, 8, 1, 8, 20, tzinfo=datetime.timezone.utc)
        )

        call_command("backfill_passed_starting_gate", stdout=StringIO())

        only_crossed_tp1.contestanttrack.refresh_from_db()
        self.assertFalse(only_crossed_tp1.contestanttrack.passed_starting_gate)
