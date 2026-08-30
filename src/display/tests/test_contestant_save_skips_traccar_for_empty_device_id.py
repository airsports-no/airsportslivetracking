"""
Regression test for models+services finding #9 (2026-08-28 review): Contestant.save()
unconditionally called traccar.get_or_create_device("", "") for any contestant with
tracking_service=TRACCAR and an empty tracker_device_id (the normal state for an
app-tracked contestant - see Person.simulator_tracking_id's help text), which can
POST-create a device with an empty uniqueId on the Traccar side and adds a synchronous
external HTTP call to every save, including bulk scheduler writes. The equivalent
post_save signal handler (create_tracker_in_traccar, display/signals.py) already guards
on len(tracker_device_id) > 0; save() didn't.
"""

import datetime

from django.test import TestCase

from display.models import Aeroplane, Contest, Contestant, Crew, NavigationTask, Person, Route, Scorecard, Team
from display.default_scorecards.create_scorecards import create_scorecards
from display.utilities.tracking_definitions import TrackingService
from utilities.mock_utilities import TraccarMock


class TestContestantSaveSkipsTraccarForEmptyDeviceId(TestCase):
    def setUp(self):
        create_scorecards()
        scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        contest = Contest.objects.create(
            name="Traccar save contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            time_zone="Europe/Oslo",
        )
        self.navigation_task = NavigationTask.objects.create(
            name="Traccar save task",
            contest=contest,
            route=Route.objects.create(name="Traccar save route", waypoints=[], takeoff_gates=[], landing_gates=[]),
            original_scorecard=scorecard,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Traccar", last_name="Save"))
        self.team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-TRACCAR"))
        TraccarMock.get_or_create_device.reset_mock()

    def _create_kwargs(self, **overrides):
        start_time = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc)
        kwargs = dict(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=75,
            wind_direction=165,
            wind_speed=8,
            tracking_service=TrackingService.TRACCAR,
        )
        kwargs.update(overrides)
        return kwargs

    def test_save_with_empty_tracker_device_id_does_not_call_traccar(self):
        from unittest.mock import patch

        with patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock), patch(
            "display.signals.get_traccar_instance", return_value=TraccarMock
        ):
            Contestant.objects.create(**self._create_kwargs(tracker_device_id=""))

        TraccarMock.get_or_create_device.assert_not_called()

    def test_save_with_a_real_tracker_device_id_still_calls_traccar(self):
        from unittest.mock import patch

        with patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock), patch(
            "display.signals.get_traccar_instance", return_value=TraccarMock
        ):
            Contestant.objects.create(**self._create_kwargs(tracker_device_id="real-device-123"))

        TraccarMock.get_or_create_device.assert_any_call("real-device-123", "real-device-123")
