"""2.B3 Duration scored by the task: the time airborne is Q, P is scaled against the best flight of the task, landing
outside the area costs a percentage of P, and an authored landing gate ends the flight (S18, F14, N3).

The flights come from the flight simulator (`display.calculators.tests.flight_simulator`) and the expected numbers from
the catalogue oracle.
"""

from display.calculators.tests import catalogue_oracle as oracle
from display.calculators.tests.cima_scenario_support import CimaScenarioCase
from display.calculators.tests.flight_simulator import (
    KNOT_IN_MS,
    Knot,
    Plan,
    add_contestant,
    build_task,
    duration_flight,
    landing_area_feature,
    local_point,
    runway_gate_feature,
    sample_plan,
)
from display.calculators.update_score_message import ACHIEVEMENT, PERCENTAGE_PENALTY
from display.utilities.coordinate_utilities import Projector
from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Scorecard
from display.utilities.task_types import CIMA_DURATION_SCORECARD, DURATION, TASK_TYPE_REGISTRY

START = (60.0, 11.0)
LANDING_ALONG_M = 18000.0
LANDING_AREA = landing_area_feature(START, (17000, 19000), (-500, 500))
# The simulated contestants may fly for two hours at most (finished_by_time).
HOUR, HALF_HOUR, LONGEST = 3600, 1800, 5400


def build(features=(LANDING_AREA,), configure=None):
    return build_task(
        {"type": "FeatureCollection", "features": list(features)},
        task_subtype=DURATION,
        scorecard_shortcut=CIMA_DURATION_SCORECARD,
        configure_scorecard=configure,
    )


def fly(task, airborne_s, across_m=0.0, landing_along_m=LANDING_ALONG_M):
    track = duration_flight(
        START,
        local_point(START, landing_along_m, across_m),
        takeoff_time=task.contestant.takeoff_time,
        airborne_s=airborne_s,
    )
    return task.run(track)


class CimaDurationScorecardTest(CimaScenarioCase):
    def test_the_task_type_has_its_own_scorecard(self):
        create_scorecards()
        scorecard = Scorecard.get_originals().get(shortcut_name=CIMA_DURATION_SCORECARD)
        self.assertEqual(CIMA_DURATION_SCORECARD, TASK_TYPE_REGISTRY[DURATION].scorecard_shortcut_name)
        self.assertEqual("desc", scorecard.score_sorting_direction)
        self.assertEqual("precision", scorecard.calculator)
        self.assertEqual(50, scorecard.duration_landing_area_penalty_percent)
        for gate_type in ("to", "ldg"):
            gate = scorecard.get_gate_scorecard(gate_type)
            self.assertEqual((0, 0, 0), (gate.penalty_per_second, gate.maximum_penalty, gate.missed_penalty))


class DurationScoredByTheTaskTest(CimaScenarioCase):
    def test_the_duration_is_an_achievement_in_minutes(self):
        result = fly(build(), HOUR)
        (message,) = result.messages_of_type("duration_score")
        self.assertEqual(ACHIEVEMENT, message.kind)
        self.assertAlmostEqual(HOUR / 60, message.score, places=6)
        self.assertIn("minutes", message.message)
        self.assertAlmostEqual(HOUR / 60, result.raw_quality, places=6)

    def test_the_score_is_scaled_against_the_best_flight_of_the_task(self):
        task = build()
        second = add_contestant(task)
        longer, shorter = fly(task, HOUR), fly(second, HALF_HOUR)
        expected = oracle.final_scores([oracle.q_duration(s) for s in (HOUR, HALF_HOUR)])
        self.assertEqual([1000, 500], expected)
        self.assertEqual(expected, [longer.score, shorter.score])

    def test_the_best_changes_when_another_contestant_lands(self):
        task = build()
        second, third = add_contestant(task), add_contestant(task)
        first, other = fly(task, HOUR), fly(second, HALF_HOUR)
        self.assertEqual([1000, 500], [first.score, other.score])
        longest = fly(third, LONGEST)
        expected = oracle.final_scores([oracle.q_duration(s) for s in (HOUR, HALF_HOUR, LONGEST)])
        self.assertEqual([667, 333, 1000], expected)
        self.assertEqual(expected, [first.score, other.score, longest.score])

    def test_a_flight_that_never_landed_scores_nothing_and_takes_no_part_in_the_best(self):
        task = build()
        second = add_contestant(task)
        landed = fly(task, HOUR)
        self.assertEqual(1000, landed.score)
        # The second aircraft takes off and is still flying when the track ends: no duration, no points.
        track = duration_flight(
            START,
            local_point(START, LANDING_ALONG_M, 0.0),
            takeoff_time=second.contestant.takeoff_time,
            airborne_s=HOUR,
            hold_after_s=0.0,
        )[: 90 + 600]
        unfinished = second.run(track)
        self.assertEqual(0, unfinished.score)
        self.assertEqual(1000, landed.score)


class DurationLandingAreaTest(CimaScenarioCase):
    def test_landing_outside_the_area_costs_the_scorecards_percentage(self):
        task = build(configure=lambda scorecard: setattr(scorecard, "duration_landing_area_penalty_percent", 20))
        second = add_contestant(task)
        inside, outside = fly(task, HOUR), fly(second, HOUR, across_m=800.0)
        (penalty,) = outside.messages_of_type("duration_landing_area_outside")
        self.assertEqual((PERCENTAGE_PENALTY, 20), (penalty.kind, penalty.score))
        self.assertEqual([], inside.messages_of_type("duration_landing_area_outside"))
        expected = oracle.final_scores([oracle.q_duration(HOUR)] * 2, [[], [0.2]])
        self.assertEqual([1000, 800], expected)
        self.assertEqual(expected, [inside.score, outside.score])

    def test_the_default_penalty_is_the_scorecards_and_not_the_prohibited_zone_penalty(self):
        def configure(scorecard):
            scorecard.prohibited_zone_penalty = 777

        task = build(configure=configure)
        second = add_contestant(task)
        fly(task, HOUR)
        outside = fly(second, HOUR, across_m=800.0)
        self.assertEqual(500, outside.score)
        self.assertEqual(50, outside.percentage_penalty)

    def test_no_penalty_when_the_scorecard_sets_none(self):
        task = build(configure=lambda scorecard: setattr(scorecard, "duration_landing_area_penalty_percent", 0))
        self.assertEqual(1000, fly(task, HOUR, across_m=800.0).score)


class DurationLandingRecognitionTest(CimaScenarioCase):
    def test_the_inferred_landing_is_where_the_aircraft_came_to_rest_not_a_minute_later(self):
        result = fly(build(), HOUR)
        (message,) = result.messages_of_type("duration_airborne_time")
        self.assertEqual(HOUR, (message.actual - message.planned).total_seconds())

    def test_an_authored_landing_gate_ends_the_flight_when_it_is_crossed(self):
        # The aircraft climbs through the take-off gate 100 m after the start and flies through the landing gate 500 m
        # before it stops (the track must cross the lines: it may not start or end on them).
        features = [
            runway_gate_feature("takeoff", START, 100.0),
            runway_gate_feature("landing", START, 17500.0, 1000.0),
            LANDING_AREA,
        ]
        task = build(features=features)
        result = fly(task, HOUR)
        self.assertTrue(result.messages_of_type("gate_score")[-1].message.startswith("passed landing gate"))
        (message,) = result.messages_of_type("duration_airborne_time")
        flown_s = (17500.0 - 100.0) / LANDING_ALONG_M * HOUR
        self.assertAlmostEqual(flown_s, (message.actual - message.planned).total_seconds(), delta=1.0)
        self.assertAlmostEqual(flown_s / 60, result.messages_of_type("duration_score")[0].score, delta=1.0 / 60)
        self.assertEqual(1000, result.score)


class LandingGateOverflightTest(CimaScenarioCase):
    """The authored landing gate of 2.B3 ends the flight only when the aircraft lands at it: an overflight at cruise
    speed, or slowly into wind, must not end the duration."""

    TAKEOFF_ALONG, GATE_ALONG = 100.0, 6000.0
    CRUISE_KT, SLOW_KT = 80.0, 30.0

    def task(self):
        features = [
            runway_gate_feature("takeoff", START, self.TAKEOFF_ALONG),
            runway_gate_feature("landing", START, self.GATE_ALONG, 1000.0),
            LANDING_AREA,
        ]
        return build(features=features)

    def track(self, task, legs):
        """`legs` are (x metres east of START, speed kt) knots after take-off at x=0; the aircraft stands still before
        take-off and after the last knot."""
        projector = Projector(*START)
        knots = [Knot(0.0, 0.0, -90.0), Knot(0.0, 0.0, 0.0)]
        for x, speed_kt in legs:
            previous = knots[-1]
            knots.append(Knot(x, 0.0, previous.t + abs(x - previous.x) / (speed_kt * KNOT_IN_MS)))
        knots.append(Knot(knots[-1].x, 0.0, knots[-1].t + 90.0))
        return sample_plan(Plan(knots, projector, task.contestant.takeoff_time)), knots

    def landing_time(self, result):
        (message,) = result.messages_of_type("duration_airborne_time")
        return (message.actual - message.planned).total_seconds()

    def test_an_overflight_at_cruise_speed_does_not_end_the_flight(self):
        task = self.task()
        # It comes to rest 20 km (about eight minutes) past the gate. A gate is authored, so nothing is inferred from
        # the speed: the landing gate is the only thing that could have ended the flight, and it did not.
        positions, _ = self.track(task, [(self.GATE_ALONG + 20000.0, self.CRUISE_KT)])
        result = task.run(positions)
        self.assertEqual([], result.messages_of_type("duration_airborne_time"))
        self.assertEqual([], result.messages_of_type("duration_score"))

    def test_a_slow_overflight_into_wind_that_flies_on_does_not_end_the_flight(self):
        task = self.task()
        positions, _ = self.track(task, [(self.GATE_ALONG + 30000.0, self.SLOW_KT)])
        result = task.run(positions[:-100])
        self.assertEqual([], result.messages_of_type("duration_airborne_time"))

    def test_a_landing_through_the_gate_ends_the_flight_at_the_crossing(self):
        task = self.task()
        # Cruise, approach at 35 kt through the gate, roll out 100 m further and stop.
        positions, knots = self.track(
            task, [(self.GATE_ALONG - 1000.0, self.CRUISE_KT), (self.GATE_ALONG + 100.0, 35.0)]
        )
        result = task.run(positions)
        crossing_s = knots[2].t + 1000.0 / (35.0 * KNOT_IN_MS)
        self.assertAlmostEqual(crossing_s, self.landing_time(result), delta=1.5)
        self.assertTrue(result.messages_of_type("gate_score")[-1].message.startswith("passed landing gate"))

    def test_an_overflight_followed_by_a_landing_through_the_gate_gets_the_later_time(self):
        task = self.task()
        gate, cruise = self.GATE_ALONG, self.CRUISE_KT * KNOT_IN_MS
        # Over the gate at cruise speed, a wide loop to the north (clear of the gate line) and back to approach it
        # again at 35 kt, landing 100 m beyond it.
        points = [
            (0.0, 0.0),
            (gate + 500.0, 0.0),
            (gate + 500.0, 6000.0),
            (gate - 1500.0, 6000.0),
            (gate - 1000.0, 0.0),
        ]
        knots = [Knot(0.0, 0.0, -90.0)]
        t = 0.0
        for index, (x, y) in enumerate(points):
            if index:
                t += ((x - points[index - 1][0]) ** 2 + (y - points[index - 1][1]) ** 2) ** 0.5 / cruise
            knots.append(Knot(x, y, t))
        first_crossing_s = knots[2].t - 500.0 / cruise
        approach = 35.0 * KNOT_IN_MS
        gate_time = t + 1000.0 / approach
        knots.append(Knot(gate, 0.0, gate_time))
        knots.append(Knot(gate + 100.0, 0.0, gate_time + 100.0 / approach))
        knots.append(Knot(gate + 100.0, 0.0, knots[-1].t + 90.0))
        result = task.run(sample_plan(Plan(knots, Projector(*START), task.contestant.takeoff_time)))
        self.assertAlmostEqual(gate_time, self.landing_time(result), delta=1.5)
        self.assertGreater(self.landing_time(result), first_crossing_s + 100.0)
