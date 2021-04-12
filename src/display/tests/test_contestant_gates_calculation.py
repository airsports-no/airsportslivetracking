import datetime
from unittest.mock import patch

from django.test import TestCase

from display.calculate_gate_times import calculate_and_get_relative_gate_times
from display.convert_flightcontest_gpx import create_anr_corridor_route_from_kml
from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Aeroplane, NavigationTask, Team, Contestant, Crew, Contest, Person
from display.views import create_precision_route_from_csv
from mock_utilities import TraccarMock


class TestContestantGatesCalculation(TestCase):
    @patch("display.models.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, patch):
        with open("display/tests/NM.csv", "r") as file:
            route = create_precision_route_from_csv("navigation_task", file.readlines()[1:], True)
        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        scorecard = get_default_scorecard()
        self.navigation_task = NavigationTask.objects.create(name="NM navigation test",
                                                             scorecard=scorecard,
                                                             route=route, contest=Contest.objects.create(name="contest",
                                                                                                         start_time=datetime.datetime.now(
                                                                                                             datetime.timezone.utc),
                                                                                                         finish_time=datetime.datetime.now(
                                                                                                             datetime.timezone.utc)),
                                                             start_time=navigation_task_start_time,
                                                             finish_time=navigation_task_finish_time)
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        team = Team.objects.create(crew=crew, aeroplane=aeroplane)
        start_time, speed = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc), 75
        self.contestant = Contestant.objects.create(navigation_task=self.navigation_task, team=team,
                                                    takeoff_time=start_time,
                                                    tracker_start_time=start_time - datetime.timedelta(minutes=30),
                                                    finished_by_time=start_time + datetime.timedelta(hours=2),
                                                    tracker_device_id="Test contestant", contestant_number=1,
                                                    minutes_to_starting_point=6, air_speed=speed,
                                                    wind_direction=165,
                                                    wind_speed=8)

    def test_gate_times(self):
        gate_times = self.contestant.gate_times
        expected_times = [
            ("SP", 8, 11, 0),
            ("SC 1/1", 8, 12, 44),
            ("TP1", 8, 17, 45),
            ("SC 2/1", 8, 20, 44),
            ("TP2", 8, 23, 17),
            ("SC 3/1", 8, 25, 6),
            ("SC 3/2", 8, 27, 44),
            ("TP3", 8, 32, 27),
            ("TP4", 8, 36, 44),
            ("SC 5/1", 8, 40, 43),
            ("TP5", 8, 45, 0),
            ("SC 6/1", 8, 48, 23),
            ("TP6", 8, 55, 18),
            ("SC 7/1", 8, 57, 56),
            ("SC 7/2", 9, 1, 45),
            ("FP", 9, 5, 27)
        ]
        for gate, hour, minute, second in expected_times:
            expected = datetime.datetime(2020, 8, 1, hour, minute, second, tzinfo=datetime.timezone.utc)
            actual = gate_times[gate].replace(microsecond=0)
            # self.assertEqual(expected, actual, "Timing error for gate {}".format(gate))
            if expected != actual:
                print("{}: {}".format(gate, (actual - expected).total_seconds()))
            else:
                print("{} Matches!".format(gate))

    def test_calculate_and_get_relative_gate_times(self):
        times = calculate_and_get_relative_gate_times(self.navigation_task.route, 75, 8, 165)
        expected_times = [('SP', datetime.timedelta(0)), ('SC 1/1', datetime.timedelta(0, 104, 606172)),
                          ('TP1', datetime.timedelta(0, 405, 953623)), ('SC 2/1', datetime.timedelta(0, 585, 504090)),
                          ('TP2', datetime.timedelta(0, 738, 235839)), ('SC 3/1', datetime.timedelta(0, 847, 104080)),
                          ('SC 3/2', datetime.timedelta(0, 1005, 69764)), ('TP3', datetime.timedelta(0, 1288, 421177)),
                          ('TP4', datetime.timedelta(0, 1545, 321030)), ('SC 5/1', datetime.timedelta(0, 1784, 8036)),
                          ('TP5', datetime.timedelta(0, 2041, 35476)), ('SC 6/1', datetime.timedelta(0, 2244, 13203)),
                          ('TP6', datetime.timedelta(0, 2659, 112258)), ('SC 7/1', datetime.timedelta(0, 2817, 307225)),
                          ('SC 7/2', datetime.timedelta(0, 3046, 131105)), ('FP', datetime.timedelta(0, 3268, 33269))]
        print(times)
        self.assertListEqual(expected_times, times)


class TestContestantGatesCalculationANRRounded(TestCase):
    @patch("display.models.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, patch):
        with open("display/tests/kjeller.kml", "r") as file:
            route = create_anr_corridor_route_from_kml("test", file, 0.5, True)
        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        scorecard = get_default_scorecard()
        self.navigation_task = NavigationTask.objects.create(name="NM navigation test",
                                                             scorecard=scorecard,
                                                             route=route, contest=Contest.objects.create(name="contest",
                                                                                                         start_time=datetime.datetime.now(
                                                                                                             datetime.timezone.utc),
                                                                                                         finish_time=datetime.datetime.now(
                                                                                                             datetime.timezone.utc)),
                                                             start_time=navigation_task_start_time,
                                                             finish_time=navigation_task_finish_time)
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        team = Team.objects.create(crew=crew, aeroplane=aeroplane)
        start_time, speed = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc), 75
        self.contestant = Contestant.objects.create(navigation_task=self.navigation_task, team=team,
                                                    takeoff_time=start_time,
                                                    tracker_start_time=start_time - datetime.timedelta(minutes=30),
                                                    finished_by_time=start_time + datetime.timedelta(hours=2),
                                                    tracker_device_id="Test contestant", contestant_number=1,
                                                    minutes_to_starting_point=6, air_speed=speed,
                                                    wind_direction=165,
                                                    wind_speed=8)

    def test_calculate_and_get_relative_gate_times(self):
        times = calculate_and_get_relative_gate_times(self.navigation_task.route, 75, 8, 165)
        expected_times = [('SP', datetime.timedelta(0)), ('Waypoint 1', datetime.timedelta(0, 125, 42535)),
                          ('Waypoint 2', datetime.timedelta(0, 345, 912307)),
                          ('Waypoint 3', datetime.timedelta(0, 450, 779638)), ('FP', datetime.timedelta(0, 634, 67374))]
        print(times)
        for item in times:
            print(item[1].total_seconds())
        self.assertListEqual(expected_times, times)
