"""Scenario tests: synthetic flights through the real calculators for CIMA 2.A4 and 2.A5, against the catalogue oracle.

2.A4 Navigation over a known circuit and 2.A5 Navigation with unknown legs score the same way: Qh = Vh x Nh for the
hidden gates correctly crossed, Qt = sum(Vt - Ei) over the time gates crossed, 50% for backtracking, a hidden gate
crossed twice invalid. The route is the standard one of the scenario tests (SP, TP1, TP2, FP, four hidden gates); SP,
TP1, TP2 and FP are the time gates. The briefed values are the scorecard's own, 180 for a hidden gate and for a time
gate, so that the application's worst case (Qmax) equals the perfect pilot's Q of the catalogue and the scenarios show
the differences that are not about the briefing. 2.A4 also has the optional declared time of a turn point and the speed
element; 2.A5's route has an unknown-leg point with extension waypoints and is flown along the true backbone.

Tests marked xfail(strict=True) are known disagreements of the application, with the finding and the slice of
docs/PLAN_task_scoring_reliability.md that will fix them.
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
    LONG_BACKTRACKING_GRACE_S,
    CimaScenarioCase,
    correct_gate_count,
    first_crossing_errors,
    measured_error,
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
    generate_track,
    precision_route_geojson,
)
from display.utilities.cima_task_type_definitions import KNOWN_CIRCUIT, UNKNOWN_LEGS

BACKTRACKING = [oracle.BACKTRACKING_PENALTY]
TIME_GATES = ["SP", "TP1", "TP2", "FP"]
GATE_VALUE = 180.0  # Vh and Vt, as briefed in the scorecard
PERFECT_Q = oracle.q_observation_navigation(4, [0, 0, 0, 0], hidden_value=GATE_VALUE, gate_value=GATE_VALUE)
LATE = 36  # seconds: 36 / 1440 x 1000 is a whole 25 points
VERY_LATE = 200  # more than Vt: the error counts Vt


def configure(brief_loops=True, speed_keeping=False):
    """The scorecard of the scenarios: a long backtracking grace time so that the brief loops of the hidden-gate
    scenarios are not backtracking, and the speed element (a 2.A4 rule of the application) off unless asked for."""

    def configure_scorecard(scorecard):
        if brief_loops:
            scorecard.backtracking_grace_time_seconds = LONG_BACKTRACKING_GRACE_S
        if not speed_keeping:
            scorecard.speed_keeping_penalty_per_kt = 0

    return configure_scorecard


class ObservationNavigationFlights:
    """The scenarios shared by 2.A4 and 2.A5."""

    task_subtype = None
    route_options: dict = {}

    def build(self, brief_loops=True, speed_keeping=False, **route_options):
        options = {**self.route_options, **route_options}
        self.task = build_task(
            precision_route_geojson(hidden_gates=HIDDEN_GATES, **options),
            task_subtype=self.task_subtype,
            scorecard_shortcut="CIMA Precision",
            configure_scorecard=configure(brief_loops, speed_keeping),
            whole_second_gate_times=True,
        )
        self.assertTrue(self.task.contestant.contestanttaskconfiguration.is_valid)
        return self.task

    def quality(self, task, track, time_gates=TIME_GATES):
        crossings = task.crossings(track, [*time_gates, *HIDDEN_NAMES])
        errors = [error for error in first_crossing_errors(crossings, time_gates) if error is not None]
        return oracle.q_observation_navigation(
            correct_gate_count(crossings, HIDDEN_NAMES), errors, hidden_value=GATE_VALUE, gate_value=GATE_VALUE
        )

    def fly(self, *deviations, backtracking=False, **options):
        track = self.task.generate_track(list(deviations), **options)
        result = self.task.run(track)
        expected = self.final_against_reference(
            self.quality(self.task, track), PERFECT_Q, BACKTRACKING if backtracking else ()
        )
        return result, expected

    def test_perfect_flight_scores_the_task_value(self):
        self.build()
        result, expected = self.fly()
        self.assertEqual(expected, 1000)
        self.assert_final_score(result, expected, "perfect flight")

    @pytest.mark.xfail(
        strict=True, reason="S9: the application's score is not rounded to a whole number (994.44 against 994)"
    )
    def test_small_timing_error_at_a_time_gate(self):
        self.build()
        result, expected = self.fly(TimeOffset("TP1", 8))
        self.assertEqual(expected, oracle.round_half_up(1000 * (1440 - 8) / 1440))
        self.assert_final_score(result, expected, "TP1 8 s late")

    def test_large_timing_error_at_a_time_gate(self):
        self.build()
        result, expected = self.fly(TimeOffset("TP2", -LATE))
        self.assertEqual(expected, 975)
        self.assert_final_score(result, expected, "TP2 36 s early")

    def test_timing_error_beyond_the_gate_value_counts_the_gate_value(self):
        self.build()
        result, expected = self.fly(TimeOffset("FP", VERY_LATE), lead_out_s=VERY_LATE + 60)
        self.assertEqual(expected, 875)
        self.assert_final_score(result, expected, "FP 200 s late")

    def test_hidden_gate_missed(self):
        self.build()
        result, expected = self.fly(MissGate("HG2", margin_m=100))
        self.assertEqual(expected, 875)
        self.assert_final_score(result, expected, "HG2 missed")

    def test_hidden_gate_crossed_in_the_wrong_direction(self):
        self.build()
        result, expected = self.fly(WrongDirectionCrossing("HG2", **BRIEF_LOOP))
        self.assertEqual(expected, 875)
        self.assert_final_score(result, expected, "HG2 crossed against the route")

    @pytest.mark.xfail(
        strict=True,
        reason="F1 / S11: a hidden gate crossed twice is never invalidated (it keeps its "
        "points; the application charges nothing)",
    )
    def test_hidden_gate_crossed_twice_is_invalidated(self):
        self.build()
        result, expected = self.fly(DoubleCrossing("HG2", gap_s=BRIEF_LOOP_GAP_S, **BRIEF_LOOP))
        self.assertEqual(expected, 875)
        self.assert_final_score(result, expected, "HG2 crossed twice")

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
        reason="S9: Qmax is the best Q of the task; the application scores every pilot "
        "against the worst case of 1440, so the best of two imperfect pilots "
        "does not get 1000",
    )
    def test_two_pilots_in_the_same_task_are_scored_against_the_best(self):
        self.build()
        second = add_contestant(self.task)
        track_a = self.task.generate_track([MissGate("HG4", margin_m=100)])
        track_b = second.generate_track([TimeOffset("TP1", LATE), MissGate("HG2", margin_m=100)])
        a, b = self.task.run(track_a), second.run(track_b)
        qs = [self.quality(self.task, track_a), self.quality(second, track_b)]
        expected = oracle.final_scores(qs)
        self.assertEqual(expected[0], 1000)
        self.assertEqual(expected[1], 971)  # (1440 - 36 - 180) / (1440 - 180)
        self.assertEqual((a.score, b.score), tuple(expected))


class KnownCircuitFlightsTest(ObservationNavigationFlights, CimaScenarioCase):
    """2.A4: a known circuit; the pilot may declare the time of a turn point; a speed element."""

    task_subtype = KNOWN_CIRCUIT

    def declared_task(self, turn_point: str, seconds_after: int):
        """The task with a declared time for `turn_point`, `seconds_after` seconds after its calculated time."""
        task = self.build()
        declared_time = task.gate_times[turn_point] + datetime.timedelta(seconds=seconds_after)
        return task.declare({"turnpoint_time_overrides": {turn_point: declared_time.isoformat()}})

    def test_a_declared_time_is_the_time_the_gate_is_scored_against(self):
        task = self.declared_task("TP2", LATE)
        self.assertEqual(task.gate_times["TP2"] - self.task.gate_times["TP2"], datetime.timedelta(seconds=LATE))
        track = task.generate_track([])
        result = task.run(track)
        self.assertEqual(self.quality(task, track), PERFECT_Q)
        self.assert_final_score(result, 1000, "flown to the declared time of TP2")

    def test_without_the_declaration_the_same_flight_is_late(self):
        declared = self.declared_task("TP2", LATE)
        track = declared.generate_track([])
        undeclared = self.build()
        result = undeclared.run(track)
        self.assertEqual(measured_error(undeclared.crossings(track, ["TP2"])["TP2"][0]), LATE)
        expected = self.final_against_reference(self.quality(undeclared, track), PERFECT_Q)
        self.assertEqual(expected, 975)
        self.assert_final_score(result, expected, "the declared flight scored without the declaration")

    @pytest.mark.xfail(
        strict=True,
        reason="F7 / S15: the speed element penalises every leg flown off the declared "
        "speed, uncapped, on top of the timing error (about 19 points here); the "
        "catalogue has no such penalty",
    )
    def test_a_timing_error_does_not_cost_a_second_time_through_the_speed_element(self):
        self.build(speed_keeping=True)
        result, expected = self.fly(TimeOffset("TP2", LATE))
        self.assertEqual(expected, 975)
        self.assert_final_score(result, expected, "TP2 36 s late with the speed element on")

    @pytest.mark.xfail(
        strict=True,
        reason="F7 / S15: flying faster than the declared speed costs points in the "
        "application (speed-keeping deviation); in the catalogue the speed is "
        "rewarded (Qv = Vs x S / Smax) or, not included, free",
    )
    def test_flying_faster_than_the_declared_speed_is_not_penalised(self):
        task = build_task(
            precision_route_geojson(hidden_gates=HIDDEN_GATES, untimed=["TP1", "TP2", "FP"]),
            task_subtype=KNOWN_CIRCUIT,
            scorecard_shortcut="CIMA Precision",
            configure_scorecard=configure(speed_keeping=True),
            whole_second_gate_times=True,
        )
        start = task.gate_times["SP"]
        faster = {name: start + (time - start) / 1.2 for name, time in task.gate_times.items()}
        track = generate_track(task.effective_waypoints, faster, projector=task.projector)
        result = task.run(track)
        crossings = task.crossings(track, ["SP", *HIDDEN_NAMES])
        q = oracle.q_observation_navigation(
            correct_gate_count(crossings, HIDDEN_NAMES),
            [error for error in first_crossing_errors(crossings, ["SP"]) if error is not None],
            hidden_value=GATE_VALUE,
            gate_value=GATE_VALUE,
        )
        self.assertEqual(q, 4 * GATE_VALUE + GATE_VALUE)
        self.assert_final_score(result, 1000, "20% faster than declared, only SP timed")


class UnknownLegsFlightsTest(ObservationNavigationFlights, CimaScenarioCase):
    """2.A5: TP1 is an unknown-leg point with two extension waypoints; the pilot flies the true backbone."""

    task_subtype = UNKNOWN_LEGS
    route_options = {"unknown_legs": {"TP1": [(30.0, 3000.0), (60.0, 2000.0)]}}

    def test_the_extension_waypoints_are_not_part_of_the_flown_route(self):
        task = self.build()
        names = [waypoint.name for waypoint in task.effective_waypoints]
        self.assertEqual(names, ["SP", "TP1", "HG1", "HG2", "TP2", "HG3", "HG4", "FP"])
        self.assertEqual(task.effective_waypoints[1].type, "ul")
        result, expected = self.fly()
        self.assertEqual(result.missed_gates, [])
        self.assert_final_score(result, expected, "flown along the backbone")
