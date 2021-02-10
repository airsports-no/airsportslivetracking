import datetime
from unittest.mock import Mock, patch

from django.test import TransactionTestCase

from display.calculators.gatekeeper import Gatekeeper
from display.calculators.positions_and_gates import Position
from display.convert_flightcontest_gpx import create_precision_route_from_csv
from display.models import Aeroplane, NavigationTask, Contest, Crew, Contestant, Person, Team
from mock_utilities import TraccarMock


class TestInterpolation(TransactionTestCase):
    @patch("display.models.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, patch):
        with open("display/calculators/tests/NM.csv", "r") as file:
            route = create_precision_route_from_csv("navigation_task", file.readlines()[1:], True)
        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        from display.default_scorecards import default_scorecard_fai_precision_2020
        self.scorecard = default_scorecard_fai_precision_2020.get_default_scorecard()

        self.navigation_task = NavigationTask.objects.create(name="NM navigation_task",
                                                             route=route,
                                                             scorecard=self.scorecard,
                                                             contest=Contest.objects.create(name="contest",
                                                                                            start_time=datetime.datetime.now(
                                                                                                datetime.timezone.utc),
                                                                                            finish_time=datetime.datetime.now(
                                                                                                datetime.timezone.utc),
                                                                                            time_zone="Europe/Oslo"),
                                                             start_time=navigation_task_start_time,
                                                             finish_time=navigation_task_finish_time)
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=aeroplane)
        start_time, speed = datetime.datetime(2020, 8, 1, 9, 15, tzinfo=datetime.timezone.utc), 70
        # Required to make the time zone save correctly
        self.navigation_task.refresh_from_db()
        self.contestant = Contestant.objects.create(navigation_task=self.navigation_task, team=self.team,
                                                    takeoff_time=start_time,
                                                    tracker_start_time=start_time - datetime.timedelta(minutes=30),
                                                    finished_by_time=start_time + datetime.timedelta(hours=2),
                                                    tracker_device_id="Test contestant", contestant_number=1,
                                                    minutes_to_starting_point=6,
                                                    air_speed=speed,
                                                    wind_direction=165, wind_speed=8)

    def test_no_interpolation(self):
        gatekeeper = Gatekeeper(self.contestant, Mock(), [])
        start_position = Position("2020-01-01T00:00:00Z", 60, 11, 0, 0, 0, 0)
        gatekeeper.track = [start_position]
        next_position = Position("2020-01-01T00:00:02Z", 60, 12, 0, 0, 0, 0)
        interpolated = gatekeeper.interpolate_track(next_position)
        self.assertEqual(1, len(interpolated))
        self.assertEqual(next_position, interpolated[0])

    def test_interpolation(self):
        gatekeeper = Gatekeeper(self.contestant, Mock(), [])
        start_position = Position("2020-01-01T00:00:00Z", 60, 11, 0, 0, 0, 0)
        gatekeeper.track = [start_position]
        next_position = Position("2020-01-01T00:00:05Z", 60, 12, 0, 0, 0, 0)
        interpolated = gatekeeper.interpolate_track(next_position)
        expected = [
            ('2020-01-01 00:00:01+00:00', 60.00060459825317, 11.199996344505323),
            ('2020-01-01 00:00:02+00:00', 60.00090690198414, 11.399998172230388),
            ('2020-01-01 00:00:03+00:00', 60.00090690198414, 11.600001827769612),
            ('2020-01-01 00:00:04+00:00', 60.00060459825317, 11.800003655494676),
            ('2020-01-01 00:00:05+00:00', 60, 12)
        ]
        print([str(item) for item in interpolated])
        self.assertEqual(5, len(interpolated))
        for index in range(len(interpolated)):
            self.assertListEqual(
                [str(interpolated[index].time), interpolated[index].latitude, interpolated[index].longitude],
                list(expected[index]))
