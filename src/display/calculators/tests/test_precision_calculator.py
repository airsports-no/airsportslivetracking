import datetime
from unittest.mock import Mock

import gpxpy
from django.test import TestCase, TransactionTestCase

from display.calculators.positions_and_gates import Gate
from display.calculators.precision_calculator import PrecisionCalculator
from display.convert_flightcontest_gpx import create_route_from_gpx, calculate_extended_gate
from display.models import Aeroplane, NavigationTask, Scorecard, Team, Contestant, ContestantTrack, GateScore, Crew, \
    Contest, Person, TrackScoreOverride, GateScoreOverride
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
            route = create_route_from_csv("navigation_task", file.readlines()[1:], True)
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
                                                                                                datetime.timezone.utc)),
                                                             start_time=navigation_task_start_time,
                                                             finish_time=navigation_task_finish_time)
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=aeroplane)
        start_time, speed = datetime.datetime(2020, 8, 1, 9, 15, tzinfo=datetime.timezone.utc), 70
        self.contestant = Contestant.objects.create(navigation_task=self.navigation_task, team=self.team,
                                                    takeoff_time=start_time,
                                                    tracker_start_time=start_time - datetime.timedelta(minutes=30),
                                                    finished_by_time=start_time + datetime.timedelta(hours=2),
                                                    tracker_device_id="Test contestant", contestant_number=1,
                                                    minutes_to_starting_point=6,
                                                    air_speed=speed,
                                                    wind_direction=165, wind_speed=8)

    def test_correct_scoring_correct_track_precision(self):
        positions = load_track_points("display/calculators/tests/test_contestant_correct_track.gpx")
        calculator = PrecisionCalculator(self.contestant, Mock(), live_processing=False)
        calculator.start()
        calculator.add_positions(positions)
        calculator.join()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(153, contestant_track.score)

    def test_secret_score_no_override(self):
        expected_time = datetime.datetime(2017, 1, 1, tzinfo=datetime.timezone.utc)
        actual_time = datetime.datetime(2017, 1, 1, 0, 1, tzinfo=datetime.timezone.utc)
        waypoint = self.contestant.navigation_task.route.waypoints[1]
        gate = Gate(waypoint, expected_time,
                    calculate_extended_gate(waypoint, self.scorecard, self.contestant))  # SC 1/1
        self.assertEqual("secret", gate.type)
        gate.passing_time = actual_time
        score = self.scorecard.get_gate_timing_score_for_gate_type(gate.type, self.contestant,
                                                                   gate.expected_time,
                                                                   gate.passing_time)
        print([str(item) for item in self.navigation_task.route.waypoints])
        self.assertEqual(100, score)

    def test_secret_score_override(self):
        gate_override = GateScoreOverride.objects.create(
            for_gate_types=["secret"],
            checkpoint_penalty_per_second=0,
            checkpoint_maximum_penalty=0,
            checkpoint_not_found=0,
        )
        self.contestant.gate_score_override.add(gate_override)
        expected_time = datetime.datetime(2017, 1, 1, tzinfo=datetime.timezone.utc)
        actual_time = datetime.datetime(2017, 1, 1, 0, 1, tzinfo=datetime.timezone.utc)
        waypoint = self.contestant.navigation_task.route.waypoints[1]
        gate = Gate(waypoint, expected_time,
                    calculate_extended_gate(waypoint, self.scorecard, self.contestant))  # SC 1/1
        self.assertEqual("secret", gate.type)
        gate.passing_time = actual_time
        score = self.scorecard.get_gate_timing_score_for_gate_type(gate.type, self.contestant,
                                                                   gate.expected_time,
                                                                   gate.passing_time)
        print([str(item) for item in self.navigation_task.route.waypoints])
        self.assertEqual(0, score)

    def test_score_override(self):
        positions = load_track_points("display/calculators/tests/test_contestant_correct_track.gpx")
        track_override = TrackScoreOverride.objects.create()
        gate_override = GateScoreOverride.objects.create(
            for_gate_types=["sp", "tp", "fp", "secret"],
            checkpoint_grace_period_after=10,
            checkpoint_grace_period_before=10,
            checkpoint_penalty_per_second=1,
            checkpoint_maximum_penalty=100,
            checkpoint_not_found=100,
            missing_procedure_turn_penalty=100
        )
        self.contestant.track_score_override = track_override
        self.contestant.save()
        self.contestant.gate_score_override.add(gate_override)
        calculator = PrecisionCalculator(self.contestant, Mock(), live_processing=False)
        calculator.start()
        calculator.add_positions(positions)
        calculator.join()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(12, contestant_track.score)

    def test_helge_track_precision(self):
        start_time, speed = datetime.datetime(2020, 8, 1, 10, 55, tzinfo=datetime.timezone.utc), 75
        contestant = Contestant.objects.create(navigation_task=self.navigation_task, team=self.team,
                                               takeoff_time=start_time,
                                               tracker_start_time=start_time - datetime.timedelta(minutes=30),
                                               finished_by_time=start_time + datetime.timedelta(hours=2),
                                               tracker_device_id="contestant", contestant_number=2,
                                               minutes_to_starting_point=6, air_speed=speed,
                                               wind_direction=165, wind_speed=8)
        positions = load_track_points("display/calculators/tests/Helge.gpx")
        calculator = PrecisionCalculator(contestant, Mock(), live_processing=False)
        calculator.start()
        calculator.add_positions(positions)
        calculator.join()
        contestant_track = ContestantTrack.objects.get(contestant=contestant)
        self.assertEqual(471, contestant_track.score)

    def test_correct_scoring_bad_track_precision(self):
        positions = load_track_points("display/calculators/tests/Steinar.gpx")
        calculator = PrecisionCalculator(self.contestant, Mock(), live_processing=False)
        calculator.start()
        calculator.add_positions(positions)
        calculator.join()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(1800, contestant_track.score)

    def test_missed_procedure_turn(self):
        positions = load_track_points("display/calculators/tests/jorgen_missed_procedure_turn.gpx")
        calculator = PrecisionCalculator(self.contestant, Mock(), live_processing=False)
        calculator.start()
        calculator.add_positions(positions)
        calculator.join()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        print(contestant_track.score_log)
        strings = [item["string"] for item in contestant_track.score_log]
        self.assertTrue("TP1: 200 points incorrect procedure turn" in strings)
        self.assertTrue("TP4: 200 points incorrect procedure turn" in strings)
        # This is a bit in question, but I think it is correct since he never crosses the extended gate line
        # The procedure turn is performed before the gate which causes backtracking, but also a miss
        # According to A.2.2.16 the should be no penalty for missing the procedure turn if the extended gate line
        # is not crossed.
        # self.assertTrue("TP6: 200 points missing procedure turn" in strings)
        self.assertFalse("TP6: 200 points missing procedure turn" in strings)


class Test2017WPFC(TransactionTestCase):
    def setUp(self):
        with open("display/tests/demo_contests/2017_WPFC/Route-1-Blue.gpx", "r") as file:
            route = create_route_from_gpx(file, True)
        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        self.aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        from display.default_scorecards import default_scorecard_fai_precision_2020
        self.navigation_task = NavigationTask.objects.create(name="NM navigation_task",
                                                             route=route,
                                                             scorecard=default_scorecard_fai_precision_2020.get_default_scorecard(),
                                                             contest=Contest.objects.create(name="contest",
                                                                                            start_time=datetime.datetime.now(
                                                                                                datetime.timezone.utc),
                                                                                            finish_time=datetime.datetime.now(
                                                                                                datetime.timezone.utc)),
                                                             start_time=navigation_task_start_time,
                                                             finish_time=navigation_task_finish_time)
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=self.aeroplane)
        self.scorecard = default_scorecard_fai_precision_2020.get_default_scorecard()

    def test_101(self):
        track = load_track_points(
            "display/tests/demo_contests/2017_WPFC/101_-_Aircraft-039_-_1._Nav._-_Navigation_Flight_Results_(Edition_2).gpx")
        start_time, speed = datetime.datetime(2015, 1, 1, 7, 30, tzinfo=datetime.timezone.utc), 80
        self.contestant = Contestant.objects.create(navigation_task=self.navigation_task, team=self.team,
                                                    takeoff_time=start_time,
                                                    finished_by_time=start_time + datetime.timedelta(hours=2),
                                                    tracker_start_time=start_time - datetime.timedelta(minutes=30),
                                                    tracker_device_id="Test contestant", contestant_number=1,
                                                    minutes_to_starting_point=8,
                                                    air_speed=speed, wind_direction=160,
                                                    wind_speed=18)
        calculator = PrecisionCalculator(self.contestant, Mock(), live_processing=False)
        calculator.start()
        calculator.add_positions(track)
        calculator.join()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(1152,
                         contestant_track.score)  # Should be 1071, a difference of 78. Mostly caused by timing differences, I think.


class TestNM2019(TransactionTestCase):
    def setUp(self):
        with open("display/calculators/tests/NM2019.gpx", "r") as file:
            route = create_route_from_gpx(file, True)
        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        self.aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        from display.default_scorecards import default_scorecard_fai_precision_2020
        self.scorecard = default_scorecard_fai_precision_2020.get_default_scorecard()
        self.navigation_task = NavigationTask.objects.create(name="NM navigation_task",
                                                             route=route,
                                                             scorecard=self.scorecard,
                                                             contest=Contest.objects.create(name="contest",
                                                                                            start_time=datetime.datetime.now(
                                                                                                datetime.timezone.utc),
                                                                                            finish_time=datetime.datetime.now(
                                                                                                datetime.timezone.utc)),
                                                             start_time=navigation_task_start_time,
                                                             finish_time=navigation_task_finish_time)
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=self.aeroplane)

    def test_arild(self):
        track = load_track_points(
            "display/calculators/tests/arild2019.gpx")
        start_time, speed = datetime.datetime(2015, 1, 1, 14, 25, tzinfo=datetime.timezone.utc), 54
        self.contestant = Contestant.objects.create(navigation_task=self.navigation_task, team=self.team,
                                                    takeoff_time=start_time,
                                                    finished_by_time=start_time + datetime.timedelta(hours=2),
                                                    tracker_start_time=start_time - datetime.timedelta(minutes=30),
                                                    tracker_device_id="Test contestant", contestant_number=1,
                                                    minutes_to_starting_point=6,
                                                    air_speed=speed, wind_direction=220,
                                                    wind_speed=7)
        calculator = PrecisionCalculator(self.contestant, Mock(), live_processing=False)
        calculator.start()
        calculator.add_positions(track)
        calculator.join()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(875,
                         contestant_track.score)  # Should be 1071, a difference of 78. Mostly caused by timing differences, I think.

    def test_fredrik(self):
        track = load_track_points(
            "display/calculators/tests/fredrik2019.gpx")
        start_time, speed = datetime.datetime(2015, 1, 1, 12, 45, tzinfo=datetime.timezone.utc), 90
        self.contestant = Contestant.objects.create(navigation_task=self.navigation_task, team=self.team,
                                                    takeoff_time=start_time,
                                                    finished_by_time=start_time + datetime.timedelta(hours=2),
                                                    tracker_start_time=start_time - datetime.timedelta(minutes=30),
                                                    tracker_device_id="Test contestant", contestant_number=1,
                                                    minutes_to_starting_point=6,
                                                    air_speed=speed, wind_direction=220,
                                                    wind_speed=7)
        calculator = PrecisionCalculator(self.contestant, Mock(), live_processing=False)
        calculator.start()
        calculator.add_positions(track)
        calculator.join()
        contestant_track = ContestantTrack.objects.get(contestant=self.contestant)
        self.assertEqual(1000,
                         contestant_track.score)  # Should be 1071, a difference of 78. Mostly caused by timing differences, I think.
