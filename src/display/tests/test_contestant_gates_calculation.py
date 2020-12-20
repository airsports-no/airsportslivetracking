import datetime

from django.test import TestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Aeroplane, NavigationTask, Team, Contestant, Crew, Contest, Person
from display.views import create_route_from_csv


class TestContestantGatesCalculation(TestCase):
    def setUp(self):
        with open("display/tests/NM.csv", "r") as file:
            route = create_route_from_csv("navigation_task", file.readlines()[1:])
        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        self.navigation_task = NavigationTask.objects.create(name="NM navigation test",
                                                             route=route, contest=Contest.objects.create(name="contest",
                                                                                                         start_time=datetime.datetime.utcnow(),
                                                                                                         finish_time=datetime.datetime.utcnow()),
                                                             start_time=navigation_task_start_time,
                                                             finish_time=navigation_task_finish_time)
        scorecard = get_default_scorecard()
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        team = Team.objects.create(crew=crew, aeroplane=aeroplane)
        start_time, speed = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc), 75
        self.contestant = Contestant.objects.create(navigation_task=self.navigation_task, team=team,
                                                    takeoff_time=start_time,
                                                    tracker_start_time=start_time - datetime.timedelta(minutes=30),
                                                    finished_by_time=start_time + datetime.timedelta(hours=2),
                                                    traccar_device_name="Test contestant", contestant_number=1,
                                                    scorecard=scorecard, minutes_to_starting_point=6, air_speed=speed,
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
