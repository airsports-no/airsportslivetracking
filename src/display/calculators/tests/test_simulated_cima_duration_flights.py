"""Scenario tests: synthetic flights through the real calculators for CIMA 2.B3 (Duration).

The catalogue: fly as long as possible on a limited amount of fuel; the longest flight scores the task value and the
others in proportion (P = 1000 x Q / Qmax with Q the time airborne); landing outside the specified area is penalised as
briefed; a quarantine breach or flight in a prohibited area costs 100%.

The route has no backbone and no take-off or landing gate, the case the application handles by inferring take-off and
landing from the speed (the aircraft stands still, flies, and stands still again). The application recognises
touchdown after a minute at rest, so the duration it sees is the time airborne plus that minute, the same for every
pilot (SPEED_INFERENCE_DELAY_S); the oracle is given the duration as recognised. The landing area is a rectangle
2 km long on the line of flight.

Tests marked xfail(strict=True) are known disagreements of the application, with the finding and the slice of
docs/PLAN_task_scoring_reliability.md that will fix them.
"""

import pytest

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
from display.utilities.cima_task_type_definitions import DURATION

START = (60.0, 11.0)
LANDING_ALONG_M = 18000.0
SPEED_INFERENCE_DELAY_S = 59  # touchdown is recognised at the 60th low-speed sample
LONG_S, SHORT_S = 3600, 1800
LANDING_AREA = landing_area_feature(START, (17000, 19000), (-500, 500))


def build(raw_minutes=False, landing_penalty=0.0, features=(LANDING_AREA,)):
    def configure(scorecard):
        if raw_minutes:
            scorecard.duration_normalization_policy = "raw_minutes"
        scorecard.prohibited_zone_penalty = landing_penalty

    return build_task(
        {"type": "FeatureCollection", "features": list(features)},
        task_subtype=DURATION,
        scorecard_shortcut="CIMA Precision",
        configure_scorecard=configure,
    )


def fly(task, airborne_s, across_m=0.0):
    """Fly `airborne_s` seconds and land on the line of flight, `across_m` metres south of it (outside the landing area
    beyond 500 m); the score of the flight."""
    track = duration_flight(
        START,
        local_point(START, LANDING_ALONG_M, across_m),
        takeoff_time=task.contestant.takeoff_time,
        airborne_s=airborne_s,
    )
    return task.run(track)


def recognised_duration(airborne_s):
    return airborne_s + SPEED_INFERENCE_DELAY_S


class DurationFlightsTest(CimaScenarioCase):
    def test_the_application_sees_the_time_airborne_plus_the_minute_at_rest(self):
        result = fly(build(raw_minutes=True), LONG_S)
        (message,) = result.messages_of_type("duration_airborne_time")
        self.assertEqual((message.actual - message.planned).total_seconds(), recognised_duration(LONG_S))

    def test_a_single_flight_scores_the_task_value(self):
        task = build()
        expected = oracle.final_scores([oracle.q_duration(recognised_duration(LONG_S))])
        self.assertEqual(expected, [1000])
        self.assertEqual(fly(task, LONG_S).score, expected[0])

    @pytest.mark.xfail(
        strict=True,
        reason="F14 / S18: no CIMA scorecard scores the duration (the policy is empty by "
        "default): the pilot who flew an hour and the one who flew half an hour "
        "both score 1000",
    )
    def test_the_longer_flight_scores_higher_on_the_default_scorecard(self):
        task = build()
        second = add_contestant(task)
        longer, shorter = fly(task, LONG_S).score, fly(second, SHORT_S).score
        expected = oracle.final_scores([oracle.q_duration(recognised_duration(s)) for s in (LONG_S, SHORT_S)])
        self.assertEqual(expected, [1000, 508])
        self.assertEqual((longer, shorter), tuple(expected))

    @pytest.mark.xfail(
        strict=True,
        reason="F14 / S18: with the only scoring the application has (raw minutes) the "
        "duration is a penalty: the longer flight scores LOWER (939 against 969) "
        "and no flight scores the task value",
    )
    def test_the_longer_flight_scores_higher_with_raw_minutes(self):
        task = build(raw_minutes=True)
        second = add_contestant(task)
        longer, shorter = fly(task, LONG_S).score, fly(second, SHORT_S).score
        expected = oracle.final_scores([oracle.q_duration(recognised_duration(s)) for s in (LONG_S, SHORT_S)])
        self.assertGreater(longer, shorter, "the longest flight must score the most")
        self.assertEqual((longer, shorter), tuple(expected))

    @pytest.mark.xfail(
        strict=True,
        reason="F14 / S18: the landing-area penalty is a number of points subtracted from "
        "the score (0 in the CIMA scorecard, 100 here), not the percentage of the "
        "score the briefing sets (50% here)",
    )
    def test_landing_outside_the_area_costs_the_briefed_penalty(self):
        task = build(raw_minutes=True, landing_penalty=100)
        second = add_contestant(task)
        inside, outside = fly(task, LONG_S), fly(second, LONG_S, across_m=800.0)
        self.assertTrue(outside.messages_of_type("duration_landing_area_outside"))
        self.assertFalse(inside.messages_of_type("duration_landing_area_outside"))
        qs = [oracle.q_duration(recognised_duration(LONG_S))] * 2
        expected = oracle.final_scores(qs, [[], [0.5]])
        self.assertEqual(expected, [1000, 500])
        self.assertEqual((inside.score, outside.score), tuple(expected))

    @pytest.mark.xfail(
        strict=True,
        reason="NEW: with a landing gate authored the landing is never recognised: "
        "TakeoffAndLandingGateCalculator only looks for the landing gate after the "
        "finish point (takeoff_and_landing_gate_calculator.py: "
        "state.has_passed_finishpoint), and 2.B3 has none; the duration is never "
        "scored and the gate counts as missed",
    )
    def test_an_authored_landing_gate_is_recognised(self):
        features = [
            runway_gate_feature("takeoff", START, 0.0),
            runway_gate_feature("landing", START, LANDING_ALONG_M, 1000.0),
            LANDING_AREA,
        ]
        task = build(raw_minutes=True, features=features)
        result = fly(task, LONG_S)
        self.assertEqual(result.messages_of_type("gate_score")[-1].message, "passed landing gate")
        self.assertTrue(result.messages_of_type("duration_airborne_time"), "the duration was never scored")
