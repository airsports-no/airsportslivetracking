import os
import datetime
import json
import threading
from pprint import pprint
from unittest import skip
from unittest.mock import Mock, patch, call

import dateutil
import logging
from django.core.cache import cache
from django.test import TransactionTestCase, TestCase

from display.calculators.contestant_processor import ContestantProcessor
from display.calculators.tests.test_precision_calculator import calculator_runner
from display.models import (
    Aeroplane,
    NavigationTask,
    Team,
    Contestant,
    ContestantTrack,
    Crew,
    Contest,
    Person,
    TeamTestScore,
    EditableRoute,
)
from utilities.mock_utilities import TraccarMock

TEST_DATA_DIR = os.path.dirname(__file__)

@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestANR(TransactionTestCase):
    @patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        from display.default_scorecards import default_scorecard_anr_2020

        self.scorecard = default_scorecard_anr_2020.get_default_scorecard()
        with open(os.path.join(TEST_DATA_DIR, "eidsvoll.kml"), "r") as file:
            with patch(
                "display.models.EditableRoute._create_route_and_thumbnail",
                lambda name, r: EditableRoute.objects.create(name=name, route=r),
            ):
                editable_route, _ = EditableRoute.create_from_kml("Test", file)
                route = editable_route.create_precision_route(True, self.scorecard)
        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        aeroplane = Aeroplane.objects.create(registration="LN-YDB")

        self.navigation_task = NavigationTask.create(
            name="ANR navigation_task",
            route=route,
            original_scorecard=self.scorecard,
            contest=Contest.objects.create(
                name="contest",
                start_time=datetime.datetime.now(datetime.timezone.utc),
                finish_time=datetime.datetime.now(datetime.timezone.utc),
                time_zone="Europe/Oslo",
            ),
            start_time=navigation_task_start_time,
            finish_time=navigation_task_finish_time,
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=aeroplane)
        # Required to make the time zone save correctly
        self.navigation_task.refresh_from_db()

    def test_track(self, *args):
        start_time, speed = datetime.datetime(2020, 8, 1, 10, 5, tzinfo=datetime.timezone.utc), 80
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=speed,
            wind_direction=165,
            wind_speed=8,
        )
        with open(os.path.join(TEST_DATA_DIR, "anr_miss_multiple_finish.csv"), "r") as file:
            track = json.load(file)
        calculator_runner(self.contestant, track)
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(1004, contestant_track.score)

    def test_track_adaptive_start(self, *args):
        start_time, speed = datetime.datetime(2020, 8, 1, 10, 5, tzinfo=datetime.timezone.utc), 80
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=speed,
            wind_direction=165,
            wind_speed=8,
            adaptive_start=True,
        )
        with open(os.path.join(TEST_DATA_DIR, "anr_miss_start_and_finish.csv"), "r") as file:
            track = json.load(file)
        calculator_runner(self.contestant, track)
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(1200, contestant_track.score)


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestAnrCorridorCalculator(TransactionTestCase):
    @patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        from display.default_scorecards import default_scorecard_anr_2020

        self.scorecard = default_scorecard_anr_2020.get_default_scorecard()
        with open(os.path.join(TEST_DATA_DIR, "eidsvoll.kml"), "r") as file:
            with patch(
                "display.models.EditableRoute._create_route_and_thumbnail",
                lambda name, r: EditableRoute.objects.create(name=name, route=r),
            ):
                editable_route, _ = EditableRoute.create_from_kml("Test", file)
                route = editable_route.create_precision_route(True, self.scorecard)
        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        self.aeroplane = Aeroplane.objects.create(registration="LN-YDB")

        self.navigation_task = NavigationTask.create(
            name="ANR navigation_task",
            route=route,
            original_scorecard=self.scorecard,
            contest=Contest.objects.create(
                name="contest",
                start_time=datetime.datetime.now(datetime.timezone.utc),
                finish_time=datetime.datetime.now(datetime.timezone.utc),
                time_zone="Europe/Oslo",
            ),
            start_time=navigation_task_start_time,
            finish_time=navigation_task_finish_time,
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=self.aeroplane)
        # Required to make the time zone save correctly
        self.navigation_task.refresh_from_db()
        start_time, speed = datetime.datetime(2020, 8, 1, 10, 5, tzinfo=datetime.timezone.utc), 80
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=speed,
            wind_direction=165,
            wind_speed=8,
        )

    def test_outside_2_seconds_enroute(self, *args):
        # Grace time is 5 seconds, so 2 seconds outside should not give any penalty.
        track = [
            {"time": "2020-08-01T10:11:00Z", "latitude": 60.3304, "longitude": 11.233},
            {"time": "2020-08-01T10:11:01Z", "latitude": 60.3304, "longitude": 11.233},
            {"time": "2020-08-01T10:11:02Z", "latitude": 60.3304, "longitude": 11.233},
        ]
        calculator_runner(self.contestant, track)
        self.assertEqual(0, self.contestant.contestanttrack.score)

    def test_outside_20_seconds_enroute(self, *args):
        # Grace time is 5 seconds, so 20 seconds outside should give 15 * 3 penalty points.
        track = [{"time": "2020-08-01T10:11:{:02d}Z".format(i), "latitude": 60.3304, "longitude": 11.233} for i in range(21)]
        calculator_runner(self.contestant, track)
        self.assertEqual(15 * self.scorecard.corridor_outside_penalty, self.contestant.contestanttrack.score)

    def test_inside_20_seconds_enroute(self, *args):
        # Inside the corridor, should give 0 penalty.
        track = [{"time": "2020-08-01T10:11:{:02d}Z".format(i), "latitude": 60.3304, "longitude": 11.133} for i in range(21)]
        calculator_runner(self.contestant, track)
        self.assertEqual(0, self.contestant.contestanttrack.score)

    def test_outside_20_seconds_outside_route(self, *args):
        # Outside the corridor, but not enroute, so should give 0 penalty.
        track = [{"time": "2020-08-01T10:10:{:02d}Z".format(i), "latitude": 60.3304, "longitude": 11.233} for i in range(21)]
        calculator_runner(self.contestant, track)
        self.assertEqual(0, self.contestant.contestanttrack.score)

    def test_outside_20_seconds_until_finish(self, *args):
        # Starts outside and flies until finish point.
        track = [{"time": "2020-08-01T10:11:{:02d}Z".format(i), "latitude": 60.3304, "longitude": 11.233} for i in range(21)]
        track.append({"time": "2020-08-01T10:11:21Z", "latitude": 60.3304, "longitude": 11.133})
        # Add finish point position
        track.append({"time": "2020-08-01T10:11:22Z", "latitude": 60.3204, "longitude": 11.133})
        calculator_runner(self.contestant, track)
        self.assertEqual(15 * self.scorecard.corridor_outside_penalty, self.contestant.contestanttrack.score)


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestANRPolygon(TransactionTestCase):
    @patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        from display.default_scorecards import default_scorecard_anr_2020

        self.scorecard = default_scorecard_anr_2020.get_default_scorecard()
        with open(os.path.join(TEST_DATA_DIR, "kjeller.kml"), "r") as file:
            with patch(
                "display.models.EditableRoute._create_route_and_thumbnail",
                lambda name, r: EditableRoute.objects.create(name=name, route=r),
            ):
                editable_route, _ = EditableRoute.create_from_kml("Test", file)
                route = editable_route.create_precision_route(True, self.scorecard)
        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        self.aeroplane = Aeroplane.objects.create(registration="LN-YDB")

        self.navigation_task = NavigationTask.create(
            name="ANR navigation_task",
            route=route,
            original_scorecard=self.scorecard,
            contest=Contest.objects.create(
                name="contest",
                start_time=datetime.datetime.now(datetime.timezone.utc),
                finish_time=datetime.datetime.now(datetime.timezone.utc),
                time_zone="Europe/Oslo",
            ),
            start_time=navigation_task_start_time,
            finish_time=navigation_task_finish_time,
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=self.aeroplane)
        # Required to make the time zone save correctly
        self.navigation_task.refresh_from_db()

    def test_track(self, *args):
        start_time, speed = datetime.datetime(2020, 8, 1, 10, 5, tzinfo=datetime.timezone.utc), 80
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=speed,
            wind_direction=165,
            wind_speed=8,
        )
        with open(os.path.join(TEST_DATA_DIR, "kjeller.csv"), "r") as file:
            track = json.load(file)
        calculator_runner(self.contestant, track)
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(140, contestant_track.score)


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestANRBergenBacktracking(TransactionTestCase):
    @patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        from display.default_scorecards import default_scorecard_anr_2020

        self.scorecard = default_scorecard_anr_2020.get_default_scorecard()
        with open(os.path.join(TEST_DATA_DIR, "Bergen_Open_Test.kml"), "r") as file:
            with patch(
                "display.models.EditableRoute._create_route_and_thumbnail",
                lambda name, r: EditableRoute.objects.create(name=name, route=r),
            ):
                editable_route, _ = EditableRoute.create_from_kml("Test", file)
                route = editable_route.create_precision_route(True, self.scorecard)
        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        self.aeroplane = Aeroplane.objects.create(registration="LN-YDB")

        self.navigation_task = NavigationTask.create(
            name="ANR navigation_task",
            route=route,
            original_scorecard=self.scorecard,
            contest=Contest.objects.create(
                name="contest",
                start_time=datetime.datetime.now(datetime.timezone.utc),
                finish_time=datetime.datetime.now(datetime.timezone.utc),
                time_zone="Europe/Oslo",
            ),
            start_time=navigation_task_start_time,
            finish_time=navigation_task_finish_time,
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=self.aeroplane)
        # Required to make the time zone save correctly
        self.navigation_task.refresh_from_db()

    def test_track(self, *args):
        start_time, speed = datetime.datetime(2022, 5, 14, 10, 5, tzinfo=datetime.timezone.utc), 80
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=speed,
            wind_direction=165,
            wind_speed=8,
        )
        with open(os.path.join(TEST_DATA_DIR, "Bergen_backtracking.csv"), "r") as file:
            track = json.load(file)
        calculator_runner(self.contestant, track)
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(600, contestant_track.score)


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestANRBergenBacktrackingTommy(TransactionTestCase):
    @patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        from display.default_scorecards import default_scorecard_anr_2020

        self.scorecard = default_scorecard_anr_2020.get_default_scorecard()
        with open(os.path.join(TEST_DATA_DIR, "tommy_test.kml"), "r") as file:
            with patch(
                "display.models.EditableRoute._create_route_and_thumbnail",
                lambda name, r: EditableRoute.objects.create(name=name, route=r),
            ):
                editable_route, _ = EditableRoute.create_from_kml("Test", file)
                route = editable_route.create_precision_route(True, self.scorecard)
        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        self.aeroplane = Aeroplane.objects.create(registration="LN-YDB")

        self.navigation_task = NavigationTask.create(
            name="ANR navigation_task",
            route=route,
            original_scorecard=self.scorecard,
            contest=Contest.objects.create(
                name="contest",
                start_time=datetime.datetime.now(datetime.timezone.utc),
                finish_time=datetime.datetime.now(datetime.timezone.utc),
                time_zone="Europe/Oslo",
            ),
            start_time=navigation_task_start_time,
            finish_time=navigation_task_finish_time,
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=self.aeroplane)
        # Required to make the time zone save correctly
        self.navigation_task.refresh_from_db()

    def test_track(self, *args):
        start_time, speed = datetime.datetime(2022, 5, 14, 10, 5, tzinfo=datetime.timezone.utc), 80
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=speed,
            wind_direction=165,
            wind_speed=8,
        )
        with open(os.path.join(TEST_DATA_DIR, "tommy_missing_circling_penalty.csv"), "r") as file:
            track = json.load(file)
        calculator_runner(self.contestant, track)
        strings = [item.string for item in self.contestant.scorelogentry_set.all()]
        for s in strings:
            print(s)
        # If the last outside corridor is counted twice, the score will be closer to 1600.
        self.assertEqual(932, self.contestant.contestanttrack.score)
