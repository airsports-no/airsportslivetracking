import datetime
from unittest.mock import Mock

import gpxpy
from django.test import TestCase, TransactionTestCase

from display.calculators.precision_calculator import PrecisionCalculator
from display.convert_flightcontest_gpx import create_route_from_gpx
from display.models import Aeroplane, NavigationTask, Scorecard, Team, Contestant, ContestantTrack, GateScore, Crew
from display.views import create_route_from_csv


def load_track_points(filename):
    with open(filename, "r") as i:
        gpx = gpxpy.parse(i)
    positions = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                positions.append(
                    {"time": point.time.isoformat(),
                     "latitude": point.latitude, "longitude": point.longitude,
                     "altitude": point.elevation, "speed": 0, "course": 0, "battery_level": 100})
    return positions


class TestFullTrack(TransactionTestCase):
    def setUp(self):
        with open("display/calculators/tests/NM.csv", "r") as file:
            route = create_route_from_csv("navigation_task", file.readlines()[1:])
        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        self.navigation_task = NavigationTask.objects.create(name="NM navigation_task",
                                                             route=route,
                                                             start_time=navigation_task_start_time,
                                                             finish_time=navigation_task_finish_time)
        from display.default_scorecards import default_scorecard_fai_precision_2020
        scorecard = default_scorecard_fai_precision_2020.get_default_scorecard()
        crew = Crew.objects.create(pilot="Test contestant", navigator="")
        team = Team.objects.create(crew=crew, aeroplane=aeroplane)
        start_time, speed = datetime.datetime(2020, 8, 1, 9, 15, tzinfo=datetime.timezone.utc), 70
        self.contestant = Contestant.objects.create(navigation_task=self.navigation_task, team=team,
                                                    takeoff_time=start_time,
                                                    tracker_start_time=start_time - datetime.timedelta(minutes=30),
                                                    finished_by_time=start_time + datetime.timedelta(hours=2),
                                                    traccar_device_name="Test contestant", contestant_number=1,
                                                    scorecard=scorecard, minutes_to_starting_point=6, air_speed=speed,
                                                    wind_direction=165, wind_speed=8)

    def test_correct_scoring_correct_track_precision(self):
        positions = load_track_points("display/calculators/tests/test_contestant_correct_track.gpx")
        calculator = PrecisionCalculator(self.contestant, Mock())
        calculator.start()
        calculator.add_positions(positions)
        calculator.join()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(144, contestant_track.score)

    def test_correct_scoring_bad_track_precision(self):
        positions = load_track_points("display/calculators/tests/Steinar.gpx")
        calculator = PrecisionCalculator(self.contestant, Mock())
        calculator.start()
        calculator.add_positions(positions)
        calculator.join()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(2000, contestant_track.score)

    def test_missed_procedure_turn(self):
        positions = load_track_points("display/calculators/tests/jorgen_missed_procedure_turn.gpx")
        calculator = PrecisionCalculator(self.contestant, Mock())
        calculator.start()
        calculator.add_positions(positions)
        calculator.join()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        print(contestant_track.score_log)
        self.assertTrue("200 points for incorrect procedure turn at TP1" in contestant_track.score_log)
        self.assertTrue("200 points for incorrect procedure turn at TP4" in contestant_track.score_log)
        self.assertTrue("200 for missing procedure turn at TP6" not in contestant_track.score_log)


class Test2017WPFC(TransactionTestCase):
    def setUp(self):
        with open("display/tests/demo_contests/2017_WPFC/Route-1-Blue.gpx", "r") as file:
            route = create_route_from_gpx("navigation_task", file)
        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        self.aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        self.navigation_task = NavigationTask.objects.create(name="NM navigation_task",
                                                             route=route,
                                                             start_time=navigation_task_start_time,
                                                             finish_time=navigation_task_finish_time)
        crew = Crew.objects.create(pilot="Test contestant", navigator="")
        self.team = Team.objects.create(crew=crew, aeroplane=self.aeroplane)
        from display.default_scorecards import default_scorecard_fai_precision_2020
        self.scorecard = default_scorecard_fai_precision_2020.get_default_scorecard()

    def test_101(self):
        track = load_track_points(
            "display/tests/demo_contests/2017_WPFC/101_-_Aircraft-039_-_1._Nav._-_Navigation_Flight_Results_(Edition_2).gpx")
        start_time, speed = datetime.datetime(2015, 1, 1, 7, 30, tzinfo=datetime.timezone.utc), 80
        self.contestant = Contestant.objects.create(navigation_task=self.navigation_task, team=self.team,
                                                    takeoff_time=start_time,
                                                    finished_by_time=start_time + datetime.timedelta(hours=2),
                                                    tracker_start_time=start_time - datetime.timedelta(minutes=30),
                                                    traccar_device_name="Test contestant", contestant_number=1,
                                                    scorecard=self.scorecard, minutes_to_starting_point=8,
                                                    air_speed=speed, wind_direction=160,
                                                    wind_speed=18)
        calculator = PrecisionCalculator(self.contestant, Mock())
        calculator.start()
        calculator.add_positions(track)
        calculator.join()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(1149, contestant_track.score)  # Should be 1071, a difference of 78. Mostly caused by timing differences, I think.
