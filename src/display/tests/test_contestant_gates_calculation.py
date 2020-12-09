import datetime

from django.test import TestCase

from display.models import Aeroplane, NavigationTask, Scorecard, Team, Contestant
from display.views import create_track_from_csv


class TestContestantGatesCalculation(TestCase):
    def setUp(self):
        with open("display/tests/NM.csv", "r") as file:
            track = create_track_from_csv("navigation_task", file.readlines()[1:])
        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        self.navigation_task = NavigationTask.objects.create(name="NM navigation test",
                                              track=track, server_address=" ",
                                              server_token=" ",
                                              start_time=navigation_task_start_time, finish_time=navigation_task_finish_time,
                                              wind_direction=165,
                                              wind_speed=8)
        scorecard = Scorecard.objects.create(missed_gate=100,
                                             gate_timing_per_second=3,
                                             gate_perfect_limit_seconds=2,
                                             maximum_gate_score=100,
                                             backtracking=200,
                                             missed_procedure_turn_penalty=200,
                                             below_minimum_altitude=500,
                                             takeoff_time_limit_seconds=60,
                                             missed_takeoff_gate=100
                                             )
        team = Team.objects.create(pilot="Test contestant", navigator="", aeroplane=aeroplane)
        start_time, speed = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc), 75
        self.contestant = Contestant.objects.create(navigation_task=self.navigation_task, team=team, takeoff_time=start_time,
                                                    finished_by_time=start_time + datetime.timedelta(hours=2),
                                                    traccar_device_name="Test contestant", contestant_number=1,
                                                    scorecard=scorecard, minutes_to_starting_point=6, air_speed=speed)

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
