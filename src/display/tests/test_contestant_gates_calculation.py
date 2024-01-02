import datetime
from unittest.mock import patch

from django.test import TestCase

from display.utilities.calculate_gate_times import calculate_and_get_relative_gate_times
from display.default_scorecards import default_scorecard_fai_anr_2017
from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Aeroplane, NavigationTask, Team, Contestant, Crew, Contest, Person, EditableRoute
from utilities.mock_utilities import TraccarMock


def chop_microseconds(delta):
    return delta - datetime.timedelta(microseconds=delta.microseconds)


class TestContestantGatesCalculation(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        scorecard = get_default_scorecard()
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Test", file.readlines()[1:])
            route = editable_route.create_precision_route(True, scorecard)
        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        self.navigation_task = NavigationTask.create(
            name="NM navigation test",
            original_scorecard=scorecard,
            route=route,
            contest=Contest.objects.create(
                name="contest",
                start_time=datetime.datetime.now(datetime.timezone.utc),
                finish_time=datetime.datetime.now(datetime.timezone.utc),
            ),
            start_time=navigation_task_start_time,
            finish_time=navigation_task_finish_time,
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        team = Team.objects.create(crew=crew, aeroplane=aeroplane)
        start_time, speed = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc), 75
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=team,
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

    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    def test_gate_times(self, p):
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
            ("FP", 9, 5, 27),
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
        def chop_microseconds(delta):
            return delta - datetime.timedelta(microseconds=delta.microseconds)

        times = calculate_and_get_relative_gate_times(self.navigation_task.route, 75, 8, 165)
        expected_times = [
            ("SP", datetime.timedelta(0)),
            ("SC 1/1", datetime.timedelta(seconds=104, microseconds=981691)),
            ("TP1", datetime.timedelta(seconds=407, microseconds=411176)),
            ("SC 2/1", datetime.timedelta(seconds=587, microseconds=331999)),
            ("TP2", datetime.timedelta(seconds=740, microseconds=537499)),
            ("SC 3/1", datetime.timedelta(seconds=849, microseconds=796023)),
            ("SC 3/2", datetime.timedelta(seconds=1008, microseconds=328113)),
            ("TP3", datetime.timedelta(seconds=1292, microseconds=695841)),
            ("TP4", datetime.timedelta(seconds=1550, microseconds=440154)),
            ("SC 5/1", datetime.timedelta(seconds=1789, microseconds=511703)),
            ("TP5", datetime.timedelta(seconds=2047, microseconds=89828)),
            ("SC 6/1", datetime.timedelta(seconds=2250, microseconds=438729)),
            ("TP6", datetime.timedelta(seconds=2666, microseconds=290646)),
            ("SC 7/1", datetime.timedelta(seconds=2824, microseconds=756831)),
            ("SC 7/2", datetime.timedelta(seconds=3054, microseconds=214214)),
            ("FP", datetime.timedelta(seconds=3276, microseconds=732726)),
        ]
        # print(times)
        times = [(item[0], chop_microseconds(item[1])) for item in times]
        expected_times = [(item[0], chop_microseconds(item[1])) for item in expected_times]
        self.assertListEqual(expected_times, times)


class TestContestantGatesCalculationANRRounded(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        with open("display/tests/kjeller.kml", "r") as file:
            with patch(
                "display.models.EditableRoute._create_route_and_thumbnail",
                lambda name, r: EditableRoute.objects.create(name=name, route=r),
            ):
                editable_route, _ = EditableRoute.create_from_kml("Test", file)
                route = editable_route.create_anr_route(
                    True, 0.5, default_scorecard_fai_anr_2017.get_default_scorecard()
                )
        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        scorecard = get_default_scorecard()
        self.navigation_task = NavigationTask.create(
            name="NM navigation test",
            original_scorecard=scorecard,
            route=route,
            contest=Contest.objects.create(
                name="contest",
                start_time=datetime.datetime.now(datetime.timezone.utc),
                finish_time=datetime.datetime.now(datetime.timezone.utc),
            ),
            start_time=navigation_task_start_time,
            finish_time=navigation_task_finish_time,
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        team = Team.objects.create(crew=crew, aeroplane=aeroplane)
        start_time, speed = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc), 75
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=team,
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

    def test_calculate_and_get_relative_gate_times(self):
        times = calculate_and_get_relative_gate_times(self.navigation_task.route, 75, 8, 165)
        expected_times = [
            ("SP", datetime.timedelta(0)),
            ("TP 1", datetime.timedelta(seconds=125)),
            ("TP 2", datetime.timedelta(seconds=348)),
            ("TP 3", datetime.timedelta(seconds=456)),
            ("FP", datetime.timedelta(seconds=641)),
        ]
        # print(times)
        # for item in times:
        # print(item[1].total_seconds())
        self.assertListEqual(expected_times, [(item[0], chop_microseconds(item[1])) for item in times])
