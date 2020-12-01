import datetime
from unittest.mock import Mock

import gpxpy
from django.test import TestCase, TransactionTestCase

from display.calculators.original_calculator import OriginalCalculator
from display.calculators.precision_calculator import PrecisionCalculator
from display.models import Aeroplane, Contest, Scorecard, Team, Contestant, ContestantTrack
from display.views import create_track_from_csv


class TestFullTrack(TransactionTestCase):
    def setUp(self):
        with open("display/calculators/tests/NM.csv", "r") as file:
            track = create_track_from_csv("contest", file.readlines()[1:])
        contest_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        contest_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        self.contest = Contest.objects.create(name="NM contest",
                                              track=track, server_address=" ",
                                              server_token=" ",
                                              start_time=contest_start_time, finish_time=contest_finish_time,
                                              wind_direction=165,
                                              wind_speed=8)
        scorecard = Scorecard.objects.create(missed_gate=100,
                                             gate_timing_per_second=3,
                                             gate_perfect_limit_seconds=2,
                                             maximum_gate_score=100,
                                             backtracking=200,
                                             missed_procedure_turn=200,
                                             below_minimum_altitude=500,
                                             takeoff_time_limit_seconds=60,
                                             missed_takeoff_gate=100
                                             )
        team = Team.objects.create(pilot="Test contestant", navigator="", aeroplane=aeroplane)
        start_time, speed = datetime.datetime(2020, 8, 1, 9, 15, tzinfo=datetime.timezone.utc), 70
        self.contestant = Contestant.objects.create(contest=self.contest, team=team, takeoff_time=start_time,
                                                    finished_by_time=start_time + datetime.timedelta(hours=2),
                                                    traccar_device_name="Test contestant", contestant_number=1,
                                                    scorecard=scorecard, minutes_to_starting_point=6, air_speed=speed)

    def load_track_points(self, filename):
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

    # def test_correct_scoring_correct_track_original(self):
    #     positions = self.load_track_points("display/calculators/tests/test_contestant_correct_track.gpx")
    #     calculator = OriginalCalculator(self.contestant, Mock())
    #     calculator.start()
    #     calculator.add_positions(positions)
    #     calculator.join()
    #     contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
    #     self.assertEqual(280, contestant_track.score)


    def test_correct_scoring_correct_track_precision(self):
        positions = self.load_track_points("display/calculators/tests/test_contestant_correct_track.gpx")
        calculator = PrecisionCalculator(self.contestant, Mock())
        calculator.start()
        calculator.add_positions(positions)
        calculator.join()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(280, contestant_track.score)

    def test_correct_scoring_bad_track_precision(self):
        positions = self.load_track_points("display/calculators/tests/Steinar.gpx")
        calculator = PrecisionCalculator(self.contestant, Mock())
        calculator.start()
        calculator.add_positions(positions)
        calculator.join()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(2600, contestant_track.score)


    def test_missed_procedure_turn(self):
        positions = self.load_track_points("display/calculators/tests/jorgen_missed_procedure_turn.gpx")
        calculator = PrecisionCalculator(self.contestant, Mock())
        calculator.start()
        calculator.add_positions(positions)
        calculator.join()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        print(contestant_track.score_log)
        self.assertTrue("200 points for incorrect procedure turn at TP1" in contestant_track.score_log)
        self.assertTrue("200 points for incorrect procedure turn at TP4" in contestant_track.score_log)
        self.assertTrue("200 for missing procedure turn at TP6" in contestant_track.score_log)
