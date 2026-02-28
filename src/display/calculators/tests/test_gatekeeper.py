import os
import datetime
from multiprocessing import Queue
from unittest import skip
from unittest.mock import patch

import dateutil.parser
from django.test import TransactionTestCase

from display.calculators.contestant_processor import ContestantProcessor
from display.calculators.gatekeeper import Gatekeeper
from display.calculators.gate_calculator import GateCalculator
from display.models import Aeroplane, NavigationTask, Contest, Crew, Contestant, Person, Team, EditableRoute
from display.models.contestant_utility_models import ContestantReceivedPosition
from utilities.mock_utilities import TraccarMock

NM_CSV_PATH = os.path.join(os.path.dirname(__file__), "NM.csv")


@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestInterpolation(TransactionTestCase):
    @patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        from display.default_scorecards import default_scorecard_fai_precision_2020

        self.scorecard = default_scorecard_fai_precision_2020.get_default_scorecard()
        with open(NM_CSV_PATH, "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Test", file.readlines()[1:])
            route = editable_route.create_precision_route(True, self.scorecard)
        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        aeroplane = Aeroplane.objects.create(registration="LN-YDB")

        self.navigation_task = NavigationTask.create(
            name="NM navigation_task",
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
        start_time, speed = datetime.datetime(2020, 8, 1, 9, 15, tzinfo=datetime.timezone.utc), 70
        # Required to make the time zone save correctly
        self.navigation_task.refresh_from_db()
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

    def test_no_interpolation(self, *args):
        processor = ContestantProcessor(self.contestant)
        start_position = ContestantReceivedPosition(
            contestant=self.contestant, time=dateutil.parser.parse("2020-01-01T00:00:00Z"), latitude=60, longitude=11
        )
        processor.previous_position = start_position
        next_position = ContestantReceivedPosition(
            contestant=self.contestant, time=dateutil.parser.parse("2020-01-01T00:00:01Z"), latitude=60, longitude=12
        )
        interpolated = processor.interpolate_track(start_position, next_position)
        self.assertEqual(1, len(interpolated))
        self.assertEqual(next_position, interpolated[0])

    def test_interpolation(self, *args):
        processor = ContestantProcessor(self.contestant)
        start_position = ContestantReceivedPosition(
            contestant=self.contestant, time=dateutil.parser.parse("2020-01-01T00:00:00Z"), latitude=60, longitude=11
        )
        processor.previous_position = start_position
        next_position = ContestantReceivedPosition(
            contestant=self.contestant, time=dateutil.parser.parse("2020-01-01T00:00:05Z"), latitude=60, longitude=12
        )
        interpolated = processor.interpolate_track(start_position, next_position)
        expected = [
            ("2020-01-01 00:00:01+00:00", 60.00060561690469, 11.199996344501796),
            ("2020-01-01 00:00:02+00:00", 60.000908429948986, 11.399998172228623),
            ("2020-01-01 00:00:03+00:00", 60.00090842994899, 11.600001827771377),
            ("2020-01-01 00:00:04+00:00", 60.00060561690469, 11.800003655498205),
            ("2020-01-01 00:00:05+00:00", 60, 12),
        ]
        self.assertEqual(5, len(interpolated))
        for index in range(len(interpolated)):
            self.assertEqual(str(interpolated[index].time), expected[index][0])
            self.assertAlmostEqual(interpolated[index].latitude, expected[index][1])
            self.assertAlmostEqual(interpolated[index].longitude, expected[index][2])

    def test_interpolation_two_seconds(self, *args):
        processor = ContestantProcessor(self.contestant)
        start_position = ContestantReceivedPosition(
            contestant=self.contestant, time=dateutil.parser.parse("2020-01-01T00:00:00Z"), latitude=60, longitude=11
        )
        processor.previous_position = start_position
        next_position = ContestantReceivedPosition(
            contestant=self.contestant, time=dateutil.parser.parse("2020-01-01T00:00:02Z"), latitude=60, longitude=12
        )
        interpolated = processor.interpolate_track(start_position, next_position)
        expected = [
            ("2020-01-01 00:00:01+00:00", 60.00094628179479, 11.5),
            ("2020-01-01 00:00:02+00:00", 60, 12),
        ]
        self.assertEqual(2, len(interpolated))
        for index in range(len(interpolated)):
            self.assertEqual(str(interpolated[index].time), expected[index][0])
            self.assertAlmostEqual(interpolated[index].latitude, expected[index][1])
            self.assertAlmostEqual(interpolated[index].longitude, expected[index][2])

    def test_interpolation_two_seconds_latitude(self, *args):
        processor = ContestantProcessor(self.contestant)
        start_position = ContestantReceivedPosition(
            contestant=self.contestant, time=dateutil.parser.parse("2020-01-01T00:00:00Z"), latitude=60, longitude=11
        )
        processor.previous_position = start_position
        next_position = ContestantReceivedPosition(
            contestant=self.contestant, time=dateutil.parser.parse("2020-01-01T00:00:02Z"), latitude=61, longitude=11
        )
        interpolated = processor.interpolate_track(start_position, next_position)
        expected = [
            ("2020-01-01 00:00:01+00:00", 60.5000188734541, 11),
            ("2020-01-01 00:00:02+00:00", 61, 11),
        ]
        self.assertEqual(2, len(interpolated))
        for index in range(len(interpolated)):
            self.assertEqual(str(interpolated[index].time), expected[index][0])
            self.assertAlmostEqual(interpolated[index].latitude, expected[index][1])
            self.assertAlmostEqual(interpolated[index].longitude, expected[index][2])

    def test_interpolation_close_positions(self, *args):
        processor = ContestantProcessor(self.contestant)
        start_position = ContestantReceivedPosition(
            contestant=self.contestant,
            time=dateutil.parser.parse("2020-01-01T00:00:00Z"),
            latitude=49.042362,
            longitude=21.042522,
        )
        processor.previous_position = start_position
        next_position = ContestantReceivedPosition(
            contestant=self.contestant,
            time=dateutil.parser.parse("2020-01-01T00:00:02Z"),
            latitude=49.043268,
            longitude=21.042285,
        )
        interpolated = processor.interpolate_track(start_position, next_position)
        expected = [
            ("2020-01-01 00:00:01+00:00", 49.042815000078704, 21.042403501076294),
            ("2020-01-01 00:00:02+00:00", 49.043268, 21.042285),
        ]
        self.assertEqual(2, len(interpolated))
        for index in range(len(interpolated)):
            self.assertEqual(str(interpolated[index].time), expected[index][0])
            self.assertAlmostEqual(interpolated[index].latitude, expected[index][1])
            self.assertAlmostEqual(interpolated[index].longitude, expected[index][2])


@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestCrossingEstimate(TransactionTestCase):
    @patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        from display.default_scorecards import default_scorecard_fai_precision_2020

        self.scorecard = default_scorecard_fai_precision_2020.get_default_scorecard()

        with open(NM_CSV_PATH, "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Test", file.readlines()[1:])
            self.route = editable_route.create_precision_route(True, self.scorecard)
        self.route.waypoints[1].time_check = False
        self.route.save()
        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        self.navigation_task = NavigationTask.create(
            name="NM navigation_task",
            route=self.route,
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
        start_time, speed = datetime.datetime(2020, 8, 1, 9, 15, tzinfo=datetime.timezone.utc), 70
        # Required to make the time zone save correctly
        self.navigation_task.refresh_from_db()
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

    def test_crossing_estimate(self, *args):
        gatekeeper = Gatekeeper(self.contestant, Queue(), [GateCalculator])
        # The SP gate is at lon 9.481223867089488. Correct direction is WEST (decreasing longitude).
        start_position = ContestantReceivedPosition(
            contestant=self.contestant,
            time=dateutil.parser.parse("2020-01-01T00:00:00Z"),
            latitude=59.19144317223039,
            longitude=9.481323867089488,
            speed=70,
            course=270,
        )
        next_position = ContestantReceivedPosition(
            contestant=self.contestant,
            time=dateutil.parser.parse("2020-01-01T00:00:02Z"),
            latitude=59.19144317223039,
            longitude=9.481123867089488,
            speed=70,
            course=270,
        )
        # Position after crossing starting line to trigger enroute estimation
        enroute_position = ContestantReceivedPosition(
            contestant=self.contestant,
            time=dateutil.parser.parse("2020-01-01T00:00:04Z"),
            latitude=59.19144317223039,
            longitude=9.481023867089488,
            speed=70,
            course=270,
        )
        enroute_position_2 = ContestantReceivedPosition(
            contestant=self.contestant,
            time=dateutil.parser.parse("2020-01-01T00:00:06Z"),
            latitude=59.19144317223039,
            longitude=9.480923867089488,
            speed=70,
            course=270,
        )
        gatekeeper.calculate_score(start_position)
        gatekeeper.calculate_score(next_position)
        gatekeeper.calculate_score(enroute_position)
        gatekeeper.calculate_score(enroute_position_2)
        # Verify state
        state = gatekeeper.get_state()
        self.assertIsNotNone(state.estimated_crossing_time)
