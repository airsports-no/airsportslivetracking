import datetime
import threading
from multiprocessing import Queue
from typing import List, Tuple
from unittest.mock import Mock, patch, call

import dateutil
from django.core.cache import cache
from django.test import TransactionTestCase
from django.test.utils import freeze_time

from display.calculators.anr_corridor_calculator import AnrCorridorCalculator
from display.calculators.calculator_factory import calculator_factory
from display.calculators.calculator_utilities import load_track_points_traccar_csv
from display.convert_flightcontest_gpx import create_anr_corridor_route_from_kml
from display.models import Aeroplane, NavigationTask, Contest, Crew, Person, Team, Contestant, ContestantTrack, \
    TrackScoreOverride
from influx_facade import InfluxFacade
from mock_utilities import TraccarMock


def load_traccar_track(track_file) -> List[Tuple[datetime.datetime, float, float]]:
    positions = []
    with open(track_file, "r") as i:
        for line in i.readlines():
            elements = line.split(",")
            positions.append((dateutil.parser.parse(elements[1]).replace(tzinfo=datetime.timezone.utc),
                              float(elements[2]), float(elements[3])))
    return positions


@patch("display.models.get_traccar_instance", return_value=TraccarMock)
class TestANRPerLeg(TransactionTestCase):
    @patch("display.models.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, p):
        with open("display/calculators/tests/kjeller.kml", "r") as file:
            route = create_anr_corridor_route_from_kml("test", file, 0.5, False)
        navigation_task_start_time = datetime.datetime(2021, 1, 27, 6, 0, 0, tzinfo=datetime.timezone.utc)
        navigation_task_finish_time = datetime.datetime(2021, 1, 27, 16, 0, 0, tzinfo=datetime.timezone.utc)
        self.aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        from display.default_scorecards import default_scorecard_fai_anr_2017
        self.navigation_task = NavigationTask.objects.create(name="NM navigation_task",
                                                             route=route,
                                                             scorecard=default_scorecard_fai_anr_2017.get_default_scorecard(),
                                                             contest=Contest.objects.create(name="contest",
                                                                                            start_time=datetime.datetime.now(
                                                                                                datetime.timezone.utc),
                                                                                            finish_time=datetime.datetime.now(
                                                                                                datetime.timezone.utc),
                                                                                            time_zone="Europe/Oslo"),
                                                             start_time=navigation_task_start_time,
                                                             finish_time=navigation_task_finish_time)
        self.navigation_task.track_score_override = TrackScoreOverride.objects.create(corridor_width=0.5,
                                                                                      corridor_grace_time=5,
                                                                                      corridor_maximum_penalty=50)
        self.navigation_task.save()
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=self.aeroplane)
        self.scorecard = default_scorecard_fai_anr_2017.get_default_scorecard()
        # Required to make the time zone save correctly
        self.navigation_task.refresh_from_db()

    def test_anr_score_per_leg(self, p):
        track = load_track_points_traccar_csv(
            load_traccar_track("display/calculators/tests/kjeller_anr_bad.csv"))
        start_time, speed = datetime.datetime(2021, 3, 15, 19, 30, tzinfo=datetime.timezone.utc), 70
        self.contestant = Contestant.objects.create(navigation_task=self.navigation_task, team=self.team,
                                                    takeoff_time=start_time,
                                                    finished_by_time=start_time + datetime.timedelta(hours=2),
                                                    tracker_start_time=start_time - datetime.timedelta(minutes=30),
                                                    tracker_device_id="Test contestant", contestant_number=1,
                                                    minutes_to_starting_point=7,
                                                    air_speed=speed, wind_direction=160,
                                                    wind_speed=0)
        q = Queue()
        influx = InfluxFacade()
        calculator = calculator_factory(self.contestant, q, live_processing=False)
        for i in track:
            i["deviceId"] = ""
            i["attributes"] = {}
            data = influx.generate_position_block_for_contestant(self.contestant, i, dateutil.parser.parse(i["time"]))
            q.put(data)
        q.put(None)
        calculator.run()
        while not q.empty():
            q.get_nowait()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        strings = [item["string"] for item in contestant_track.score_log]
        print(strings)
        self.assertListEqual(['Takeoff: 0.0 points missing gate\n(planned: 20:30:00 +0100, actual: --)',
                              'SP: 200.0 points missing gate\n(planned: 20:37:00 +0100, actual: --)',
                              'SP: 50.0 points outside corridor (77 seconds)', 'Waypoint 1: 200.0 points backtracking',
                              'Waypoint 1: 50.0 points outside corridor (152 seconds)',
                              'Waypoint 1: 0 points entering corridor',
                              'Waypoint 2: 50.0 points outside corridor (170 seconds)',
                              'Waypoint 3: 50.0 points outside corridor (170 seconds)',
                              'FP: 200.0 points passing gate (-778 s)\n(planned: 20:48:09 +0100, actual: 20:35:11 +0100)'],
                             strings)
        self.assertEqual(800, contestant_track.score)

    def test_anr_miss_multiple_finish(self, p):
        track = load_track_points_traccar_csv(
            load_traccar_track("display/calculators/tests/anr_miss_multiple_finish.csv"))
        start_time, speed = datetime.datetime.now(datetime.timezone.utc), 70
        self.contestant = Contestant.objects.create(navigation_task=self.navigation_task, team=self.team,
                                                    takeoff_time=start_time,
                                                    finished_by_time=start_time + datetime.timedelta(seconds=30),
                                                    tracker_start_time=start_time - datetime.timedelta(minutes=30),
                                                    tracker_device_id="Test contestant", contestant_number=1,
                                                    minutes_to_starting_point=7,
                                                    air_speed=speed, wind_direction=160,
                                                    wind_speed=0)
        q = Queue()
        influx = InfluxFacade()
        calculator = calculator_factory(self.contestant, q, live_processing=True)
        for i in track:
            i["deviceId"] = ""
            i["attributes"] = {}
            data = influx.generate_position_block_for_contestant(self.contestant, i,
                                                                 dateutil.parser.parse(i["time"]))
            q.put(data)
        calculator.run()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        strings = [item["string"] for item in contestant_track.score_log]
        print(strings)
        fixed_strings = [item.split("\n")[0] for item in strings]
        fixed_strings[1] = fixed_strings[1][:10]
        self.assertListEqual(['Takeoff: 0.0 points missing gate',
                              'SP: 200.0 ',
                              'SP: 50.0 points outside corridor (48 seconds)',
                              'Waypoint 1: 42.0 points outside corridor (14 seconds)',
                              'Waypoint 1: 0 points entering corridor', 'Waypoint 1: 200.0 points backtracking',
                              'Waypoint 1: 8.0 points outside corridor (capped) (226 seconds)',
                              'Waypoint 2: 50.0 points outside corridor (0 seconds)',
                              'Waypoint 3: 50.0 points outside corridor (0 seconds)',
                              'FP: 200.0 points missing gate',
                              'FP: 50.0 points outside corridor (0 seconds)',
                              'Landing: 0.0 points missing gate'],
                             fixed_strings)
        self.assertEqual(850, contestant_track.score)

    def test_manually_terminate_calculator(self, p):
        track = load_track_points_traccar_csv(
            load_traccar_track("display/calculators/tests/anr_miss_multiple_finish.csv"))
        start_time, speed = datetime.datetime.now(datetime.timezone.utc), 70
        self.contestant = Contestant.objects.create(navigation_task=self.navigation_task, team=self.team,
                                                    takeoff_time=start_time,
                                                    finished_by_time=start_time + datetime.timedelta(minutes=30),
                                                    tracker_start_time=start_time - datetime.timedelta(minutes=30),
                                                    tracker_device_id="Test contestant", contestant_number=1,
                                                    minutes_to_starting_point=7,
                                                    air_speed=speed, wind_direction=160,
                                                    wind_speed=0)
        q = Queue()
        influx = InfluxFacade()
        calculator = calculator_factory(self.contestant, q, live_processing=True)
        for i in track:
            i["deviceId"] = ""
            i["attributes"] = {}
            data = influx.generate_position_block_for_contestant(self.contestant, i,
                                                                 dateutil.parser.parse(i["time"]))
            q.put(data)
        threading.Timer(5, lambda: self.contestant.request_calculator_termination()).start()
        calculator.run()
        while not q.empty():
            q.get_nowait()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        strings = [item["string"] for item in contestant_track.score_log]
        print(strings)
        self.assertListEqual(['Takeoff: 0 points manually terminated'],
                             strings)
        self.assertEqual(0, contestant_track.score)

    def test_anr_miss_start_and_finish(self, p):
        track = load_track_points_traccar_csv(
            load_traccar_track("display/calculators/tests/anr_miss_start_and_finish.csv"))
        start_time, speed = datetime.datetime(2021, 3, 16, 14, 5, tzinfo=datetime.timezone.utc), 70
        self.contestant = Contestant.objects.create(navigation_task=self.navigation_task, team=self.team,
                                                    takeoff_time=start_time,
                                                    finished_by_time=start_time + datetime.timedelta(seconds=30),
                                                    tracker_start_time=start_time - datetime.timedelta(minutes=30),
                                                    tracker_device_id="Test contestant", contestant_number=1,
                                                    minutes_to_starting_point=7, adaptive_start=True,
                                                    air_speed=speed, wind_direction=160,
                                                    wind_speed=0)
        q = Queue()
        influx = InfluxFacade()
        calculator = calculator_factory(self.contestant, q, live_processing=False)
        for i in track:
            i["deviceId"] = ""
            i["attributes"] = {}
            data = influx.generate_position_block_for_contestant(self.contestant, i,
                                                                 dateutil.parser.parse(i["time"]))
            q.put(data)
        q.put(None)
        calculator.run()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        strings = [item["string"] for item in contestant_track.score_log]
        print(strings)
        expected = ['Takeoff: 0.0 points missing gate\n(planned: 15:05:00 +0100, actual: --)',
                    'SP: 200.0 points missing gate\n(planned: 14:17:00 +0100, actual: --)',
                    'SP: 3.0 points outside corridor (1 seconds)', 'SP: 0 points entering corridor',
                    'Waypoint 1: 0 points passing gate (no time check) (-56 s)\n(planned: 14:18:59 +0100, actual: 14:18:03 +0100)',
                    'Waypoint 2: 0 points passing gate (no time check) (-167 s)\n(planned: 14:22:33 +0100, actual: 14:19:46 +0100)',
                    'Waypoint 2: 24.0 points outside corridor (8 seconds)', 'Waypoint 2: 0 points entering corridor',
                    'Waypoint 3: 0 points passing gate (no time check) (-220 s)\n(planned: 14:24:31 +0100, actual: 14:20:51 +0100)',
                    'Waypoint 3: 21.0 points outside corridor (7 seconds)',
                    'FP: 200.0 points missing gate\n(planned: 14:28:09 +0100, actual: --)']
        self.assertListEqual(expected, strings)
        self.assertEqual(448, contestant_track.score)


@patch("display.models.get_traccar_instance", return_value=TraccarMock)
class TestANR(TransactionTestCase):
    @patch("display.models.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, p):
        with open("display/calculators/tests/eidsvoll.kml", "r") as file:
            route = create_anr_corridor_route_from_kml("test", file, 0.5, False)
        navigation_task_start_time = datetime.datetime(2021, 1, 27, 6, 0, 0, tzinfo=datetime.timezone.utc)
        navigation_task_finish_time = datetime.datetime(2021, 1, 27, 16, 0, 0, tzinfo=datetime.timezone.utc)
        self.aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        from display.default_scorecards import default_scorecard_fai_anr_2017
        self.navigation_task = NavigationTask.objects.create(name="NM navigation_task",
                                                             route=route,
                                                             scorecard=default_scorecard_fai_anr_2017.get_default_scorecard(),
                                                             contest=Contest.objects.create(name="contest",
                                                                                            start_time=datetime.datetime.now(
                                                                                                datetime.timezone.utc),
                                                                                            finish_time=datetime.datetime.now(
                                                                                                datetime.timezone.utc),
                                                                                            time_zone="Europe/Oslo"),
                                                             start_time=navigation_task_start_time,
                                                             finish_time=navigation_task_finish_time)
        self.navigation_task.track_score_override = TrackScoreOverride.objects.create(corridor_width=0.5,
                                                                                      corridor_grace_time=5)
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=self.aeroplane)
        self.scorecard = default_scorecard_fai_anr_2017.get_default_scorecard()
        # Required to make the time zone save correctly
        self.navigation_task.refresh_from_db()

    def test_track(self, p):
        track = load_track_points_traccar_csv(
            load_traccar_track("display/calculators/tests/kolaf_eidsvoll_traccar.csv"))
        start_time, speed = datetime.datetime(2021, 1, 27, 6, 45, tzinfo=datetime.timezone.utc), 40
        self.contestant = Contestant.objects.create(navigation_task=self.navigation_task, team=self.team,
                                                    takeoff_time=start_time,
                                                    finished_by_time=start_time + datetime.timedelta(hours=2),
                                                    tracker_start_time=start_time - datetime.timedelta(minutes=30),
                                                    tracker_device_id="Test contestant", contestant_number=1,
                                                    minutes_to_starting_point=7,
                                                    air_speed=speed, wind_direction=160,
                                                    wind_speed=0)
        q = Queue()
        influx = InfluxFacade()
        calculator = calculator_factory(self.contestant, q, live_processing=False)
        for i in track:
            i["deviceId"] = ""
            i["attributes"] = {}
            data = influx.generate_position_block_for_contestant(self.contestant, i, dateutil.parser.parse(i["time"]))
            q.put(data)
        q.put(None)
        calculator.run()
        while not q.empty():
            q.get_nowait()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(1371,  # 593,  # 2368,
                         contestant_track.score)
        strings = [item["string"] for item in contestant_track.score_log]
        self.assertTrue(
            "SP: 96.0 points passing gate (+33 s)\n(planned: 07:52:00 +0100, actual: 07:52:33 +0100)" in strings)

    def test_track_adaptive_start(self, p):
        track = load_track_points_traccar_csv(
            load_traccar_track("display/calculators/tests/kolaf_eidsvoll_traccar.csv"))
        start_time, speed = datetime.datetime(2021, 1, 27, 6, 45, tzinfo=datetime.timezone.utc), 40
        self.contestant = Contestant.objects.create(navigation_task=self.navigation_task, team=self.team,
                                                    adaptive_start=True,
                                                    takeoff_time=start_time,
                                                    finished_by_time=start_time + datetime.timedelta(hours=2),
                                                    tracker_start_time=start_time - datetime.timedelta(minutes=30),
                                                    tracker_device_id="Test contestant", contestant_number=1,
                                                    minutes_to_starting_point=7,
                                                    air_speed=speed, wind_direction=160,
                                                    wind_speed=0)
        q = Queue()
        influx = InfluxFacade()
        calculator = calculator_factory(self.contestant, q, live_processing=False)
        for i in track:
            i["deviceId"] = ""
            i["attributes"] = {}
            data = influx.generate_position_block_for_contestant(self.contestant, i, dateutil.parser.parse(i["time"]))
            q.put(data)
        q.put(None)
        calculator.run()
        while not q.empty():
            q.get_nowait()

        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(1353,  # 575,  # 2350,
                         contestant_track.score)
        strings = [item["string"] for item in contestant_track.score_log]
        self.assertTrue(
            "SP: 78.0 points passing gate (-27 s)\n(planned: 07:53:00 +0100, actual: 07:52:33 +0100)" in strings)


class TestAnrCorridorCalculator(TransactionTestCase):
    @patch("display.models.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, p):
        with patch("display.convert_flightcontest_gpx.load_features_from_kml",
                   return_value={"route": [(60, 11), (60, 12), (61, 12), (61, 11)]}):
            self.route = create_anr_corridor_route_from_kml("test", Mock(), 0.5, False)
        from display.default_scorecards import default_scorecard_fai_anr_2017
        navigation_task_start_time = datetime.datetime(2021, 1, 27, 6, 0, 0, tzinfo=datetime.timezone.utc)
        navigation_task_finish_time = datetime.datetime(2021, 1, 27, 16, 0, 0, tzinfo=datetime.timezone.utc)

        self.navigation_task = NavigationTask.objects.create(name="NM navigation_task",
                                                             route=self.route,
                                                             scorecard=default_scorecard_fai_anr_2017.get_default_scorecard(),
                                                             contest=Contest.objects.create(name="123467",
                                                                                            start_time=datetime.datetime.now(
                                                                                                datetime.timezone.utc),
                                                                                            finish_time=datetime.datetime.now(
                                                                                                datetime.timezone.utc),
                                                                                            time_zone="Europe/Oslo"),
                                                             start_time=navigation_task_start_time,
                                                             finish_time=navigation_task_finish_time)
        self.navigation_task.track_score_override = TrackScoreOverride.objects.create(corridor_width=0.5,
                                                                                      corridor_grace_time=5)
        start_time, speed = datetime.datetime(2021, 1, 27, 6, 45, tzinfo=datetime.timezone.utc), 40
        self.aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=self.aeroplane)

        self.contestant = Contestant.objects.create(navigation_task=self.navigation_task, team=self.team,
                                                    takeoff_time=start_time,
                                                    finished_by_time=start_time + datetime.timedelta(hours=2),
                                                    tracker_start_time=start_time - datetime.timedelta(minutes=30),
                                                    tracker_device_id="Test contestant", contestant_number=1,
                                                    minutes_to_starting_point=7,
                                                    air_speed=speed, wind_direction=160,
                                                    wind_speed=0)
        self.update_score = Mock()
        self.calculator = AnrCorridorCalculator(self.contestant, self.navigation_task.scorecard, self.route.waypoints,
                                                self.route, self.update_score)

    def test_inside_20_seconds_enroute(self):
        position = Mock()
        position.latitude = 60
        position.longitude = 11.5
        position.time = datetime.datetime(2020, 1, 1, 0, 0)
        position2 = Mock()
        position2.latitude = 60
        position2.longitude = 11.5
        position2.time = datetime.datetime(2020, 1, 1, 0, 0, 20)

        gate = Mock()
        self.calculator.calculate_enroute([position], gate, gate)
        self.calculator.calculate_enroute([position2], gate, gate)
        self.update_score.assert_not_called()

    def test_outside_2_seconds_enroute(self):
        position = Mock()
        position.latitude = 60.5
        position.longitude = 11
        position.time = datetime.datetime(2020, 1, 1, 0, 0)
        position2 = Mock()
        position2.latitude = 60.5
        position2.longitude = 11
        position2.time = datetime.datetime(2020, 1, 1, 0, 0, 1)
        position3 = Mock()
        position3.latitude = 60
        position3.longitude = 11.5
        position3.time = datetime.datetime(2020, 1, 1, 0, 0, 3)

        gate = Mock()
        self.calculator.calculate_enroute([position], gate, gate)
        self.calculator.calculate_enroute([position2], gate, gate)
        self.calculator.calculate_enroute([position3], gate, gate)
        self.update_score.assert_not_called()

    def test_outside_20_seconds_enroute(self):
        position = Mock()
        position.latitude = 60.5
        position.longitude = 11
        position.time = datetime.datetime(2020, 1, 1, 0, 0)
        position2 = Mock()
        position2.latitude = 60.5
        position2.longitude = 11
        position2.time = datetime.datetime(2020, 1, 1, 0, 0, 1)
        position3 = Mock()
        position3.latitude = 60
        position3.longitude = 11.5
        position3.time = datetime.datetime(2020, 1, 1, 0, 0, 21)

        gate = Mock()
        self.calculator.calculate_enroute([position], gate, gate)
        self.calculator.calculate_enroute([position2], gate, gate)
        self.calculator.calculate_enroute([position3], gate, gate)
        self.update_score.assert_has_calls([call(gate, 48.0, 'outside corridor (16 seconds)', 60.5, 11, 'anomaly',
                                                 f'outside_corridor_{gate.name}', maximum_score=-1)])

    def test_outside_20_seconds_until_finish(self):
        position = Mock()
        position.latitude = 60.5
        position.longitude = 11
        position.time = datetime.datetime(2020, 1, 1, 0, 0)
        position2 = Mock()
        position2.latitude = 60.5
        position2.longitude = 11
        position2.time = datetime.datetime(2020, 1, 1, 0, 0, 1)
        position3 = Mock()
        position3.latitude = 60
        position3.longitude = 11.5
        position3.time = datetime.datetime(2020, 1, 1, 0, 0, 21)

        gate = Mock()
        self.calculator.calculate_enroute([position], gate, gate)
        self.calculator.calculate_enroute([position2], gate, gate)
        self.calculator.passed_finishpoint([position3], gate)
        self.update_score.assert_called_with(gate, 48, 'outside corridor (16 seconds)', 60.5, 11, 'anomaly',
                                             f'outside_corridor_{gate.name}', maximum_score=-1)

    def test_outside_20_seconds_outside_route(self):
        position = Mock()
        position.latitude = 60.5
        position.longitude = 11
        position.time = datetime.datetime(2020, 1, 1, 0, 0)
        position2 = Mock()
        position2.latitude = 60.5
        position2.longitude = 11
        position2.time = datetime.datetime(2020, 1, 1, 0, 0, 1)
        position3 = Mock()
        position3.latitude = 60
        position3.longitude = 11.5
        position3.time = datetime.datetime(2020, 1, 1, 0, 0, 21)

        gate = Mock()
        self.calculator.calculate_outside_route([position], gate)
        self.calculator.calculate_outside_route([position2], gate)
        self.calculator.calculate_outside_route([position3], gate)
        self.update_score.assert_not_called()


@patch("display.models.get_traccar_instance", return_value=TraccarMock)
class TestANRPolygon(TransactionTestCase):
    @patch("display.models.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, p):
        with open("display/calculators/tests/kjeller.kml", "r") as file:
            route = create_anr_corridor_route_from_kml("test", file, 0.5, False)
        navigation_task_start_time = datetime.datetime(2021, 1, 27, 6, 0, 0, tzinfo=datetime.timezone.utc)
        navigation_task_finish_time = datetime.datetime(2021, 1, 27, 16, 0, 0, tzinfo=datetime.timezone.utc)
        self.aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        from display.default_scorecards import default_scorecard_fai_anr_2017
        self.navigation_task = NavigationTask.objects.create(name="NM navigation_task",
                                                             route=route,
                                                             scorecard=default_scorecard_fai_anr_2017.get_default_scorecard(),
                                                             contest=Contest.objects.create(name="contest",
                                                                                            start_time=datetime.datetime.now(
                                                                                                datetime.timezone.utc),
                                                                                            finish_time=datetime.datetime.now(
                                                                                                datetime.timezone.utc),
                                                                                            time_zone="Europe/Oslo"),
                                                             start_time=navigation_task_start_time,
                                                             finish_time=navigation_task_finish_time)
        self.navigation_task.track_score_override = TrackScoreOverride.objects.create(corridor_width=0.5,
                                                                                      corridor_grace_time=5)
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=self.aeroplane)
        self.scorecard = default_scorecard_fai_anr_2017.get_default_scorecard()
        # Required to make the time zone save correctly
        self.navigation_task.refresh_from_db()

    def test_track(self, p):
        track = load_track_points_traccar_csv(
            load_traccar_track("display/calculators/tests/kolaf_eidsvoll_traccar.csv"))
        start_time, speed = datetime.datetime(2021, 1, 27, 6, 45, tzinfo=datetime.timezone.utc), 40
        self.contestant = Contestant.objects.create(navigation_task=self.navigation_task, team=self.team,
                                                    takeoff_time=start_time,
                                                    finished_by_time=start_time + datetime.timedelta(hours=2),
                                                    tracker_start_time=start_time - datetime.timedelta(minutes=30),
                                                    tracker_device_id="Test contestant", contestant_number=1,
                                                    minutes_to_starting_point=7,
                                                    air_speed=speed, wind_direction=160,
                                                    wind_speed=0)
        q = Queue()
        influx = InfluxFacade()
        calculator = calculator_factory(self.contestant, q, live_processing=False)
        for i in track:
            i["deviceId"] = ""
            i["attributes"] = {}
            data = influx.generate_position_block_for_contestant(self.contestant, i, dateutil.parser.parse(i["time"]))
            q.put(data)
        q.put(None)
        calculator.run()
        while not q.empty():
            q.get_nowait()
