import datetime
import os
import threading
from multiprocessing import Queue
from pprint import pprint
from unittest.mock import patch, Mock

import dateutil.parser
from django.core.cache import cache
from django.test import TransactionTestCase

from display.calculators.anr_corridor_calculator import AnrCorridorCalculator
from display.calculators.backtracking_and_procedure_turns import BacktrackingAndProcedureTurnsCalculator
from display.calculators.calculator import GatekeeperState, FinishLinePassedEvent
from display.calculators.contestant_processor import ContestantProcessor
from display.calculators.gate_calculator import GateCalculator
from display.calculators.gatekeeper import Gatekeeper
from display.calculators.penalty_zone_calculator import PenaltyZoneCalculator
from display.calculators.prohibited_zone_calculator import ProhibitedZoneCalculator
from display.models import (
    Aeroplane,
    NavigationTask,
    Contest,
    Crew,
    Contestant,
    Person,
    Team,
    EditableRoute,
    ContestantTrack,
)
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.calculators.calculator_utilities import load_track_points_traccar_csv
from display.calculators.tests.utilities import load_traccar_track
from utilities.mock_utilities import TraccarMock
from redis_queue import RedisQueue

TEST_DATA_DIR = os.path.dirname(__file__)


def calculator_runner(contestant, track):
    processor = ContestantProcessor(contestant, live_processing=False)
    q = RedisQueue(contestant.pk)
    for i in track:
        # Construct the dict that Traccar normally returns
        data = {
            "id": 0,
            "deviceId": contestant.tracker_device_id,
            "attributes": {"course": i.get("course", 0), "batteryLevel": 100},
            "device_time": dateutil.parser.parse(i["time"]),
            "latitude": i["latitude"],
            "longitude": i["longitude"],
            "altitude": i.get("altitude", 0),
            "speed": i.get("speed", 0),
            "time": i["time"],
            "server_time": i["time"],
        }
        q.append(data)
    q.append(None)  # Signal end
    processor.run()


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestANRPerLeg(TransactionTestCase):
    @patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        cache.clear()
        from display.default_scorecards import default_scorecard_fai_anr_2017

        with open(os.path.join(TEST_DATA_DIR, "kjeller.kml"), "r") as file:
            with patch(
                "display.models.EditableRoute._create_route_and_thumbnail",
                lambda name, r: EditableRoute.objects.create(name=name, route=r),
            ):
                editable_route, _ = EditableRoute.create_from_kml("test", file)
                route = editable_route.create_anr_route(
                    False, 0.5, default_scorecard_fai_anr_2017.get_default_scorecard()
                )
        navigation_task_start_time = datetime.datetime(2021, 3, 15, 6, 0, 0, tzinfo=datetime.timezone.utc)
        navigation_task_finish_time = datetime.datetime(2021, 3, 15, 16, 0, 0, tzinfo=datetime.timezone.utc)
        self.aeroplane = Aeroplane.objects.create(registration="LN-YDB")

        self.navigation_task = NavigationTask.create(
            name="NM navigation_task",
            route=route,
            original_scorecard=default_scorecard_fai_anr_2017.get_default_scorecard(),
            contest=Contest.objects.create(
                name="contest_{}_{}".format(self.__class__.__name__, datetime.datetime.now().timestamp()),
                start_time=datetime.datetime.now(datetime.timezone.utc),
                finish_time=datetime.datetime.now(datetime.timezone.utc),
                time_zone="Europe/Oslo",
            ),
            start_time=navigation_task_start_time,
            finish_time=navigation_task_finish_time,
        )
        self.navigation_task.scorecard.corridor_maximum_penalty = 50
        self.navigation_task.scorecard.corridor_grace_time = 5
        self.navigation_task.scorecard.corridor_maximum_penalty_is_per_leg = True
        self.navigation_task.scorecard.save()
        crew = Crew.objects.create(
            member1=Person.objects.create(
                first_name="Mister",
                last_name="Pilot",
            )
        )
        self.team = Team.objects.create(crew=crew, aeroplane=self.aeroplane)

    def test_anr_score_per_leg(self, *args):
        track = load_track_points_traccar_csv(load_traccar_track(os.path.join(TEST_DATA_DIR, "kjeller_anr_bad.csv")))
        start_time, speed = (
            datetime.datetime(2021, 3, 15, 19, 30, tzinfo=datetime.timezone.utc),
            70,
        )
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=7,
            air_speed=speed,
            wind_direction=160,
            wind_speed=0,
        )
        calculator_runner(self.contestant, track)
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        strings = [item.string for item in self.contestant.scorelogentry_set.all().order_by("time", "pk")]
        pprint(strings)
        a = [
            "Takeoff 1: 0.0 points missing takeoff gate\nplanned: 20:30:00\nactual: --",
            "SP: 200.0 points passing gate (-367 s)\nplanned: 20:37:00\nactual: 20:30:53",
            "SP: 0.0 points exiting corridor",
            "SP: 50.0 points outside corridor (39 s) (capped)",
            "TP 1: 0.0 points passing gate (no time check) (-406 s)\n" + "planned: 20:39:00\n" + "actual: 20:32:14",
            "SP: 0.0 points exiting corridor",
            "SP: 200.0 points backtracking",
            "SP: 50.0 points outside corridor (116 s) (capped)",
            # "SP: 0.0 points exiting corridor",
            # "SP: 0.0 points outside corridor (0 s) (capped)",  # Missing TP 2
            # "SP: 0.0 points outside corridor (0 s)",  # Missing TP 3
            # "SP: 0.0 points outside corridor (0 s)",  # Missing FP
            "FP: 200.0 points passing gate (-780 s)\nplanned: 20:48:11\nactual: 20:35:11",
            "Landing 1: 0.0 points missing landing gate\nplanned: 22:29:00\nactual: --",
        ]

        self.assertListEqual(a, strings)
        self.assertEqual(700.0, contestant_track.score)

    def test_anr_score_per_leg_enabled(self, *args):
        # This test validates that when per-leg scoring is ON, the maximum penalty applies to each leg individually.
        track = load_track_points_traccar_csv(load_traccar_track(os.path.join(TEST_DATA_DIR, "kjeller_anr_bad.csv")))
        start_time, speed = (
            datetime.datetime(2021, 3, 15, 19, 30, tzinfo=datetime.timezone.utc),
            70,
        )
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=7,
            air_speed=speed,
            wind_direction=160,
            wind_speed=0,
        )
        # Enable per-leg maximum penalty
        self.navigation_task.scorecard.corridor_maximum_penalty_is_per_leg = True
        self.navigation_task.scorecard.save()

        calculator_runner(self.contestant, track)

        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        strings = [item.string for item in self.contestant.scorelogentry_set.all().order_by("time", "pk")]

        # Count how many times we got a 50 point capped penalty
        capped_50_penalties = [s for s in strings if "SP: 50.0 points outside corridor" in s and "(capped)" in s]
        self.assertEqual(len(capped_50_penalties), 2)

        # Verify total score
        contestant_track.refresh_from_db()
        self.assertEqual(700.0, contestant_track.score)

    def test_anr_miss_multiple_finish(self, *args):
        track = load_track_points_traccar_csv(
            load_traccar_track(os.path.join(TEST_DATA_DIR, "anr_miss_multiple_finish.csv"))
        )
        start_time, speed = datetime.datetime(2023, 6, 22, 12, tzinfo=datetime.timezone.utc), 70
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=7,
            air_speed=speed,
            wind_direction=160,
            wind_speed=0,
        )
        # Ensure per-leg is ON for this test context
        self.navigation_task.scorecard.corridor_maximum_penalty_is_per_leg = True
        self.navigation_task.scorecard.save()

        calculator_runner(self.contestant, track)
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        strings = [item.string for item in self.contestant.scorelogentry_set.all().order_by("time", "pk")]
        pprint(strings)
        final_list = [
            "Takeoff 1: 0.0 points missing takeoff gate\nplanned: 14:00:00\nactual: --",
            "SP: 200.0 points passing gate (-71535748 s)\nplanned: 14:07:00\nactual: 14:04:32",
            "SP: 0.0 points exiting corridor",
            "SP: 48.0 points outside corridor (21 s)",
            # "SP: 0.0 points exiting corridor", # Is new leg
            "SP: 9.0 points outside corridor (3 s)",
            "SP: 0.0 points exiting corridor",
            "SP: 200.0 points backtracking",
            "SP: 41.0 points outside corridor (228 s) (capped)",  # Missed TP 2
            "SP: 0.0 points outside corridor (0 s)",  # Missed TP 3, but already at maximum penalty, so no additional points
            "SP: 0.0 points outside corridor (0 s)",  # Missed FP, but already at maximum penalty, so no additional points
            "FP: 200.0 points missing gate\nplanned: 14:18:11\nactual: --",
            "Landing 1: 0.0 points missing landing gate\nplanned: 15:59:00\nactual: --",
        ]
        self.assertListEqual(
            final_list,
            strings,
        )
        self.assertEqual(698.0, contestant_track.score)

    def test_manually_terminate_calculator(self, *args):
        cache.clear()
        track = load_track_points_traccar_csv(
            load_traccar_track(os.path.join(TEST_DATA_DIR, "anr_miss_multiple_finish.csv"))
        )
        start_time, speed = datetime.datetime.now(datetime.timezone.utc), 70
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=7,
            air_speed=speed,
            wind_direction=160,
            wind_speed=0,
        )
        q = RedisQueue(self.contestant.pk)
        contestant_processor = ContestantProcessor(self.contestant, live_processing=True)
        for i in track:
            # Construct dict
            data = {
                "id": 0,
                "deviceId": self.contestant.tracker_device_id,
                "attributes": {},
                "device_time": dateutil.parser.parse(i["time"]),
                "latitude": i["latitude"],
                "longitude": i["longitude"],
                "altitude": i.get("altitude", 0),
                "speed": i.get("speed", 0),
                "time": i["time"],
                "server_time": i["time"],
            }
            q.append(data)
        threading.Timer(0.1, lambda: self.contestant.request_calculator_termination()).start()
        contestant_processor.run()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        strings = [item.string for item in self.contestant.scorelogentry_set.all().order_by("time", "pk")]

        print(strings)
        self.assertTrue(any("manually terminated" in e for e in strings))

        # Verify the time matches the request time (roughly, since we use a timer)
        entry = self.contestant.scorelogentry_set.get(message="manually terminated")
        self.assertGreater(entry.time, start_time - datetime.timedelta(minutes=1))

    def test_anr_miss_start_and_finish(self, *args):
        track = load_track_points_traccar_csv(
            load_traccar_track(os.path.join(TEST_DATA_DIR, "anr_miss_start_and_finish.csv"))
        )
        start_time, speed = (
            datetime.datetime(2021, 3, 16, 14, 5, tzinfo=datetime.timezone.utc),
            70,
        )
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=7,
            adaptive_start=True,
            air_speed=speed,
            wind_direction=160,
            wind_speed=0,
        )
        calculator_runner(self.contestant, track)
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        strings = [item.string for item in self.contestant.scorelogentry_set.all().order_by("time", "pk")]
        pprint(strings)
        expected = [
            "Takeoff 1: 0.0 points missing takeoff gate\nplanned: 15:05:00\nactual: --",
            "SP: 0.0 points crossing infinite starting line and starting adaptive timing",
            "SP: 9.0 points passing gate (+4 s)\nplanned: 14:17:00\nactual: 14:17:04",
            "TP 1: 0.0 points passing gate (no time check) (-57 s)\nplanned: 14:19:00\nactual: 14:18:03",
            "TP 2: 0.0 points passing gate (no time check) (-168 s)\nplanned: 14:22:34\nactual: 14:19:46",
            "TP 3: 0.0 points passing gate (no time check) (-221 s)\nplanned: 14:24:32\nactual: 14:20:51",
            # "SP: 0.0 points exiting corridor",
            # "SP: 0.0 points outside corridor (0 s)",  # Missing FP
            "FP: 200.0 points passing gate (-320 s)\nplanned: 14:28:10\nactual: 14:22:51",
            "Landing 1: 0.0 points missing landing gate\nplanned: 17:04:00\nactual: --",
        ]
        self.assertListEqual(expected, strings)
        self.assertEqual(209.0, contestant_track.score)


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestANR(TransactionTestCase):
    @patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        cache.clear()
        from display.default_scorecards import default_scorecard_fai_anr_2017

        with open(os.path.join(TEST_DATA_DIR, "eidsvoll.kml"), "r") as file:
            with patch(
                "display.models.EditableRoute._create_route_and_thumbnail",
                lambda name, r: EditableRoute.objects.create(name=name, route=r),
            ):
                editable_route, _ = EditableRoute.create_from_kml("test", file)
                route = editable_route.create_anr_route(
                    False, 0.5, default_scorecard_fai_anr_2017.get_default_scorecard()
                )
        navigation_task_start_time = datetime.datetime(2021, 1, 27, 6, 0, 0, tzinfo=datetime.timezone.utc)
        navigation_task_finish_time = datetime.datetime(2021, 1, 27, 16, 0, 0, tzinfo=datetime.timezone.utc)
        self.aeroplane = Aeroplane.objects.create(registration="LN-YDB")

        self.navigation_task = NavigationTask.create(
            name="NM navigation_task",
            route=route,
            original_scorecard=default_scorecard_fai_anr_2017.get_default_scorecard(),
            contest=Contest.objects.create(
                name="contest_{}_{}".format(self.__class__.__name__, datetime.datetime.now().timestamp()),
                start_time=datetime.datetime.now(datetime.timezone.utc),
                finish_time=datetime.datetime.now(datetime.timezone.utc),
                time_zone="Europe/Oslo",
            ),
            start_time=navigation_task_start_time,
            finish_time=navigation_task_finish_time,
        )
        self.navigation_task.scorecard.corridor_grace_time = 5
        self.navigation_task.scorecard.corridor_maximum_penalty_is_per_leg = False
        self.navigation_task.scorecard.save()
        crew = Crew.objects.create(
            member1=Person.objects.create(
                first_name="Mister",
                last_name="Pilot",
            )
        )
        self.team = Team.objects.create(crew=crew, aeroplane=self.aeroplane)

    def test_track(self, *args):
        track = load_track_points_traccar_csv(
            load_traccar_track(os.path.join(TEST_DATA_DIR, "kolaf_eidsvoll_traccar.csv"))
        )
        start_time, speed = (
            datetime.datetime(2021, 1, 27, 6, 45, tzinfo=datetime.timezone.utc),
            40,
        )
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=7,
            air_speed=speed,
            wind_direction=160,
            wind_speed=0,
        )
        calculator_runner(self.contestant, track)
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        # Verify score is correct
        self.assertEqual(476.0, contestant_track.score)

    def test_track_adaptive_start(self, *args):
        track = load_track_points_traccar_csv(
            load_traccar_track(os.path.join(TEST_DATA_DIR, "kolaf_eidsvoll_traccar.csv"))
        )
        start_time, speed = (
            datetime.datetime(2021, 1, 27, 6, 45, tzinfo=datetime.timezone.utc),
            40,
        )
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=7,
            air_speed=speed,
            adaptive_start=True,
            wind_direction=160,
            wind_speed=0,
        )
        calculator_runner(self.contestant, track)
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        # Verify score is correct
        self.assertEqual(458.0, contestant_track.score)


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestAnrCorridorCalculator(TransactionTestCase):
    @patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        from display.default_scorecards import default_scorecard_fai_anr_2017

        with open(os.path.join(TEST_DATA_DIR, "kjeller.kml"), "r") as file:
            with patch(
                "display.models.EditableRoute._create_route_and_thumbnail",
                lambda name, r: EditableRoute.objects.create(name=name, route=r),
            ):
                editable_route, _ = EditableRoute.create_from_kml("test", file)
                self.route = editable_route.create_anr_route(
                    False, 0.5, default_scorecard_fai_anr_2017.get_default_scorecard()
                )
        navigation_task_start_time = datetime.datetime(2021, 1, 27, 6, 0, 0, tzinfo=datetime.timezone.utc)
        navigation_task_finish_time = datetime.datetime(2021, 1, 27, 16, 0, 0, tzinfo=datetime.timezone.utc)
        self.aeroplane = Aeroplane.objects.create(registration="LN-YDB")

        self.navigation_task = NavigationTask.create(
            name="NM navigation_task",
            route=self.route,
            original_scorecard=default_scorecard_fai_anr_2017.get_default_scorecard(),
            contest=Contest.objects.create(
                name="contest",
                start_time=datetime.datetime.now(datetime.timezone.utc),
                finish_time=datetime.datetime.now(datetime.timezone.utc),
                time_zone="Europe/Oslo",
            ),
            start_time=navigation_task_start_time,
            finish_time=navigation_task_finish_time,
        )
        self.navigation_task.scorecard.corridor_grace_time = 5
        self.navigation_task.scorecard.corridor_maximum_penalty_is_per_leg = False
        self.navigation_task.scorecard.save()
        crew = Crew.objects.create(
            member1=Person.objects.create(
                first_name="Mister",
                last_name="Pilot",
            )
        )
        self.team = Team.objects.create(crew=crew, aeroplane=self.aeroplane)
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=datetime.datetime.now(datetime.timezone.utc),
            finished_by_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2),
            tracker_start_time=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=30),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=7,
            air_speed=70,
            wind_direction=160,
            wind_speed=0,
        )
        self.calculator = AnrCorridorCalculator(
            self.contestant,
            self.navigation_task.scorecard,
            self.route.waypoints,
            self.route,
            Queue(),
        )
        self.calculator.enroute = True
        self.calculator.update_score = Mock()

    def test_inside_enroute(self, *args):
        position = Mock()
        position.latitude = 59.939
        position.longitude = 11.062
        position.time = datetime.datetime(2020, 1, 1, 0, 0)
        from display.calculators.calculator import GatekeeperState

        state = GatekeeperState(
            last_gate=None,
            outstanding_gates=self.route.waypoints,
            in_range_of_gate=None,
            projector=None,
            takeoff_gate=None,
            landing_gate=None,
            has_passed_finishpoint=False,
            recalculation_completed=True,
            estimated_next_timed_gate=None,
            estimated_crossing_time=None,
        )

        self.calculator.calculate_enroute([position], state)
        self.calculator.update_score.assert_not_called()

    def test_outside_enroute(self, *args):
        position = Mock()
        position.latitude = 60.5
        position.longitude = 11
        position.time = datetime.datetime(2020, 1, 1, 0, 0)
        from display.calculators.calculator import GatekeeperState

        state = GatekeeperState(
            last_gate=None,
            outstanding_gates=self.route.waypoints,
            in_range_of_gate=None,
            projector=None,
            takeoff_gate=None,
            landing_gate=None,
            has_passed_finishpoint=False,
            recalculation_completed=True,
            estimated_next_timed_gate=None,
            estimated_crossing_time=None,
        )

        self.calculator.calculate_enroute([position], state)
        self.calculator.update_score.assert_called_once()
        call = self.calculator.update_score.call_args.args[0]
        self.assertEqual(call.time, datetime.datetime(2020, 1, 1, 0, 0))
        self.assertEqual(call.message, "exiting corridor")
        self.assertEqual(call.score, 0)

    def test_outside_2_seconds_enroute(self, *args):
        position = Mock()
        position.latitude = 60.5
        position.longitude = 11
        position.time = datetime.datetime(2020, 1, 1, 0, 0)
        position2 = Mock()
        position2.latitude = 60.5
        position2.longitude = 11
        position2.time = datetime.datetime(2020, 1, 1, 0, 0, 1)
        position3 = Mock()
        position3.latitude = 59.939
        position3.longitude = 11.062
        position3.time = datetime.datetime(2020, 1, 1, 0, 0, 3)

        gate = Mock()
        from display.calculators.calculator import GatekeeperState

        state = GatekeeperState(
            last_gate=None,
            outstanding_gates=self.route.waypoints,
            in_range_of_gate=None,
            projector=None,
            takeoff_gate=None,
            landing_gate=None,
            has_passed_finishpoint=False,
            recalculation_completed=True,
            estimated_next_timed_gate=None,
            estimated_crossing_time=None,
        )

        self.calculator.calculate_enroute([position], state)
        self.calculator.calculate_enroute([position, position2], state)
        self.calculator.calculate_enroute([position, position2, position3], state)

        # Verify calls manually
        calls = [c.args[0] for c in self.calculator.update_score.call_args_list]
        self.assertEqual(len(calls), 2)

        self.assertEqual(calls[0].time, datetime.datetime(2020, 1, 1, 0, 0))
        self.assertEqual(calls[0].message, "exiting corridor")
        self.assertEqual(calls[0].score, 0)
        self.assertEqual(calls[0].score_type, "outside_corridor")

        # Returned inside at 00:03, so finalized at 00:02
        self.assertEqual(calls[1].time, datetime.datetime(2020, 1, 1, 0, 0, 2))
        self.assertEqual(calls[1].message, "outside corridor (2 s)")
        self.assertEqual(calls[1].score, 0)
        self.assertEqual(calls[1].score_type, "outside_corridor")

    def test_outside_20_seconds_enroute(self, *args):
        position = Mock()
        position.latitude = 60.5
        position.longitude = 11
        position.time = datetime.datetime(2020, 1, 1, 0, 0)
        position2 = Mock()
        position2.latitude = 60.5
        position2.longitude = 11
        position2.time = datetime.datetime(2020, 1, 1, 0, 0, 20)
        position3 = Mock()
        position3.latitude = 59.939
        position3.longitude = 11.062
        position3.time = datetime.datetime(2020, 1, 1, 0, 0, 21)

        gate = Mock()
        from display.calculators.calculator import GatekeeperState

        state = GatekeeperState(
            last_gate=None,
            outstanding_gates=self.route.waypoints,
            in_range_of_gate=None,
            projector=None,
            takeoff_gate=None,
            landing_gate=None,
            has_passed_finishpoint=False,
            recalculation_completed=True,
            estimated_next_timed_gate=None,
            estimated_crossing_time=None,
        )

        self.calculator.calculate_enroute([position], state)
        # Position 2 at T=20 keeps it outside
        self.calculator.calculate_enroute([position, position2], state)
        # Position 3 at T=21 brings it inside, finalizes at T=20
        self.calculator.calculate_enroute([position, position2, position3], state)

        # Verify calls manually
        calls = [c.args[0] for c in self.calculator.update_score.call_args_list]
        self.assertEqual(len(calls), 2)

        self.assertEqual(calls[0].time, datetime.datetime(2020, 1, 1, 0, 0))
        self.assertEqual(calls[0].message, "exiting corridor")
        self.assertEqual(calls[0].score, 0)

        # Finalized at T=20
        self.assertEqual(calls[1].time, datetime.datetime(2020, 1, 1, 0, 0, 20))
        self.assertEqual(calls[1].message, "outside corridor (20 s)")
        self.assertEqual(calls[1].score, 45.0)

    def test_outside_20_seconds_until_finish(self, *args):
        position = Mock()
        position.latitude = 60.5
        position.longitude = 11
        position.time = datetime.datetime(2020, 1, 1, 0, 0)
        position2 = Mock()
        position2.latitude = 60.5
        position2.longitude = 11
        position2.time = datetime.datetime(2020, 1, 1, 0, 0, 1)
        position3 = Mock()
        position3.latitude = 59.939
        position3.longitude = 11.062
        position3.time = datetime.datetime(2020, 1, 1, 0, 0, 21)

        from display.calculators.calculator import GatekeeperState, FinishLinePassedEvent

        state = GatekeeperState(
            last_gate=None,
            outstanding_gates=self.route.waypoints,
            in_range_of_gate=None,
            projector=None,
            takeoff_gate=None,
            landing_gate=None,
            has_passed_finishpoint=False,
            recalculation_completed=True,
            estimated_next_timed_gate=None,
            estimated_crossing_time=None,
        )

        self.calculator.calculate_enroute([position], state)
        self.calculator.calculate_enroute([position, position2], state)
        # Passed finish line at 00:20
        self.calculator.passed_finishpoint(
            FinishLinePassedEvent(None, [position3], event_time=datetime.datetime(2020, 1, 1, 0, 0, 20))
        )

        calls = [c.args[0] for c in self.calculator.update_score.call_args_list]
        self.assertEqual(len(calls), 2)

        self.assertEqual(calls[0].message, "exiting corridor")
        self.assertEqual(calls[0].score, 0)

        self.assertEqual(calls[1].time, datetime.datetime(2020, 1, 1, 0, 0, 20))
        self.assertEqual(calls[1].message, "outside corridor (20 s)")
        self.assertEqual(calls[1].score, 45.0)

    def test_outside_20_seconds_outside_route(self, *args):
        position = Mock()
        position.latitude = 60.5
        position.longitude = 11
        position.time = datetime.datetime(2020, 1, 1, 0, 0)
        position2 = Mock()
        position2.latitude = 60.5
        position2.longitude = 11
        position2.time = datetime.datetime(2020, 1, 1, 0, 0, 1)
        position3 = Mock()
        position3.latitude = 59.939
        position3.longitude = 11.062
        position3.time = datetime.datetime(2020, 1, 1, 0, 0, 21)

        from display.calculators.calculator import GatekeeperState

        state = GatekeeperState(
            last_gate=None,
            outstanding_gates=self.route.waypoints,
            in_range_of_gate=None,
            projector=None,
            takeoff_gate=None,
            landing_gate=None,
            has_passed_finishpoint=False,
            recalculation_completed=True,
            estimated_next_timed_gate=None,
            estimated_crossing_time=None,
        )

        self.calculator.calculate_enroute([position], state)
        self.calculator.calculate_enroute([position, position2], state)
        self.calculator.calculate_outside_route([position, position2, position3], state)

        calls = [c.args[0] for c in self.calculator.update_score.call_args_list]
        self.assertEqual(len(calls), 1)

        self.assertEqual(calls[0].message, "exiting corridor")
        self.assertEqual(calls[0].score, 0)


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestANRBergenBacktrackingTommy(TransactionTestCase):
    @patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        from display.default_scorecards import default_scorecard_fai_anr_2017

        with open(os.path.join(TEST_DATA_DIR, "tommy_test.kml"), "r") as file:
            with patch(
                "display.models.EditableRoute._create_route_and_thumbnail",
                lambda name, r: EditableRoute.objects.create(name=name, route=r),
            ):
                editable_route, _ = EditableRoute.create_from_kml("test", file)
                route = editable_route.create_anr_route(
                    False, 0.5, default_scorecard_fai_anr_2017.get_default_scorecard()
                )
        navigation_task_start_time = datetime.datetime(2021, 3, 31, 6, 0, 0, tzinfo=datetime.timezone.utc)
        navigation_task_finish_time = datetime.datetime(2021, 3, 31, 16, 0, 0, tzinfo=datetime.timezone.utc)
        self.aeroplane = Aeroplane.objects.create(registration="LN-YDB")

        self.navigation_task = NavigationTask.create(
            name="NM navigation_task",
            route=route,
            original_scorecard=default_scorecard_fai_anr_2017.get_default_scorecard(),
            contest=Contest.objects.create(
                name="contest_{}_{}".format(self.__class__.__name__, datetime.datetime.now().timestamp()),
                start_time=datetime.datetime.now(datetime.timezone.utc),
                finish_time=datetime.datetime.now(datetime.timezone.utc),
                time_zone="Europe/Oslo",
            ),
            start_time=navigation_task_start_time,
            finish_time=navigation_task_finish_time,
        )
        self.navigation_task.scorecard.corridor_grace_time = 5
        self.navigation_task.scorecard.corridor_maximum_penalty_is_per_leg = True
        self.navigation_task.scorecard.save()
        crew = Crew.objects.create(
            member1=Person.objects.create(
                first_name="Mister",
                last_name="Pilot",
            )
        )
        self.team = Team.objects.create(crew=crew, aeroplane=self.aeroplane)

    def test_track(self, *args):
        track = load_track_points_traccar_csv(
            load_traccar_track(os.path.join(TEST_DATA_DIR, "tommy_missing_circling_penalty.csv"))
        )
        start_time, speed = (
            datetime.datetime(2021, 3, 31, 11, 45, tzinfo=datetime.timezone.utc),
            70,
        )
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=7,
            air_speed=speed,
            adaptive_start=False,
            wind_direction=160,
            wind_speed=0,
        )
        calculator_runner(self.contestant, track)
        expected_strings = [
            "SP: 200.0 points entered prohibited zone enbr",
            "SP: 200.0 points passing gate (-407 s)\nplanned: 13:52:00\nactual: 13:45:13",
            "SP: 0.0 points exiting corridor",
            "SP: 102.0 points outside corridor (39 s)",
            "TP 1: 0.0 points passing gate (no time check) (-337 s)\nplanned: 13:54:41\nactual: 13:49:04",
            "TP 2: 0.0 points passing gate (no time check) (-324 s)\nplanned: 13:57:39\nactual: 13:52:15",
            "TP 3: 0.0 points passing gate (no time check) (-307 s)\nplanned: 13:59:26\nactual: 13:54:19",
            "TP 4: 0.0 points passing gate (no time check) (-296 s)\nplanned: 14:03:46\nactual: 13:58:50",
            "FP: 200.0 points missing gate\nplanned: 14:17:24\nactual: --",
        ]
        strings = [item.string for item in self.contestant.scorelogentry_set.all().order_by("time", "pk")]
        print(strings)
        self.assertListEqual(expected_strings, strings)
        self.contestant.contestanttrack.refresh_from_db()
        # 200 (Zone) + 200 (SP) + 102 (Corridor) + 200 (FP) = 702
        self.assertEqual(702.0, self.contestant.contestanttrack.score)
