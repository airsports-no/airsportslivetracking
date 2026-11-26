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
from display.utilities.cima_task_type_definitions import CURVE_NAVIGATION_TIME_ESTIMATION, PRECISION_NAVIGATION

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
            precision_route_geojson(hidden_gates=HIDDEN_GATES),
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

    @pytest.mark.xfail(
        strict=True,
        reason="F2 / S12: the application divides by a theoretical worst case of 1440 "
        "(every gate, SP and FP included) and does not round; the catalogue "
        "divides by the best pilot's Qh + Qt (1360)",
    )
    def test_small_timing_error_at_a_time_gate(self):
        self.build()
        result, expected = self.fly(TimeOffset("TP1", 8))
        self.assertEqual(expected, oracle.round_half_up(1000 * (1360 - 8) / 1360))
        self.assert_final_score(result, expected, "TP1 8 s late")

    @pytest.mark.xfail(
        strict=True,
        reason="F2 / S12: Qt = Emax x Nt - Et against the best pilot's Q; the application "
        "takes the error over a worst case of 1440 (all gates, S9)",
    )
    def test_large_timing_error_at_a_time_gate(self):
        self.build()
        result, expected = self.fly(TimeOffset("TP2", -35))
        self.assert_final_score(result, expected, "TP2 35 s early")

    @pytest.mark.xfail(
        strict=True,
        reason="F2 / S12: the application also times FP (late as well in this flight, "
        "another 180) and divides by 1440; the catalogue counts TP2 at Emax only",
    )
    def test_timing_error_beyond_emax_counts_emax(self):
        self.build()
        result, expected = self.fly(*late_from("TP2", LATE_TAIL, ["HG3", "HG4", "FP"]), lead_out_s=LATE_TAIL + 60)
        self.assertEqual(expected, oracle.round_half_up(1000 * (1360 - 180) / 1360))
        self.assert_final_score(result, expected, "TP2 200 s late")

    @pytest.mark.xfail(
        strict=True,
        reason="F2 / S12: a missed hidden gate costs 1000 / Nh = 250 of Qh in the "
        "catalogue; the application subtracts the missed penalty (180) of 1440",
    )
    def test_hidden_gate_missed(self):
        self.build()
        result, expected = self.fly(MissGate("HG2", margin_m=100))
        self.assertEqual(expected, oracle.round_half_up(1000 * (750 + 360) / 1360))
        self.assert_final_score(result, expected, "HG2 missed")

    @pytest.mark.xfail(
        strict=True,
        reason="F1 / S11: a hidden gate crossed twice is never invalidated (the check for "
        "a repeated crossing is dead code: the gate is no longer outstanding)",
    )
    def test_hidden_gate_crossed_twice_is_invalidated(self):
        self.build()
        result, expected = self.fly(DoubleCrossing("HG2", gap_s=BRIEF_LOOP_GAP_S, **BRIEF_LOOP))
        self.assertEqual(expected, oracle.round_half_up(1000 * (750 + 360) / 1360))
        self.assertTrue(result.messages_of_type("curve_navigation_repeated_crossing"), "no invalidation message")
        self.assert_final_score(result, expected, "HG2 crossed twice")

    @pytest.mark.xfail(
        strict=True,
        reason="F2 / S12: against the route the gate counts as missed: 180 of 1440 in the "
        "application, 1000 / Nh = 250 of Qh in the catalogue",
    )
    def test_hidden_gate_crossed_in_the_wrong_direction(self):
        self.build()
        result, expected = self.fly(WrongDirectionCrossing("HG2", **BRIEF_LOOP))
        self.assertEqual(expected, oracle.round_half_up(1000 * (750 + 360) / 1360))
        self.assert_final_score(result, expected, "HG2 crossed against the route")

    @pytest.mark.xfail(
        strict=True,
        reason="F1 / S11: HG3 and HG4 are crossed twice (once each way) and not "
        "invalidated; F15 / S19: backtracking is a flat 200, not 50% of P",
    )
    def test_gates_flown_out_of_order(self):
        self.build(brief_loops=False)
        result, expected = self.fly(VisitOrder(["HG1", "HG2", "HG4", "HG3"]), backtracking=True)
        self.assert_final_score(result, expected, "HG4 before HG3")

    @pytest.mark.xfail(
        strict=True,
        reason="F15 / S19: backtracking costs a flat 200 points; the catalogue takes 50% of the final score",
    )
    def test_backtracking_on_a_leg_costs_half_the_score(self):
        self.build(brief_loops=False)
        result, expected = self.fly(Reverse(BACKTRACKING_LEG, seconds=10, fraction=0.25), backtracking=True)
        self.assertEqual(expected, 500)
        self.assert_final_score(result, expected, "10 s backwards on the leg")

    @pytest.mark.xfail(
        strict=True,
        reason="S9: Qmax is the best Q of the task; the application scores every pilot "
        "against a theoretical worst case of 1440 (F2 / S12 for the weights)",
    )
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

    @pytest.mark.xfail(
        strict=True,
        reason="S9: the application divides the error by a worst case of 1440 points "
        "and does not round, the catalogue by the best pilot's Q (720 here)",
    )
    def test_small_timing_error_at_a_turn_point(self):
        self.build()
        result, expected = self.fly(TimeOffset("TP1", 8))
        self.assertEqual(expected, oracle.round_half_up(1000 * (720 - 8) / 720))
        self.assert_final_score(result, expected, "TP1 8 s late")

    @pytest.mark.xfail(strict=True, reason="S9: Qmax is the best pilot's Q, not a theoretical worst case")
    def test_large_timing_error_at_a_hidden_gate(self):
        self.build()
        result, expected = self.fly(TimeOffset("HG1", 30))
        self.assert_final_score(result, expected, "HG1 30 s late")

    @pytest.mark.xfail(
        strict=True,
        reason="S9: the application's Qmax is a worst case of 1440, the catalogue's the best pilot's Q (720)",
    )
    def test_timing_error_beyond_emax_counts_emax(self):
        self.build()
        result, expected = self.fly(TimeOffset("FP", LATE_TAIL), lead_out_s=LATE_TAIL + 60)
        self.assertEqual(expected, oracle.round_half_up(1000 * (720 - 180) / 720))
        self.assert_final_score(result, expected, "FP 200 s late")

    @pytest.mark.xfail(
        strict=True,
        reason="NEW (S13/S9): a missed hidden gate loses its 180 points AND counts Emax "
        "as a time error in the catalogue (360 of 720); the application charges "
        "the missed penalty once (180 of 1440)",
    )
    def test_hidden_gate_missed(self):
        self.build()
        result, expected = self.fly(MissGate("HG2", margin_m=100))
        self.assertEqual(expected, oracle.round_half_up(1000 * (720 - 360) / 720))
        self.assert_final_score(result, expected, "HG2 missed")

    @pytest.mark.xfail(
        strict=True,
        reason="F1 / S11: a hidden gate crossed twice is never invalidated in 2.A2 "
        "(the gate keeps the 180 points; the application charges nothing)",
    )
    def test_hidden_gate_crossed_twice_is_invalidated(self):
        self.build()
        result, expected = self.fly(DoubleCrossing("HG2", gap_s=BRIEF_LOOP_GAP_S, **BRIEF_LOOP))
        self.assertLess(expected, 1000)
        perfect = self.task.run(self.task.generate_track([]))
        self.assertLess(result.score, perfect.score, "crossing a hidden gate twice must cost the gate")
        self.assert_final_score(result, expected, "HG2 crossed twice")

    @pytest.mark.xfail(
        strict=True,
        reason="S9: both lose 180 points (the first crossing still gives the time), "
        "but the application divides by 1440, the catalogue by the best Q (720)",
    )
    def test_hidden_gate_crossed_in_the_wrong_direction(self):
        self.build()
        result, expected = self.fly(WrongDirectionCrossing("HG2", **BRIEF_LOOP))
        self.assert_final_score(result, expected, "HG2 crossed against the route")

    @pytest.mark.xfail(
        strict=True,
        reason="F1 / S11: HG3 and HG4 are crossed twice and not invalidated; "
        "F15 / S19: backtracking is 200 points, not 50%",
    )
    def test_gates_flown_out_of_order(self):
        self.build(brief_loops=False)
        result, expected = self.fly(VisitOrder(["HG1", "HG2", "HG4", "HG3"]), backtracking=True)
        self.assert_final_score(result, expected, "HG4 before HG3")

    @pytest.mark.xfail(
        strict=True,
        reason="F15 / S19: backtracking costs a flat 200 points; the catalogue takes 50% of the final score",
    )
    def test_backtracking_on_a_leg_costs_half_the_score(self):
        self.build(brief_loops=False)
        result, expected = self.fly(Reverse(BACKTRACKING_LEG, seconds=10, fraction=0.25), backtracking=True)
        self.assertEqual(expected, 500)
        self.assert_final_score(result, expected, "10 s backwards on the leg")

    @pytest.mark.xfail(
        strict=True,
        reason="F3 / S13: the pilot is asked to predict SP and every hidden gate; the "
        "catalogue asks for the turn points and the finish only",
    )
    def test_a_declaration_of_the_turn_points_and_the_finish_is_complete(self):
        self.build()
        declaration = self.perfect_predictions(self.task, omit=["SP", *HIDDEN_NAMES])
        self.assertEqual(sorted(declaration), ["FP", "TP1", "TP2"])
        declared = self.task.declare({"known_time_gate_predictions": declaration})
        config = declared.contestant.contestanttaskconfiguration
        self.assertTrue(config.is_valid, config.validation_errors)

    @pytest.mark.xfail(
        strict=True,
        reason="S9: Qmax is the best Q of the task; the application scores every pilot "
        "against a theoretical worst case of 1440",
    )
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
