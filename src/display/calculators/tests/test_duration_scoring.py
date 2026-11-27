"""2.B3 Duration scored by the task: the time airborne is Q, P is scaled against the best flight of the task, landing
outside the area costs a percentage of P, and an authored landing gate ends the flight (S18, F14, N3).

The flights come from the flight simulator (`display.calculators.tests.flight_simulator`) and the expected numbers from
the catalogue oracle.
"""

from display.calculators.tests import catalogue_oracle as oracle
from display.calculators.tests.cima_scenario_support import CimaScenarioCase
from display.calculators.tests.flight_simulator import (
    add_contestant,
    build_task,
    duration_flight,
    landing_area_feature,
    local_point,
    runway_gate_feature,
)
from display.calculators.update_score_message import ACHIEVEMENT, PERCENTAGE_PENALTY
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
