"""
Regression tests for the SENSITIVE finding (2026-08-28 review, models+services
finding #1): update_contestant_with_related_state persisted via
Contestant.objects.filter(pk=...).update(**normalized_data), which doesn't
emit pre_save, so Contestant.clean()'s "no timing changes after calculator
start" guard compared the new values against a DB row this same call had
already overwritten - the guard always passed trivially, letting timing/wind
fields be changed via PATCH/PUT after calculator_started, and silently
defeating delete_flight_order_and_gate_times_if_changed too.
"""

import datetime
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TransactionTestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import NavigationTask, Contest, Route, Contestant, Aeroplane, Crew, Team, Person, TRACKING_DEVICE
from display.services.contestant_persistence import update_contestant_with_related_state
from utilities.mock_utilities import TraccarMock

TRACKER_NAME = "tracker"


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestUpdateContestantCalculatorStartedGuard(TransactionTestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        self.contest = Contest.objects.create(
            name="TestContest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
        )
        route = Route.objects.create(name="Route")
        self.navigation_task = NavigationTask.create(
            name="NavigationTask",
            original_scorecard=get_default_scorecard(),
            start_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc),
            route=route,
            contest=self.contest,
        )
        aeroplane = Aeroplane.objects.create(registration="registration")
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=aeroplane)
        self.original_takeoff_time = datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc)
        self.contestant = Contestant.objects.create(
            team=self.team,
            tracking_device=TRACKING_DEVICE,
            navigation_task=self.navigation_task,
            takeoff_time=self.original_takeoff_time,
            contestant_number=1,
            tracker_device_id=TRACKER_NAME,
            tracker_start_time=datetime.datetime(2020, 1, 1, 9, 30, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2020, 1, 1, 12, tzinfo=datetime.timezone.utc),
            wind_speed=5,
            wind_direction=90,
        )
        self.contestant.contestanttrack.calculator_started = True
        self.contestant.contestanttrack.save()

    def test_takeoff_time_change_after_calculator_start_is_rejected(self, *args):
        new_takeoff_time = self.original_takeoff_time + datetime.timedelta(minutes=30)
        with self.assertRaisesMessage(ValidationError, "it is not possible to change takeoff time"):
            update_contestant_with_related_state(
                self.contestant,
                {"takeoff_time": new_takeoff_time},
                gate_times=None,
                partial=True,
            )
        self.contestant.refresh_from_db()
        self.assertEqual(self.contestant.takeoff_time, self.original_takeoff_time)

    def test_wind_speed_change_after_calculator_start_is_rejected(self, *args):
        with self.assertRaisesMessage(ValidationError, "it is not possible to change wind speed"):
            update_contestant_with_related_state(
                self.contestant,
                {"wind_speed": 25},
                gate_times=None,
                partial=True,
            )
        self.contestant.refresh_from_db()
        self.assertEqual(self.contestant.wind_speed, 5)

    def test_unrelated_field_change_after_calculator_start_still_works(self, *args):
        # Fields the guard doesn't cover (e.g. contestant_number) must still
        # be editable after calculator start - only the specifically guarded
        # timing/wind fields are locked.
        update_contestant_with_related_state(
            self.contestant,
            {"contestant_number": 7},
            gate_times=None,
            partial=True,
        )
        self.contestant.refresh_from_db()
        self.assertEqual(self.contestant.contestant_number, 7)
