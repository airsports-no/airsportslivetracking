import datetime
from unittest.mock import Mock

import gpxpy
from django.test import TestCase, TransactionTestCase

from display.calculators.precision_calculator import PrecisionCalculator
from display.convert_flightcontest_gpx import create_track_from_gpx
from display.models import Aeroplane, Contest, Scorecard, Team, Contestant, ContestantTrack, GateScore
from display.views import create_track_from_csv


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
            track = create_track_from_csv("contest", file.readlines()[1:])
        contest_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        contest_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        self.contest = Contest.objects.create(name="NM contest",
                                              track=track,
                                              start_time=contest_start_time, finish_time=contest_finish_time,
                                              wind_direction=165,
                                              wind_speed=8)
        scorecard = Scorecard.objects.create(
            backtracking=200,
            below_minimum_altitude=500,
        )
        scores = {
            "extended_gate_width": 2,
            "bad_crossing_extended_gate_penalty": 100,
            "graceperiod_before": 2,
            "graceperiod_after": 2,
            "maximum_penalty": 100,
            "penalty_per_second": 3,
            "missed_penalty": 100,
            "missed_procedure_turn": 200
        }
        scorecard.starting_point_gate_score = GateScore.objects.create(**scores)
        scorecard.finish_point_gate_score = GateScore.objects.create(**scores)
        scorecard.turning_point_gate_score = GateScore.objects.create(**scores)
        scorecard.secret_gate_score = GateScore.objects.create(**scores)
        scorecard.save()
        team = Team.objects.create(pilot="Test contestant", navigator="", aeroplane=aeroplane)
        start_time, speed = datetime.datetime(2020, 8, 1, 9, 15, tzinfo=datetime.timezone.utc), 70
        self.contestant = Contestant.objects.create(contest=self.contest, team=team, takeoff_time=start_time,
                                                    finished_by_time=start_time + datetime.timedelta(hours=2),
                                                    traccar_device_name="Test contestant", contestant_number=1,
                                                    scorecard=scorecard, minutes_to_starting_point=6, air_speed=speed)

    def test_correct_scoring_correct_track_precision(self):
        positions = load_track_points("display/calculators/tests/test_contestant_correct_track.gpx")
        calculator = PrecisionCalculator(self.contestant, Mock())
        calculator.start()
        calculator.add_positions(positions)
        calculator.join()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(146, contestant_track.score)

    def test_correct_scoring_bad_track_precision(self):
        positions = load_track_points("display/calculators/tests/Steinar.gpx")
        calculator = PrecisionCalculator(self.contestant, Mock())
        calculator.start()
        calculator.add_positions(positions)
        calculator.join()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(2200, contestant_track.score)

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
        with open("display/tests/demo contests/2017_WPFC/Route-1-Blue.gpx", "r") as file:
            track = create_track_from_gpx("contest", file)
        contest_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        contest_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        self.aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        self.contest = Contest.objects.create(name="NM contest",
                                              track=track,
                                              start_time=contest_start_time, finish_time=contest_finish_time,
                                              wind_direction=165,
                                              wind_speed=0)
        self.team = Team.objects.create(pilot="Test contestant", navigator="", aeroplane=self.aeroplane)
        self.scorecard = Scorecard.objects.create(
            backtracking=200,
            below_minimum_altitude=500,
        )
        self.scores = {
            "extended_gate_width": 6,  # The correct for turning points with procedure turns
            "bad_crossing_extended_gate_penalty": 100,
            "graceperiod_before": 2,
            "graceperiod_after": 2,
            "maximum_penalty": 100,
            "penalty_per_second": 3,
            "missed_penalty": 100,
            "missed_procedure_turn": 200
        }
        self.scorecard.starting_point_gate_score = GateScore.objects.create(**{**self.scores, "extended_gate_width": 2})
        self.scorecard.takeoff_gate_score = GateScore.objects.create(
            **{**self.scores, "graceperiod_before": 0, "graceperiod_after": 60, "penalty_per_second": 100})
        self.scorecard.landing_gate_score = GateScore.objects.create(**self.scores)
        self.scorecard.finish_point_gate_score = GateScore.objects.create(**self.scores)
        self.scorecard.turning_point_gate_score = GateScore.objects.create(**self.scores)
        self.scorecard.secret_gate_score = GateScore.objects.create(**self.scores)
        self.scorecard.save()

    def test_101(self):
        track = load_track_points(
            "display/tests/demo contests/2017_WPFC/101_-_Aircraft-039_-_1._Nav._-_Navigation_Flight_Results_(Edition_2).gpx")
        start_time, speed = datetime.datetime(2015, 1, 1, 7, 30, tzinfo=datetime.timezone.utc), 80
        self.contestant = Contestant.objects.create(contest=self.contest, team=self.team, takeoff_time=start_time,
                                                    finished_by_time=start_time + datetime.timedelta(hours=2),
                                                    traccar_device_name="Test contestant", contestant_number=1,
                                                    scorecard=self.scorecard, minutes_to_starting_point=8,
                                                    air_speed=speed)
        calculator = PrecisionCalculator(self.contestant, Mock())
        calculator.start()
        calculator.add_positions(track)
        calculator.join()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(999, contestant_track.score)
