import os
import datetime
from pprint import pprint
from unittest.mock import patch

import dateutil
import gpxpy

from django.test import TransactionTestCase

from display.calculators.calculator_utilities import load_track_points_traccar_csv
from display.calculators.contestant_processor import ContestantProcessor
from display.calculators.positions_and_gates import Gate
from display.calculators.tests.utilities import load_traccar_track
from display.utilities.route_building_utilities import (
    create_precision_route_from_gpx,
    calculate_extended_gate,
)
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
    ScoreLogEntry,
)
from utilities.mock_utilities import TraccarMock
from redis_queue import RedisQueue

TEST_DATA_DIR = os.path.dirname(__file__)


def calculator_runner(contestant, track):
    q = RedisQueue(contestant.pk)
    contestant_processor = ContestantProcessor(contestant, live_processing=False)
    for i in track:
        i["id"] = 0
        i["deviceId"] = ""
        i["attributes"] = {}
        i["device_time"] = dateutil.parser.parse(i["time"])
        q.append(i)
    q.append(None)
    contestant_processor.run()
    while not q.empty():
        q.pop()


def load_track_points(filename):
    with open(filename, "r") as i:
        gpx = gpxpy.parse(i)
    positions = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                positions.append(
                    {
                        "time": point.time.isoformat(),
                        "latitude": point.latitude,
                        "longitude": point.longitude,
                        "altitude": point.elevation if point.elevation else 0,
                        "speed": 0,
                        "course": 0,
                        "battery_level": 100,
                    }
                )
    return positions


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.WebsocketFacade")
@patch("display.calculators.orchestrator.WebsocketFacade")
@patch("display.calculators.gate_calculator.WebsocketFacade")
class TestFullTrack(TransactionTestCase):
    @patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        from display.default_scorecards import default_scorecard_fai_precision_2020

        self.scorecard = default_scorecard_fai_precision_2020.get_default_scorecard()
        with open(os.path.join(TEST_DATA_DIR, "NM.csv"), "r") as file:
            with patch(
                "display.models.EditableRoute._create_route_and_thumbnail",
                lambda name, r: EditableRoute.objects.create(name=name, route=r),
            ):
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
                name="contest_{}_{}".format(self.__class__.__name__, datetime.datetime.now().timestamp()),
                start_time=datetime.datetime.now(datetime.timezone.utc),
                finish_time=datetime.datetime.now(datetime.timezone.utc),
                time_zone="Europe/Oslo",
            ),
            start_time=navigation_task_start_time,
            finish_time=navigation_task_finish_time,
        )
        crew = Crew.objects.create(
            member1=Person.objects.create(
                first_name="Mister",
                last_name="Pilot",
                email="mister_{}_{}@pilot.com".format(self.__class__.__name__, datetime.datetime.now().timestamp()),
            )
        )
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

    def test_team_test_score_updated(self, *args):
        self.contestant.contestanttrack.update_score(23)
        team_test_score = TeamTestScore.objects.get(team=self.team, task_test__navigation_task=self.navigation_task)
        self.assertEqual(23, team_test_score.points)

    def test_correct_scoring_correct_track_precision(self, *args):
        positions = load_track_points(os.path.join(TEST_DATA_DIR, "test_contestant_correct_track.gpx"))
        calculator_runner(self.contestant, positions)
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(222, contestant_track.score)  # 150.0,

    def test_secret_score_no_override(self, *args):
        expected_time = datetime.datetime(2017, 1, 1, tzinfo=datetime.timezone.utc)
        actual_time = datetime.datetime(2017, 1, 1, 0, 1, tzinfo=datetime.timezone.utc)
        waypoint = self.contestant.navigation_task.route.waypoints[1]
        gate = Gate(waypoint, expected_time, calculate_extended_gate(waypoint, self.scorecard))  # SC 1/1
        self.assertEqual("secret", gate.type)
        gate.passing_time = actual_time
        score = self.scorecard.get_gate_timing_score_for_gate_type(gate.type, gate.expected_time, gate.passing_time)
        print([str(item) for item in self.navigation_task.route.waypoints])
        self.assertEqual(100, score)

    def test_helge_track_precision(self, *args):
        start_time, speed = datetime.datetime(2020, 8, 1, 10, 55, tzinfo=datetime.timezone.utc), 75
        crew = Crew.objects.create(
            member1=Person.objects.create(first_name="Misters", last_name="Pilot", email="a@gg.com")
        )
        aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        team = Team.objects.create(crew=crew, aeroplane=aeroplane)

        contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="contestant",
            contestant_number=2,
            minutes_to_starting_point=6,
            air_speed=speed,
            wind_direction=165,
            wind_speed=8,
        )
        positions = load_track_points(os.path.join(TEST_DATA_DIR, "Helge.gpx"))
        calculator_runner(contestant, positions)
        contestant_track = ContestantTrack.objects.get(contestant=contestant)
        self.assertEqual(327, contestant_track.score)

    def test_correct_scoring_bad_track_precision(self, *args):
        positions = load_track_points(os.path.join(TEST_DATA_DIR, "Steinar.gpx"))
        calculator_runner(self.contestant, positions)
        # TODO: Should be 1800?
        strings = [item.string for item in self.contestant.scorelogentry_set.all().order_by("time", "pk")]
        for s in strings:
            print(s)
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(2000.0, contestant_track.score)

    def test_missed_procedure_turn(self, *args):
        positions = load_track_points(os.path.join(TEST_DATA_DIR, "jorgen_missed_procedure_turn.gpx"))
        calculator_runner(self.contestant, positions)
        # expected_strings = []
        strings = [
            item.string for item in ScoreLogEntry.objects.filter(contestant=self.contestant).order_by("time", "pk")
        ]
        # print(strings)
        # self.assertListEqual(expected_strings, strings)
        self.assertTrue("TP1: 200.0 points incorrect procedure turn" in strings)
        self.assertTrue("TP4: 200.0 points incorrect procedure turn" in strings)
        # This is a bit in question, but I think it is correct since he never crosses the extended gate line
        # The procedure turn is performed before the gate which causes backtracking, but also a miss
        # According to A.2.2.16 the should be no penalty for missing the procedure turn if the extended gate line
        # is not crossed.
        # self.assertTrue("TP6: 200 points missing procedure turn" in strings)
        self.assertFalse("TP6: 200.0 points missing procedure turn" in strings)


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class Test2017WPFC(TransactionTestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        with open(
            os.path.join(TEST_DATA_DIR, "..", "..", "tests/demo_contests/2017_WPFC/Route-1-Blue.gpx"), "r"
        ) as file:
            route = create_precision_route_from_gpx(file, True)
        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        self.aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        from display.default_scorecards import default_scorecard_fai_precision_2020

        self.navigation_task = NavigationTask.create(
            name="NM navigation_task",
            route=route,
            original_scorecard=default_scorecard_fai_precision_2020.get_default_scorecard(),
            contest=Contest.objects.create(
                name="contest",
                start_time=datetime.datetime.now(datetime.timezone.utc),
                finish_time=datetime.datetime.now(datetime.timezone.utc),
                time_zone="Europe/Oslo",
            ),
            start_time=navigation_task_start_time,
            finish_time=navigation_task_finish_time,
        )
        crew = Crew.objects.create(
            member1=Person.objects.create(
                first_name="Mister",
                last_name="Pilot",
                email="mister_{}_{}@pilot.com".format(self.__class__.__name__, datetime.datetime.now().timestamp()),
            )
        )
        self.team = Team.objects.create(crew=crew, aeroplane=self.aeroplane)
        self.scorecard = default_scorecard_fai_precision_2020.get_default_scorecard()
        # Required to make the time zone save correctly
        self.navigation_task.refresh_from_db()

    def test_101(self, *args):
        track = load_track_points(
            os.path.join(
                TEST_DATA_DIR,
                "..",
                "..",
                "tests/demo_contests/2017_WPFC/101_-_Aircraft-039_-_1._Nav._-_Navigation_Flight_Results_(Edition_2).gpx",
            )
        )
        start_time, speed = datetime.datetime(2015, 1, 1, 7, 30, tzinfo=datetime.timezone.utc), 80
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=8,
            air_speed=speed,
            wind_direction=160,
            wind_speed=18,
        )
        calculator_runner(self.contestant, track)
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        expected_strings = [
            "T/O: 0.0 points passing takeoff gate (+28 s)\nplanned: 08:30:00\nactual: 08:30:28",
            "SP: 15.0 points passing gate (+7 s)\nplanned: 08:38:00\nactual: 08:38:07",
            "SC1: 9.0 points passing gate (-5 s)\nplanned: 08:40:30\nactual: 08:40:25",
            "TP1: 21.0 points passing gate (-9 s)\nplanned: 08:42:17\nactual: 08:42:08",
            "TP1: 200.0 points backtracking",
            "SC2: 100.0 points missing gate\nplanned: 08:44:21\nactual: --",
            "SC3: 100.0 points passing gate (+41 s)\nplanned: 08:47:57\nactual: 08:48:38",
            "TP2: 100.0 points missing gate\nplanned: 08:48:58\nactual: --",
            "SC4: 100.0 points missing gate\nplanned: 08:49:26\nactual: --",
            "SC5: 75.0 points passing gate (+27 s)\nplanned: 08:52:45\nactual: 08:53:12",
            "SC6: 3.0 points passing gate (-3 s)\nplanned: 08:55:39\nactual: 08:55:36",
            "TP3: 0.0 points passing gate (0 s)\nplanned: 08:57:11\nactual: 08:57:11",
            "SC7: 6.0 points passing gate (-4 s)\nplanned: 09:02:07\nactual: 09:02:03",
            "SC8: 15.0 points passing gate (-7 s)\nplanned: 09:04:52\nactual: 09:04:45",
            "TP4: 3.0 points passing gate (-3 s)\nplanned: 09:10:20\nactual: 09:10:17",
            "SC9: 45.0 points passing gate (+17 s)\nplanned: 09:14:06\nactual: 09:14:23",
            "SC10: 36.0 points passing gate (+14 s)\nplanned: 09:16:22\nactual: 09:16:36",
            "TP5: 30.0 points passing gate (+12 s)\nplanned: 09:21:04\nactual: 09:21:16",
            "SC11: 33.0 points passing gate (+13 s)\nplanned: 09:23:40\nactual: 09:23:53",
            "TP6: 21.0 points passing gate (+9 s)\nplanned: 09:27:49\nactual: 09:27:58",
            "SC12: 33.0 points passing gate (+13 s)\nplanned: 09:33:54\nactual: 09:34:07",
            "SC13: 57.0 points passing gate (+21 s)\nplanned: 09:37:49\nactual: 09:38:10",
            "TP7: 30.0 points passing gate (+12 s)\nplanned: 09:38:47\nactual: 09:38:59",
            "SC14: 15.0 points passing gate (+7 s)\nplanned: 09:41:46\nactual: 09:41:53",
            "FP: 18.0 points passing gate (+8 s)\nplanned: 09:46:03\nactual: 09:46:11",
            "LDG: 0.0 points passed landing gate (-2300 s)\nplanned: 10:29:00\nactual: 09:50:40",
            "LDG: 0.0 points passed landing line",
        ]
        strings = [
            item.string for item in ScoreLogEntry.objects.filter(contestant=self.contestant).order_by("time", "pk")
        ]
        self.assertListEqual(expected_strings, strings)
        self.assertEqual(
            1065, contestant_track.score
        )


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestNM2019(TransactionTestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        from display.default_scorecards import default_scorecard_fai_precision_2020

        self.scorecard = default_scorecard_fai_precision_2020.get_default_scorecard()
        with open(os.path.join(TEST_DATA_DIR, "NM2019.gpx"), "r") as file:
            with patch(
                "display.models.EditableRoute._create_route_and_thumbnail",
                lambda name, r: EditableRoute.objects.create(name=name, route=r),
            ):
                editable_route, _ = EditableRoute.create_from_gpx("Test", file.read().encode("utf-8"))
                route = editable_route.create_precision_route(True, self.scorecard)
        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        self.aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        self.navigation_task = NavigationTask.create(
            name="NM navigation_task",
            route=route,
            original_scorecard=self.scorecard,
            contest=Contest.objects.create(
                name="contest_{}_{}".format(self.__class__.__name__, datetime.datetime.now().timestamp()),
                start_time=datetime.datetime.now(datetime.timezone.utc),
                finish_time=datetime.datetime.now(datetime.timezone.utc),
                time_zone="Europe/Oslo",
            ),
            start_time=navigation_task_start_time,
            finish_time=navigation_task_finish_time,
        )
        crew = Crew.objects.create(
            member1=Person.objects.create(
                first_name="Mister",
                last_name="Pilot",
                email="mister_{}_{}@pilot.com".format(self.__class__.__name__, datetime.datetime.now().timestamp()),
            )
        )
        self.team = Team.objects.create(crew=crew, aeroplane=self.aeroplane)
        # Required to make the time zone save correctly
        self.navigation_task.refresh_from_db()

    def test_arild(self, *args):
        track = load_track_points(os.path.join(TEST_DATA_DIR, "arild2019.gpx"))
        start_time, speed = datetime.datetime(2015, 1, 1, 14, 25, tzinfo=datetime.timezone.utc), 54
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=speed,
            wind_direction=220,
            wind_speed=7,
        )
        calculator_runner(self.contestant, track)

        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        expected_strings = [
            "Takeoff 1: 200.0 points missing takeoff gate\nplanned: 15:25:00\nactual: --",
            "SP: 21.0 points passing gate (+9 s)\nplanned: 15:31:00\nactual: 15:31:09",
            "TP1: 96.0 points passing gate (+34 s)\nplanned: 15:32:51\nactual: 15:33:25",
            "TP2: 84.0 points passing gate (+30 s)\nplanned: 15:42:26\nactual: 15:42:56",
            "TP3: 18.0 points passing gate (+8 s)\nplanned: 15:49:03\nactual: 15:49:11",
            "TP3: 200.0 points incorrect procedure turn",
            "TP4: 39.0 points passing gate (-15 s)\nplanned: 15:53:04\nactual: 15:52:49",
            "TP5: 42.0 points passing gate (+16 s)\nplanned: 15:56:37\nactual: 15:56:53",
            "TP6: 48.0 points passing gate (+18 s)\nplanned: 15:59:17\nactual: 15:59:35",
            "FP: 90.0 points passing gate (+32 s)\nplanned: 16:05:12\nactual: 16:05:44",
            "Landing 1: 0.0 points missing landing gate\nplanned: 17:24:00\nactual: --",
        ]
        strings = [
            item.string for item in ScoreLogEntry.objects.filter(contestant=self.contestant).order_by("time", "pk")
        ]
        self.assertListEqual(expected_strings, strings)

        self.assertEqual(
            838, contestant_track.score
        )  # Should be 1071, a difference of 78. Mostly caused by timing differences, I think.

    def test_fredrik(self, *args):
        track = load_track_points(os.path.join(TEST_DATA_DIR, "fredrik2019.gpx"))
        start_time, speed = datetime.datetime(2015, 1, 1, 12, 45, tzinfo=datetime.timezone.utc), 90
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=speed,
            wind_direction=220,
            wind_speed=7,
        )
        calculator_runner(self.contestant, track)
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        # Apparently the contestant crosses the finish line before starting the track, leading to everything to be missed.
        self.assertEqual(
            1000, contestant_track.score
        )  # Should be 1071, a difference of 78. Mostly caused by timing differences, I think.


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestHamar23March2021(TransactionTestCase):
    @patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        from display.default_scorecards import default_scorecard_fai_precision_2020

        self.scorecard = default_scorecard_fai_precision_2020.get_default_scorecard()
        with open(os.path.join(TEST_DATA_DIR, "hamartest.kml"), "r") as file:
            with patch(
                "display.models.EditableRoute._create_route_and_thumbnail",
                lambda name, r: EditableRoute.objects.create(name=name, route=r),
            ):
                editable_route, _ = EditableRoute.create_from_kml("Test", file)
                route = editable_route.create_precision_route(True, self.scorecard)
        navigation_task_start_time = datetime.datetime(2021, 3, 23, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2021, 3, 23, 19, 0, 0).astimezone()
        self.aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        self.navigation_task = NavigationTask.create(
            name="NM navigation_task",
            route=route,
            original_scorecard=self.scorecard,
            contest=Contest.objects.create(
                name="contest_{}_{}".format(self.__class__.__name__, datetime.datetime.now().timestamp()),
                start_time=datetime.datetime.now(datetime.timezone.utc),
                finish_time=datetime.datetime.now(datetime.timezone.utc),
                time_zone="Europe/Oslo",
            ),
            start_time=navigation_task_start_time,
            finish_time=navigation_task_finish_time,
        )
        crew = Crew.objects.create(
            member1=Person.objects.create(
                first_name="Mister",
                last_name="Pilot",
                email="mister_{}_{}@pilot.com".format(self.__class__.__name__, datetime.datetime.now().timestamp()),
            )
        )
        self.team = Team.objects.create(crew=crew, aeroplane=self.aeroplane)
        # Required to make the time zone save correctly
        self.navigation_task.refresh_from_db()

    def test_kolaf(self, *args):
        track = load_track_points(os.path.join(TEST_DATA_DIR, "hamar_kolaf.gpx"))
        start_time, speed = datetime.datetime(2021, 3, 23, 13, 32, tzinfo=datetime.timezone.utc), 70
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=6,
            adaptive_start=True,
            air_speed=speed,
            wind_direction=180,
            wind_speed=4,
        )
        calculator_runner(self.contestant, track)

        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        expected_strings = [
            "SP: 0.0 points crossing infinite starting line and starting adaptive timing",
            "SP: 6.0 points passing gate (-4 s)\nplanned: 14:38:00\nactual: 14:37:56",
            "TP 1: 24.0 points passing gate (-10 s)\nplanned: 14:41:22\nactual: 14:41:12",
            "TP 2: 33.0 points passing gate (+13 s)\nplanned: 14:46:37\nactual: 14:46:50",
            "TP 3: 75.0 points passing gate (+27 s)\nplanned: 14:50:37\nactual: 14:51:04",
            "TP 4: 54.0 points passing gate (+20 s)\nplanned: 14:58:19\nactual: 14:58:39",
            "TP 5: 0.0 points passing gate (-2 s)\nplanned: 15:02:03\nactual: 15:02:02",
            "FP: 24.0 points passing gate (-10 s)\nplanned: 15:09:12\nactual: 15:09:03",
        ]
        strings = [
            item.string for item in ScoreLogEntry.objects.filter(contestant=self.contestant).order_by("time", "pk")
        ]
        pprint(strings)
        self.assertListEqual(expected_strings, strings)

        self.assertEqual(216, contestant_track.score)

    def test_vjoycar(self, *args):
        track = load_track_points_traccar_csv(load_traccar_track(os.path.join(TEST_DATA_DIR, "vjoycarhamar.csv")))
        start_time, speed = datetime.datetime(2021, 3, 23, 13, 32, tzinfo=datetime.timezone.utc), 70
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=6,
            adaptive_start=True,
            air_speed=speed,
            wind_direction=180,
            wind_speed=4,
        )
        calculator_runner(self.contestant, track)
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        expected_strings = [
            "SP: 0.0 points crossing infinite starting line and starting adaptive timing",
            "SP: 3.0 points passing gate (-3 s)\nplanned: 14:38:00\nactual: 14:37:57",
            "TP 1: 24.0 points passing gate (-10 s)\nplanned: 14:41:23\nactual: 14:41:13",
            "TP 2: 30.0 points passing gate (+12 s)\nplanned: 14:46:38\nactual: 14:46:50",
            "TP 3: 72.0 points passing gate (+26 s)\nplanned: 14:50:38\nactual: 14:51:04",
            "TP 4: 54.0 points passing gate (+20 s)\nplanned: 14:58:20\nactual: 14:58:40",
            "TP 5: 6.0 points passing gate (-4 s)\nplanned: 15:02:04\nactual: 15:02:01",
            "FP: 24.0 points passing gate (-10 s)\nplanned: 15:09:13\nactual: 15:09:04",
        ]
        strings = [
            item.string for item in ScoreLogEntry.objects.filter(contestant=self.contestant).order_by("time", "pk")
        ]
        self.assertListEqual(expected_strings, strings)

        self.assertEqual(213, contestant_track.score)

    def test_lt03(self, *args):
        track = load_track_points_traccar_csv(load_traccar_track(os.path.join(TEST_DATA_DIR, "lt03_hamar.csv")))
        start_time, speed = datetime.datetime(2021, 3, 23, 13, 32, tzinfo=datetime.timezone.utc), 70
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=6,
            adaptive_start=True,
            air_speed=speed,
            wind_direction=180,
            wind_speed=4,
        )
        calculator_runner(self.contestant, track)
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        expected_strings = [
            "SP: 0.0 points crossing infinite starting line and starting adaptive timing",
            "SP: 6.0 points passing gate (-4 s)\nplanned: 14:38:00\nactual: 14:37:56",
            "TP 1: 24.0 points passing gate (-10 s)\nplanned: 14:41:22\nactual: 14:41:12",
            "TP 2: 36.0 points passing gate (+14 s)\nplanned: 14:46:37\nactual: 14:46:51",
            "TP 3: 75.0 points passing gate (+27 s)\nplanned: 14:50:37\nactual: 14:51:04",
            "TP 4: 54.0 points passing gate (+20 s)\nplanned: 14:58:19\nactual: 14:58:39",
            "TP 5: 0.0 points passing gate (-1 s)\nplanned: 15:02:03\nactual: 15:02:03",
            "FP: 21.0 points passing gate (-9 s)\nplanned: 15:09:12\nactual: 15:09:04",
        ]
        strings = [
            item.string for item in ScoreLogEntry.objects.filter(contestant=self.contestant).order_by("time", "pk")
        ]
        self.assertListEqual(expected_strings, strings)

        self.assertEqual(216, contestant_track.score)

    def test_kolaf_trackar(self, *args):
        track = load_track_points_traccar_csv(load_traccar_track(os.path.join(TEST_DATA_DIR, "kolaf_hamar.csv")))
        start_time, speed = datetime.datetime(2021, 3, 23, 13, 32, tzinfo=datetime.timezone.utc), 70
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=6,
            adaptive_start=True,
            air_speed=speed,
            wind_direction=180,
            wind_speed=4,
        )
        calculator_runner(self.contestant, track)
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        expected_strings = [
            "SP: 0.0 points crossing infinite starting line and starting adaptive timing",
            "SP: 6.0 points passing gate (-4 s)\nplanned: 14:38:00\nactual: 14:37:56",
            "TP 1: 21.0 points passing gate (-9 s)\nplanned: 14:41:22\nactual: 14:41:13",
            "TP 2: 36.0 points passing gate (+14 s)\nplanned: 14:46:37\nactual: 14:46:51",
            "TP 3: 75.0 points passing gate (+27 s)\nplanned: 14:50:37\nactual: 14:51:04",
            "TP 4: 54.0 points passing gate (+20 s)\nplanned: 14:58:19\nactual: 14:58:39",
            "TP 5: 0.0 points passing gate (-2 s)\nplanned: 15:02:03\nactual: 15:02:02",
            "FP: 21.0 points passing gate (-9 s)\nplanned: 15:09:12\nactual: 15:09:04",
        ]
        strings = [
            item.string for item in ScoreLogEntry.objects.filter(contestant=self.contestant).order_by("time", "pk")
        ]
        self.assertListEqual(expected_strings, strings)

        self.assertEqual(213, contestant_track.score)  # same as website
        # Test that task test is updated
        self.assertTrue(hasattr(self.navigation_task, "tasktest"))
        task_test = self.navigation_task.tasktest
        self.assertEqual(213, task_test.teamtestscore_set.get(team=self.team).points)
