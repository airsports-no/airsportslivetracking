"""Scenario tests: backtracking and hidden gate sequences of CIMA 2.A1 and 2.A2 (slices S11 and S19), against the oracle.

Annex 4: "A 50% penalty will be imposed for backtracking. Backtracking is defined in S10 4.24.5": flying at an angle of
more than 90 degrees to the intended flight direction for more than 5 seconds in sequence, within a corridor defined by
the width used to score gates in the task, and not within the turn point radius (the distance from the centre of the turn
point to the outermost intersection of the two leg corridors). Percentage penalties of a pilot add up (the oracle).
Hidden gates: "Crossing the same gate more than once in any direction invalidates the gate. Example: the sequence
1-2-4-3-5-6-5-7 will be evaluated as 1-2-4-6-7, a total of five correct gates."

The route is the standard one of the scenario tests (SP, TP1, TP2, FP; legs of 6000, 5000 and 6000 m, the corridor one
nautical mile wide: 926 m to each side, the turn point radius 926 m at SP and FP and 1130 m at TP1 where the route turns
by 70 degrees).
"""

import math
from dataclasses import dataclass
from typing import Sequence

import pytest

from display.calculators.tests import catalogue_oracle as oracle
from display.calculators.tests.cima_scenario_support import (
    CimaScenarioCase,
    allow_brief_backtracking,
    correct_gate_count,
    first_crossing_errors,
    hidden_crossing_sequence,
)
from display.calculators.tests.flight_simulator import (
    Deviation,
    Plan,
    Reverse,
    _point_on_leg,
    _right,
    _unit,
    build_task,
    precision_route_geojson,
)
from display.utilities.task_types import CURVE_NAVIGATION_TIME_ESTIMATION, PRECISION_NAVIGATION

BACKTRACKING = [oracle.BACKTRACKING_PENALTY]
CORRIDOR_HALF_WIDTH_M = 926.0
HIDDEN_GATES = {2: [0.8, 0.9]}
HIDDEN_NAMES_2 = ["HG1", "HG2"]
SEVEN_HIDDEN_NAMES = [f"HG{number}" for number in range(1, 8)]
# (gate number, direction) of the catalogue's 1-2-4-3-5-6-5-7, the gates counted from 1
CATALOGUE_EXAMPLE = [(1, 1), (2, 1), (4, 1), (3, 1), (5, 1), (6, 1), (5, -1), (7, 1)]


@dataclass
class ExcursionWithReversal(Deviation):
    """Leave the leg that starts at gate `leg` at `fraction` of it, `offset_m` to the right, fly backwards along the leg
    for `reverse_s` seconds there and come back to the leg line. The way out and the way back are at less than 90 degrees
    to the leg, so only the part flown backwards can be backtracking."""

    leg: str
    reverse_s: float
    offset_m: float
    fraction: float = 0.5
    out_m: float = 300.0

    def apply(self, plan: Plan):
        index, t = _point_on_leg(plan, self.leg, self.fraction)
        forward = plan.segment_direction(index)
        right = _right(forward)
        speed = plan.segment_speed(index)
        origin = plan.knots[index]
        back_m = speed * self.reverse_s

        def at(along: float, across: float):
            return origin.x + forward[0] * along + right[0] * across, origin.y + forward[1] * along + right[1] * across

        points = [at(self.out_m, self.offset_m), at(self.out_m - back_m, self.offset_m), at(2 * self.out_m - back_m, 0)]
        length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip([(origin.x, origin.y), *points], points))
        plan.insert_path(index, points, t, t + length / speed)
        plan.validate()


@dataclass
class CrossGatesInSequence(Deviation):
    """Cross the hidden gates on the leg that starts at gate `leg` in the order and directions of `crossings`: pairs of
    (gate number, +1 along the route or -1 against it), the gates being HG1, HG2, ... in route order and lying on that
    leg. Between two crossings the aircraft stays round the ends of the gate lines (`margin_m` beyond them), so each gate
    line is crossed exactly when the sequence says so. The aircraft is back on schedule at the end of the leg."""

    leg: str
    gates: Sequence[str]
    crossings: Sequence[tuple[int, int]]
    distance_m: float = 100.0
    margin_m: float = 100.0
    phase = 40

    def apply(self, plan: Plan):
        start = plan.index_of(self.leg)
        first_gate = plan.index_of(self.gates[0])
        end = plan.index_of(self.gates[-1]) + 1
        origin, destination = plan.knots[start], plan.knots[end]
        forward = _unit(destination.x - origin.x, destination.y - origin.y)
        right = _right(forward)

        def along(knot):
            return (knot.x - origin.x) * forward[0] + (knot.y - origin.y) * forward[1]

        positions = {number: along(plan.knots[first_gate + number - 1]) for number in range(1, len(self.gates) + 1)}
        side = plan.knots[first_gate].width_m / 2.0 + self.margin_m
        d = self.distance_m
        path: list[tuple[float, float]] = []
        current = 0.0
        for number, direction in self.crossings:
            entry = positions[number] - direction * d
            exit_ = positions[number] + direction * d
            lines_between = [p for p in positions.values() if min(current, entry) < p < max(current, entry)]
            if lines_between or entry < current:
                path += [(current, side), (entry, side)]
            path += [(entry, 0.0), (exit_, 0.0)]
            current = exit_
        del plan.knots[start + 1 : end]
        points = [(origin.x + forward[0] * a + right[0] * c, origin.y + forward[1] * a + right[1] * c) for a, c in path]
        plan.insert_path(start, points, origin.t, destination.t, to=(destination.x, destination.y))
        plan.validate()


class PrecisionNavigationBacktrackingTest(CimaScenarioCase):
    """2.A2 on the standard route without hidden gates: time gates TP1, TP2 and FP."""

    # Two hidden gates near the end of the last leg: a task without one has no positive Q, so no pilot scores.
    TIME_GATES = ["TP1", "TP2", "FP", "HG1", "HG2"]
    PERFECT_Q = oracle.q_precision_navigation(2, [0] * 5)

    def setUp(self):
        self.task = build_task(
            precision_route_geojson(hidden_gates=HIDDEN_GATES, hidden_timing=True),
            task_subtype=PRECISION_NAVIGATION,
            scorecard_shortcut="CIMA Precision",
            whole_second_gate_times=True,
        )
        times = self.task.gate_times
        names = [w.name for w in self.task.navigation_task.route.waypoints]
        self.task = self.task.declare(
            {"known_time_gate_predictions": {name: times[name].isoformat() for name in names}}
        )
        self.assertTrue(self.task.contestant.contestanttaskconfiguration.is_valid)

    def fly(self, *deviations, backtracks=0):
        self.fly_reference_pilot()
        track = self.task.generate_track(list(deviations))
        result = self.task.run(track)
        crossings = self.task.crossings(track, self.TIME_GATES)
        q = oracle.q_precision_navigation(
            correct_gate_count(crossings, HIDDEN_NAMES_2), first_crossing_errors(crossings, self.TIME_GATES)
        )
        expected = self.final_against_reference(q, self.PERFECT_Q, BACKTRACKING * backtracks)
        return result, expected

    def backtracks(self, result):
        return result.messages_of_type("backtracking")

    def test_backtracking_inside_the_corridor_costs_half_the_score(self):
        result, expected = self.fly(
            ExcursionWithReversal("SP", reverse_s=10, offset_m=CORRIDOR_HALF_WIDTH_M / 3), backtracks=1
        )
        self.assertEqual(expected, 500)
        self.assertEqual([(m.kind, m.score) for m in self.backtracks(result)], [("percentage_penalty", 50.0)])
        self.assert_final_score(result, expected, "10 s backwards inside the corridor")

    def test_backtracking_outside_the_corridor_is_not_penalised(self):
        result, expected = self.fly(
            ExcursionWithReversal("SP", reverse_s=10, offset_m=CORRIDOR_HALF_WIDTH_M + 300, fraction=0.3)
        )
        self.assertEqual(expected, 1000)
        self.assertEqual(self.backtracks(result), [])
        self.assert_final_score(result, expected, "10 s backwards outside the corridor")

    def test_backtracking_close_to_the_edge_of_the_corridor_is_penalised(self):
        inside, _ = self.fly(ExcursionWithReversal("SP", reverse_s=10, offset_m=CORRIDOR_HALF_WIDTH_M - 50))
        self.assertEqual(len(self.backtracks(inside)), 1)

    def test_backtracking_within_the_turn_point_radius_at_the_start_is_not_penalised(self):
        # 600 m after SP (the radius is 926 m), 8 s backwards (about 300 m)
        result, expected = self.fly(Reverse("SP", seconds=8, fraction=0.1))
        self.assertEqual(self.backtracks(result), [])
        self.assert_final_score(result, expected, "backwards close to SP")

    def test_backtracking_within_the_turn_point_radius_of_a_turn_is_not_penalised(self):
        # 5400 m of the 6000 m to TP1 (600 m before it, the radius there is 1130 m), 6 s backwards (about 230 m)
        result, expected = self.fly(Reverse("SP", seconds=6, fraction=0.9))
        self.assertEqual(self.backtracks(result), [])
        self.assert_final_score(result, expected, "backwards close to TP1")

    def test_backtracking_just_beyond_the_turn_point_radius_is_penalised(self):
        # 1750 m after TP1 (the radius is 1130 m), 10 s backwards (about 400 m)
        result, expected = self.fly(Reverse("TP1", seconds=10, fraction=0.35), backtracks=1)
        self.assertEqual(len(self.backtracks(result)), 1)
        self.assert_final_score(result, expected, "backwards beyond the turn point radius")

    def test_backtracking_for_less_than_five_seconds_is_not_penalised(self):
        result, expected = self.fly(Reverse("SP", seconds=3, fraction=0.5))
        self.assertEqual(expected, 1000)
        self.assertEqual(self.backtracks(result), [])
        self.assert_final_score(result, expected, "3 s backwards")

    def test_backtracking_for_more_than_five_seconds_is_penalised(self):
        result, expected = self.fly(Reverse("SP", seconds=7, fraction=0.5), backtracks=1)
        self.assertEqual(expected, 500)
        self.assert_final_score(result, expected, "7 s backwards")

    def test_two_backtracks_on_different_legs_take_a_percentage_each(self):
        result, expected = self.fly(
            Reverse("SP", seconds=10, fraction=0.4), Reverse("TP2", seconds=10, fraction=0.5), backtracks=2
        )
        self.assertEqual(expected, 0)  # 50% and 50%: all of it
        self.assertEqual([m.score for m in self.backtracks(result)], [50.0, 50.0])
        self.assertEqual(result.percentage_penalty, 100.0)
        self.assert_final_score(result, expected, "two backtracks")

    def test_two_backtracks_on_the_same_leg_take_a_percentage_each(self):
        result, expected = self.fly(
            Reverse("SP", seconds=10, fraction=0.2), Reverse("SP", seconds=10, fraction=0.7), backtracks=2
        )
        self.assertEqual([m.score for m in self.backtracks(result)], [50.0, 50.0])
        self.assert_final_score(result, expected, "two backtracks on one leg")

    def test_a_long_backtrack_is_one_backtrack(self):
        result, expected = self.fly(Reverse("SP", seconds=30, fraction=0.5), backtracks=1)
        self.assertEqual(len(self.backtracks(result)), 1)
        self.assert_final_score(result, expected, "30 s backwards")

    @pytest.mark.xfail(
        strict=True,
        reason="N6 / S19: the microlight clause of S10 4.24.5 (rejoining the active track line at a point prior to the "
        "point where it was left) is not implemented: it needs a threshold for leaving the line, which the rule does "
        "not give. The track leaves the line 300 m out (less than 90 degrees to it), flies 3.5 s backwards (less than "
        "the 5 s) and rejoins 66 m before the point where it left it.",
    )
    def test_rejoining_the_track_line_before_the_point_where_it_was_left_is_backtracking(self):
        result, expected = self.fly(RejoinBeforeLeaving("SP"), backtracks=1)
        self.assertEqual(expected, 500)
        self.assert_final_score(result, expected, "rejoined behind the point where the line was left")


@dataclass
class RejoinBeforeLeaving(Deviation):
    """Leave the track line 300 m to the right (at 84 degrees to it), fly 126 m backwards (3.5 s, less than the five
    seconds that make backtracking by the heading), and return to the line (at 84 degrees to it) 66 m before the point
    where it was left. At no time is the aircraft flying at more than 90 degrees to the line for more than 5 seconds."""

    leg: str
    fraction: float = 0.5

    def apply(self, plan: Plan):
        index, t = _point_on_leg(plan, self.leg, self.fraction)
        forward = plan.segment_direction(index)
        right = _right(forward)
        speed = plan.segment_speed(index)
        origin = plan.knots[index]

        def at(along: float, across: float):
            return origin.x + forward[0] * along + right[0] * across, origin.y + forward[1] * along + right[1] * across

        points = [at(30, 300), at(-96, 300), at(-66, 0)]
        length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip([(origin.x, origin.y), *points], points))
        plan.insert_path(index, points, t, t + length / speed)
        plan.validate()


class CurveNavigationBacktrackingTest(CimaScenarioCase):
    """2.A1: the same 50% for a backtrack on the straight leg after the curved one."""

    TIME_GATES = ["TP1", "TP2"]

    def test_backtracking_costs_half_the_score(self):
        task = build_task(
            precision_route_geojson(hidden_gates=HIDDEN_GATES, curved=["TP1"]),
            task_subtype=CURVE_NAVIGATION_TIME_ESTIMATION,
            scorecard_shortcut="CIMA Precision",
            whole_second_gate_times=True,
        )
        times = task.gate_times
        self.task = task.declare({"known_time_gate_predictions": {n: times[n].isoformat() for n in self.TIME_GATES}})
        self.fly_reference_pilot()
        result = self.task.run(self.task.generate_track([Reverse("TP1", seconds=10, fraction=0.3)]))
        self.assertEqual(
            [(m.kind, m.score) for m in result.messages_of_type("backtracking")], [("percentage_penalty", 50.0)]
        )
        self.assert_final_score(result, 500, "10 s backwards on the leg")


class CatalogueHiddenGateSequenceTest(CimaScenarioCase):
    """2.A1 on a route with seven hidden gates on its second leg: the catalogue's own example, 1-2-4-3-5-6-5-7."""

    TIME_GATES = ["TP1", "TP2"]
    PERFECT_Q = oracle.q_curve_navigation(7, 7, [0, 0])

    def setUp(self):
        self.task = build_task(
            precision_route_geojson(hidden_gates={1: [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]}, curved=["TP1"]),
            task_subtype=CURVE_NAVIGATION_TIME_ESTIMATION,
            scorecard_shortcut="CIMA Precision",
            configure_scorecard=allow_brief_backtracking,
            whole_second_gate_times=True,
        )
        times = self.task.gate_times
        self.task = self.task.declare(
            {"known_time_gate_predictions": {name: times[name].isoformat() for name in self.TIME_GATES}}
        )
        self.assertTrue(self.task.contestant.contestanttaskconfiguration.is_valid)

    def fly(self, crossings):
        self.fly_reference_pilot()
        track = self.task.generate_track([CrossGatesInSequence("TP1", SEVEN_HIDDEN_NAMES, crossings)])
        result = self.task.run(track)
        flown = self.task.crossings(track, [*self.TIME_GATES, *SEVEN_HIDDEN_NAMES])
        # the helper counts the gates from 0
        self.assertEqual(
            hidden_crossing_sequence(flown, SEVEN_HIDDEN_NAMES), [(n - 1, d) for n, d in crossings], "the track flown"
        )
        q = oracle.q_curve_navigation(
            7, correct_gate_count(flown, SEVEN_HIDDEN_NAMES), first_crossing_errors(flown, self.TIME_GATES)
        )
        return result, self.final_against_reference(q, self.PERFECT_Q), flown

    @staticmethod
    def penalised_hidden_gates(result):
        return sorted(
            (m.gate.name, m.score_type, m.score) for m in result.messages if m.gate.name.startswith("HG") and m.score
        )

    def test_the_catalogue_example_has_five_correct_gates(self):
        _, _, flown = self.fly(CATALOGUE_EXAMPLE)
        self.assertEqual(
            oracle.correct_hidden_gates(hidden_crossing_sequence(flown, SEVEN_HIDDEN_NAMES)), [0, 1, 3, 5, 6]
        )

    def test_the_catalogue_example_loses_gates_3_and_5_and_only_those(self):
        result, _, _ = self.fly(CATALOGUE_EXAMPLE)
        # 3 was crossed after 4 (out of order: the crossing of 4 marked it missed), 5 was crossed twice
        self.assertEqual(
            self.penalised_hidden_gates(result),
            [("HG3", "gate_score", 180.0), ("HG5", "curve_navigation_repeated_crossing", 180.0)],
        )

    @pytest.mark.xfail(
        strict=True,
        reason="F2 / S12: the gates lost are the right ones (see the tests above), but the application weighs a gate "
        "180 of a worst case of 1980 where the catalogue takes 1000 / Nh of Qh: 818 against 790",
    )
    def test_the_catalogue_example_scores_as_in_the_catalogue(self):
        result, expected, _ = self.fly(CATALOGUE_EXAMPLE)
        self.assert_final_score(result, expected, "1-2-4-3-5-6-5-7")

    def test_the_gates_in_order_lose_nothing(self):
        result, _, _ = self.fly([(number, 1) for number in range(1, 8)])
        self.assertEqual(self.penalised_hidden_gates(result), [])
        self.assertEqual(result.score, 1000)

    def test_a_gate_crossed_against_the_route_is_lost(self):
        sequence = [(1, 1), (2, 1), (3, -1), (4, 1), (5, 1), (6, 1), (7, 1)]
        result, _, flown = self.fly(sequence)
        self.assertEqual(
            oracle.correct_hidden_gates(hidden_crossing_sequence(flown, SEVEN_HIDDEN_NAMES)), [0, 1, 3, 4, 5, 6]
        )
        self.assertEqual([name for name, *_ in self.penalised_hidden_gates(result)], ["HG3"])
