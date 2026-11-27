"""Scenario tests: synthetic flights through the real calculators for CIMA 2.A1 and 2.A2, against the catalogue oracle.

2.A1 Curve navigation with time estimation (Qh = 1000 x H / Nh, Qt = Emax x Nt - Et) and 2.A2 Precision navigation
(180 per hidden gate crossed once, one negative point per second of error, Emax for a gate not crossed). The route is
the standard one of the scenario tests (SP, TP1, TP2, FP and four hidden gates). Every test asserts what the catalogue
prescribes; tests marked xfail(strict=True) are known disagreements of the application, with the finding and the slice
of docs/PLAN_task_scoring_reliability.md that will fix them.

The pilot's quality Q comes from the catalogue oracle and the geometry of the flown track (which gate lines were crossed,
in which direction, how many seconds late). The final score P is Q against a perfect flight of a reference pilot in the
same task (Qmax is the best Q of the task); tests with two real pilots in one task are marked as such.
"""

import datetime

import pytest

from display.calculators.tests import catalogue_oracle as oracle
from display.calculators.tests.cima_scenario_support import (
    BACKTRACKING_LEG,
    BRIEF_LOOP,
    BRIEF_LOOP_GAP_S,
    HIDDEN_GATES,
    HIDDEN_NAMES,
    CimaScenarioCase,
    allow_brief_backtracking,
    correct_gate_count,
    first_crossing_errors,
)
from display.calculators.tests.flight_simulator import (
    DoubleCrossing,
    MissGate,
    Reverse,
    TimeOffset,
    VisitOrder,
    WrongDirectionCrossing,
    add_contestant,
    build_task,
    precision_route_geojson,
)
from display.utilities.task_types import CURVE_NAVIGATION_TIME_ESTIMATION, PRECISION_NAVIGATION

BACKTRACKING = [oracle.BACKTRACKING_PENALTY]
LATE_TAIL = 200  # seconds: more than Emax, the rest of the flight is late by it


def late_from(gate: str, seconds: float, following: list[str]) -> list[TimeOffset]:
    """Be `seconds` late at `gate` and at every gate after it (so that the legs after it keep their length). The last
    gate is moved first, as each move has to fit between its neighbours."""
    return [TimeOffset(name, seconds) for name in reversed([gate, *following])]


class CurveNavigationFlightsTest(CimaScenarioCase):
    """2.A1: time gates TP1 and TP2 (SP and FP are not time gates), four hidden gates."""

    TIME_GATES = ["TP1", "TP2"]
    PERFECT_Q = oracle.q_curve_navigation(4, 4, [0, 0])

    def build(self, brief_loops=True):
        self.task = build_task(
            precision_route_geojson(hidden_gates=HIDDEN_GATES, curved=["TP1"]),
            task_subtype=CURVE_NAVIGATION_TIME_ESTIMATION,
            scorecard_shortcut="CIMA Precision",
            configure_scorecard=allow_brief_backtracking if brief_loops else None,
            whole_second_gate_times=True,
        )
        times = self.task.gate_times
        predictions = {name: times[name].isoformat() for name in self.TIME_GATES}
        self.task = self.task.declare({"known_time_gate_predictions": predictions})
        self.assertTrue(self.task.contestant.contestanttaskconfiguration.is_valid)

    def fly(self, *deviations, backtracking=False, **options):
        self.fly_reference_pilot()
        track = self.task.generate_track(list(deviations), **options)
        result = self.task.run(track)
        crossings = self.task.crossings(track, [*self.TIME_GATES, *HIDDEN_NAMES])
        q = oracle.q_curve_navigation(
            len(HIDDEN_NAMES),
            correct_gate_count(crossings, HIDDEN_NAMES),
            first_crossing_errors(crossings, self.TIME_GATES),
        )
        expected = self.final_against_reference(q, self.PERFECT_Q, BACKTRACKING if backtracking else ())
        return result, expected

    def test_perfect_flight_scores_the_task_value(self):
        self.build()
        result, expected = self.fly()
        self.assertEqual(expected, 1000)
        self.assert_final_score(result, expected, "perfect flight")

    def test_small_timing_error_at_a_time_gate(self):
        # The application's Q (a worst case of 1440 including SP and FP) and the catalogue's (1360) differ, but both
        # give 994 for 8 s of error because the score is a rounded share of the best pilot's Q
        self.build()
        result, expected = self.fly(TimeOffset("TP1", 8))
        self.assertEqual(expected, oracle.round_half_up(1000 * (1360 - 8) / 1360))
        self.assert_final_score(result, expected, "TP1 8 s late")

    def test_large_timing_error_at_a_time_gate(self):
        self.build()
        result, expected = self.fly(TimeOffset("TP2", -35))
        self.assert_final_score(result, expected, "TP2 35 s early")

    def test_timing_error_beyond_emax_counts_emax(self):
        self.build()
        result, expected = self.fly(*late_from("TP2", LATE_TAIL, ["HG3", "HG4", "FP"]), lead_out_s=LATE_TAIL + 60)
        self.assertEqual(expected, oracle.round_half_up(1000 * (1360 - 180) / 1360))
        self.assert_final_score(result, expected, "TP2 200 s late")

    def test_hidden_gate_missed(self):
        self.build()
        result, expected = self.fly(MissGate("HG2", margin_m=100))
        self.assertEqual(expected, oracle.round_half_up(1000 * (750 + 360) / 1360))
        self.assert_final_score(result, expected, "HG2 missed")

    def test_hidden_gate_crossed_twice_is_invalidated(self):
        self.build()
        result, expected = self.fly(DoubleCrossing("HG2", gap_s=BRIEF_LOOP_GAP_S, **BRIEF_LOOP))
        self.assertEqual(expected, oracle.round_half_up(1000 * (750 + 360) / 1360))
        self.assertTrue(result.messages_of_type("curve_navigation_repeated_crossing"), "no invalidation message")
        self.assert_final_score(result, expected, "HG2 crossed twice")

    def test_hidden_gate_crossed_in_the_wrong_direction(self):
        self.build()
        result, expected = self.fly(WrongDirectionCrossing("HG2", **BRIEF_LOOP))
        self.assertEqual(expected, oracle.round_half_up(1000 * (750 + 360) / 1360))
        self.assert_final_score(result, expected, "HG2 crossed against the route")

    def test_gates_flown_out_of_order(self):
        self.build(brief_loops=False)
        result, expected = self.fly(VisitOrder(["HG1", "HG2", "HG4", "HG3"]), backtracking=True)
        self.assert_final_score(result, expected, "HG4 before HG3")

    @pytest.mark.xfail(
        strict=True,
        reason="SIM: the scenario cannot be flown on the curved first leg: Reverse needs the 10 s between SP and the "
        "next named point of the plan, which is the first curve point 8 s on (ValueError 'Deviations do not fit'); "
        "backtracking on the straight leg after the curve is tested in test_simulated_cima_backtracking_flights.py",
    )
    def test_backtracking_on_a_leg_costs_half_the_score(self):
        self.build(brief_loops=False)
        result, expected = self.fly(Reverse(BACKTRACKING_LEG, seconds=10, fraction=0.25), backtracking=True)
        self.assertEqual(expected, 500)
        self.assert_final_score(result, expected, "10 s backwards on the leg")

    def test_two_pilots_in_the_same_task_are_scored_against_the_best(self):
        self.build()
        second = add_contestant(self.task).declare(
            {"known_time_gate_predictions": {name: self.task.gate_times[name].isoformat() for name in self.TIME_GATES}}
        )
        track_a = self.task.generate_track([MissGate("HG4", margin_m=100)])
        track_b = second.generate_track([TimeOffset("TP1", 30), MissGate("HG2", margin_m=100)])
        a, b = self.task.run(track_a), second.run(track_b)
        qs = []
        for task, track in ((self.task, track_a), (second, track_b)):
            crossings = task.crossings(track, [*self.TIME_GATES, *HIDDEN_NAMES])
            qs.append(
                oracle.q_curve_navigation(
                    4, correct_gate_count(crossings, HIDDEN_NAMES), first_crossing_errors(crossings, self.TIME_GATES)
                )
            )
        expected = oracle.final_scores(qs)
        self.assertEqual(expected[0], 1000)  # nobody flew perfectly: the better of the two is the best of the task
        self.assertLess(expected[1], 1000)
        self.assertEqual((a.score, b.score), tuple(expected))


class PrecisionNavigationFlightsTest(CimaScenarioCase):
    """2.A2: every turn point, the finish and every hidden gate are time gates (SP is time zero)."""

    TIME_GATES = ["TP1", "TP2", "FP", *HIDDEN_NAMES]
    PERFECT_Q = oracle.q_precision_navigation(4, [0] * 7)

    def build(self, brief_loops=True):
        self.task = build_task(
            precision_route_geojson(hidden_gates=HIDDEN_GATES, hidden_timing=True),
            task_subtype=PRECISION_NAVIGATION,
            scorecard_shortcut="CIMA Precision",
            configure_scorecard=allow_brief_backtracking if brief_loops else None,
            whole_second_gate_times=True,
        )
        self.task = self.task.declare({"known_time_gate_predictions": self.perfect_predictions(self.task)})
        self.assertTrue(self.task.contestant.contestanttaskconfiguration.is_valid)

    @staticmethod
    def perfect_predictions(task, omit=()):
        times = task.gate_times
        names = [w.name for w in task.navigation_task.route.waypoints if w.name not in omit]
        return {name: times[name].isoformat() for name in names}

    def fly(self, *deviations, backtracking=False, **options):
        self.fly_reference_pilot()
        track = self.task.generate_track(list(deviations), **options)
        result = self.task.run(track)
        crossings = self.task.crossings(track, self.TIME_GATES)
        q = oracle.q_precision_navigation(
            correct_gate_count(crossings, HIDDEN_NAMES), first_crossing_errors(crossings, self.TIME_GATES)
        )
        expected = self.final_against_reference(q, self.PERFECT_Q, BACKTRACKING if backtracking else ())
        return result, expected

    def test_perfect_flight_scores_the_task_value(self):
        self.build()
        result, expected = self.fly()
        self.assertEqual(expected, 1000)
        self.assert_final_score(result, expected, "perfect flight")

    def test_small_timing_error_at_a_turn_point(self):
        self.build()
        result, expected = self.fly(TimeOffset("TP1", 8))
        self.assertEqual(expected, oracle.round_half_up(1000 * (720 - 8) / 720))
        self.assert_final_score(result, expected, "TP1 8 s late")

    def test_large_timing_error_at_a_hidden_gate(self):
        self.build()
        # 15 s, not 30: the simulator crosses HG1 29.62 s late for a requested 30, which the application (whose crossing
        # time is about 0.2 s earlier than the simulator's) rounds to 29 s and the oracle to 30. Errors whose crossing
        # time ends in .5 to .75 s are ambiguous between them; 15 s ends in .81.
        result, expected = self.fly(TimeOffset("HG1", 15))
        self.assert_final_score(result, expected, "HG1 15 s late")

    def test_timing_error_beyond_emax_counts_emax(self):
        self.build()
        result, expected = self.fly(TimeOffset("FP", LATE_TAIL), lead_out_s=LATE_TAIL + 60)
        self.assertEqual(expected, oracle.round_half_up(1000 * (720 - 180) / 720))
        self.assert_final_score(result, expected, "FP 200 s late")

    def test_hidden_gate_missed(self):
        self.build()
        result, expected = self.fly(MissGate("HG2", margin_m=100))
        self.assertEqual(expected, oracle.round_half_up(1000 * (720 - 360) / 720))
        self.assert_final_score(result, expected, "HG2 missed")

    def test_hidden_gate_crossed_twice_is_invalidated(self):
        self.build()
        result, expected = self.fly(DoubleCrossing("HG2", gap_s=BRIEF_LOOP_GAP_S, **BRIEF_LOOP))
        self.assertLess(expected, 1000)
        perfect = self.task.run(self.task.generate_track([]))
        self.assertLess(result.score, perfect.score, "crossing a hidden gate twice must cost the gate")
        self.assert_final_score(result, expected, "HG2 crossed twice")

    def test_hidden_gate_crossed_in_the_wrong_direction(self):
        self.build()
        result, expected = self.fly(WrongDirectionCrossing("HG2", **BRIEF_LOOP))
        self.assert_final_score(result, expected, "HG2 crossed against the route")

    def test_gates_flown_out_of_order(self):
        self.build(brief_loops=False)
        result, expected = self.fly(VisitOrder(["HG1", "HG2", "HG4", "HG3"]), backtracking=True)
        self.assert_final_score(result, expected, "HG4 before HG3")

    def test_backtracking_on_a_leg_costs_half_the_score(self):
        self.build(brief_loops=False)
        result, expected = self.fly(Reverse(BACKTRACKING_LEG, seconds=10, fraction=0.25), backtracking=True)
        self.assertEqual(expected, 500)
        self.assert_final_score(result, expected, "10 s backwards on the leg")

    def test_a_declaration_of_the_turn_points_and_the_finish_is_complete(self):
        self.build()
        declaration = self.perfect_predictions(self.task, omit=["SP", *HIDDEN_NAMES])
        self.assertEqual(sorted(declaration), ["FP", "TP1", "TP2"])
        declared = self.task.declare({"known_time_gate_predictions": declaration})
        config = declared.contestant.contestanttaskconfiguration
        self.assertTrue(config.is_valid, config.validation_errors)

    def test_hidden_gate_times_follow_the_declared_turn_points(self):
        self.build()
        scheduled = dict(self.task.gate_times)
        delay = datetime.timedelta(seconds=60)
        declaration = self.perfect_predictions(self.task, omit=["SP", *HIDDEN_NAMES])
        declaration["TP2"] = (scheduled["TP2"] + delay).isoformat()
        declaration["FP"] = (scheduled["FP"] + delay).isoformat()

        times = self.task.declare({"known_time_gate_predictions": declaration}).gate_times

        self.assertEqual(times["SP"], scheduled["SP"])
        self.assertEqual(times["TP1"], scheduled["TP1"])
        self.assertEqual(times["TP2"], scheduled["TP2"] + delay)
        # both gates on the last leg move with the whole leg, the two before TP2 move in proportion to their place
        self.assertEqual(times["HG3"] - scheduled["HG3"], delay)
        self.assertEqual(times["HG4"] - scheduled["HG4"], delay)
        shifts = [(times[name] - scheduled[name]).total_seconds() for name in ("HG1", "HG2")]
        self.assertTrue(0 < shifts[0] < shifts[1] < 60, shifts)

    def test_two_pilots_in_the_same_task_are_scored_against_the_best(self):
        self.build()
        second = add_contestant(self.task).declare({"known_time_gate_predictions": self.perfect_predictions(self.task)})
        track_a = self.task.generate_track([MissGate("HG4", margin_m=100)])
        track_b = second.generate_track([TimeOffset("TP1", 30), MissGate("HG2", margin_m=100)])
        a, b = self.task.run(track_a), second.run(track_b)
        qs = []
        for task, track in ((self.task, track_a), (second, track_b)):
            crossings = task.crossings(track, self.TIME_GATES)
            qs.append(
                oracle.q_precision_navigation(
                    correct_gate_count(crossings, HIDDEN_NAMES), first_crossing_errors(crossings, self.TIME_GATES)
                )
            )
        expected = oracle.final_scores(qs)
        self.assertEqual(expected[0], 1000)  # nobody flew perfectly: the better of the two is the best of the task
        self.assertLess(expected[1], 1000)
        self.assertEqual((a.score, b.score), tuple(expected))
