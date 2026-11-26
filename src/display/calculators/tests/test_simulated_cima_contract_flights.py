"""Scenario tests: synthetic flights through the real calculators for CIMA 2.A3 (Contract navigation with time controls).

The catalogue: the pilot declares a sequence of catalogue turn points with the mandatory MP in it and a time T; SP is
crossed at time zero, MP at T and FP at 2T. V = N - Ep (turn points declared and flown in order minus declared points
not flown or not in order, SP, MP and FP included), Qp = 1000 x V / Vmax, Qt = Emax x 3 - Et over SP, MP and FP,
Q = Qp + Qt, P = 1000 x Q / Qmax, 50% for backtracking. Points declared after MP are invalid when flown before the
time of MP.

The route: SP, MP, FP on a line to the east (9260 m, T = 240 s at 75 kt) and four free catalogue points A, B (before MP)
and C, D (after MP) beside the line. Tests marked xfail(strict=True) are known disagreements of the application, with
the finding and the slice of docs/PLAN_task_scoring_reliability.md that will fix them.
"""

import datetime

import pytest

from display.calculators.tests import catalogue_oracle as oracle
from display.calculators.tests.cima_scenario_support import CimaScenarioCase, first_crossing_errors
from display.calculators.tests.flight_simulator import (
    Reverse,
    SkipGate,
    TimeOffset,
    add_contestant,
    build_task,
    contract_route_geojson,
    generate_track,
)
from display.utilities.cima_task_type_definitions import CONTRACT_NAVIGATION_TIME_CONTROLS

BACKTRACKING = [oracle.BACKTRACKING_PENALTY]
CATALOGUE = {"A": (2500, -1500), "B": (6000, 1500), "C": (12500, -1500), "D": (15500, 1500)}
T_SECONDS = 240
FULL_DECLARATION = {"declared_sequence": ["A", "B", "MP", "C", "D", "FP"], "declared_t_seconds": T_SECONDS}
NO_POINTS_DECLARATION = {"declared_sequence": ["MP", "FP"], "declared_t_seconds": T_SECONDS}
PERFECT_Q = oracle.q_contract_navigation(4, 4, [0, 0, 0])


def build(declaration=FULL_DECLARATION, **options):
    task = build_task(
        contract_route_geojson(catalogue=CATALOGUE),
        task_subtype=CONTRACT_NAVIGATION_TIME_CONTROLS,
        scorecard_shortcut="CIMA Precision",
        whole_second_gate_times=True,
        **options,
    )
    return task.declare(declaration) if declaration else task


def flown_points(task, track, declared: list[str]):
    """(N, Ep, time errors of SP, MP, FP) of a track for the declared sequence, found from the geometry.

    A declared catalogue point counts when it was crossed along the route, after the points declared before it that
    counted and, when declared after MP, not before the time of MP. SP, MP and FP not crossed are declared points not
    flown."""
    mp_index = declared.index("MP")
    points = [name for name in declared if name not in ("MP", "FP")]
    crossings = task.crossings(track, [*points, "SP", "MP", "FP"])
    mp_time = task.gate_times["MP"]
    flown_in_order, last_time = 0, None
    for name in points:
        times = [c.time for c in crossings[name] if c.direction == 1]
        if not times or (last_time is not None and times[0] <= last_time):
            continue
        if declared.index(name) > mp_index and times[0] < mp_time:
            continue
        flown_in_order += 1
        last_time = times[0]
    mandatory = ["SP", "MP", "FP"]
    errors = first_crossing_errors(crossings, mandatory)
    not_flown = len(points) - flown_in_order + sum(1 for error in errors if error is None)
    return flown_in_order, not_flown, errors


def catalogue_p(task, track, declared, vmax=None, percentage_penalties=()):
    """The catalogue's P of one pilot in a task whose other pilot, if `vmax` is None, flew all declared points."""
    flown, not_flown, errors = flown_points(task, track, declared)
    v = oracle.contract_v(flown, not_flown)
    vmax = len([name for name in declared if name not in ("MP", "FP")]) if vmax is None else vmax
    q = oracle.q_contract_navigation(v, max(vmax, v), errors)
    return CimaScenarioCase.final_against_reference(
        q, oracle.q_contract_navigation(max(vmax, v), max(vmax, v), [0, 0, 0]), percentage_penalties
    )


class ContractNavigationFlightsTest(CimaScenarioCase):
    declared = FULL_DECLARATION["declared_sequence"]

    def fly(self, *deviations, backtracking=False, **options):
        track = self.task.generate_track(list(deviations), **options)
        result = self.task.run(track)
        expected = catalogue_p(
            self.task, track, self.declared, percentage_penalties=BACKTRACKING if backtracking else ()
        )
        return result, expected

    def setUp(self):
        self.task = build()

    def test_the_declaration_gives_mp_at_t_and_fp_at_two_t(self):
        times = self.task.gate_times
        self.assertEqual(times["MP"] - times["SP"], datetime.timedelta(seconds=T_SECONDS))
        self.assertEqual(times["FP"] - times["SP"], datetime.timedelta(seconds=2 * T_SECONDS))
        self.assertEqual([w.name for w in self.task.effective_waypoints], ["SP", "A", "B", "MP", "C", "D", "FP"])

    def test_perfect_flight_scores_the_task_value(self):
        result, expected = self.fly()
        self.assertEqual(expected, 1000)
        self.assert_final_score(result, expected, "perfect flight")

    @pytest.mark.xfail(
        strict=True,
        reason="S9: the application divides the error by a worst case of 1260 and does "
        "not round; the catalogue by the best pilot's Q (1540)",
    )
    def test_small_timing_error_at_mp(self):
        result, expected = self.fly(TimeOffset("MP", 8))
        self.assertEqual(expected, oracle.round_half_up(1000 * (1540 - 8) / 1540))
        self.assert_final_score(result, expected, "MP 8 s late")

    @pytest.mark.xfail(
        strict=True,
        reason="S9: Qmax is the best pilot's Q (1540) and the score is rounded; the application's worst case is 1260",
    )
    def test_large_timing_error_at_sp(self):
        result, expected = self.fly(TimeOffset("SP", 30))
        self.assert_final_score(result, expected, "SP 30 s late")

    @pytest.mark.xfail(
        strict=True, reason="S9: Qmax is the best pilot's Q (1540); the application divides by a worst case of 1260"
    )
    def test_timing_error_beyond_emax_counts_emax(self):
        result, expected = self.fly(TimeOffset("FP", 200), lead_out_s=260)
        self.assertEqual(expected, oracle.round_half_up(1000 * (1540 - 180) / 1540))
        self.assert_final_score(result, expected, "FP 200 s late")

    @pytest.mark.xfail(
        strict=True,
        reason="F5 / S14: a declared point not flown costs its missed-gate penalty (180 of "
        "1260) in the application; the catalogue takes it off V (Qp = 1000 x V / Vmax)",
    )
    def test_a_declared_point_that_is_not_flown(self):
        result, expected = self.fly(SkipGate("C"))
        self.assertEqual(expected, oracle.round_half_up(1000 * (500 + 540) / 1540))
        self.assert_final_score(result, expected, "C declared and not flown")

    @pytest.mark.xfail(
        strict=True,
        reason="F4 / S14: a point declared after MP and flown before the time of MP is "
        "invalid but costs nothing in the application (score 0, 'invalid post-MP "
        "point'); the catalogue counts it in Ep",
    )
    def test_a_point_declared_after_mp_and_flown_before_the_time_of_mp(self):
        result, expected = self.fly(TimeOffset("MP", -40), TimeOffset("C", -100))
        flown, not_flown, errors = flown_points(
            self.task, self.task.generate_track([TimeOffset("MP", -40), TimeOffset("C", -100)]), self.declared
        )
        self.assertEqual((flown, not_flown), (3, 1))
        self.assertEqual(errors[1], -40)
        invalid = [m for m in result.messages if "invalid post-MP" in m.message]
        self.assertEqual(len(invalid), 1)
        self.assertLess(result.score, self.task.run(self.task.generate_track([TimeOffset("MP", -40)])).score)
        self.assert_final_score(result, expected, "C flown 23 s before the time of MP")

    def test_the_time_of_mp_for_the_post_mp_check_follows_the_declaration_and_an_adaptive_start(self):
        """F6 asks whether the check reads the time of MP from the wrong source. It does not seem to: with the declared T
        the time of MP is T after SP, and with an adaptive start (times counted from the real crossing of SP) the
        point flown before it is recognised as invalid just the same."""
        task = build_task(
            contract_route_geojson(catalogue=CATALOGUE),
            task_subtype=CONTRACT_NAVIGATION_TIME_CONTROLS,
            scorecard_shortcut="CIMA Precision",
            adaptive_start=True,
        ).declare(FULL_DECLARATION)
        placeholder = task.gate_times  # offsets from the start, at midnight, until SP is crossed
        sp_crossing = task.contestant.takeoff_time + datetime.timedelta(minutes=6)
        times = {name: sp_crossing + (time - placeholder["SP"]) for name, time in placeholder.items()}
        self.assertEqual(times["MP"] - times["SP"], datetime.timedelta(seconds=T_SECONDS))
        track = generate_track(
            task.effective_waypoints,
            times,
            deviations=[TimeOffset("MP", -40), TimeOffset("C", -100)],
            projector=task.projector,
        )
        result = task.run(track)
        invalid = [m for m in result.messages if "invalid post-MP" in m.message]
        self.assertEqual([m.gate.name for m in invalid], ["C"])

    @pytest.mark.xfail(
        strict=True,
        reason="F15 / S19: backtracking costs a flat 200 points; the catalogue takes 50% of the final score",
    )
    def test_backtracking_costs_half_the_score(self):
        result, expected = self.fly(Reverse("A", seconds=10, fraction=0.5), backtracking=True)
        self.assertEqual(expected, 500)
        self.assert_final_score(result, expected, "10 s backwards")

    @pytest.mark.xfail(
        strict=True,
        reason="F5 / S14 and S9: the score does not reward declaring more points (both "
        "pilots score 1000 for a perfect flight) and Qmax is not the best pilot's Q",
    )
    def test_a_pilot_who_declares_and_flies_many_points_outscores_one_who_declares_none(self):
        many = self.task
        none = add_contestant(self.task).declare(NO_POINTS_DECLARATION)
        many_track, none_track = many.generate_track([]), none.generate_track([])
        scores = (many.run(many_track).score, none.run(none_track).score)
        v_many = oracle.contract_v(*flown_points(many, many_track, self.declared)[:2])
        v_none = oracle.contract_v(*flown_points(none, none_track, ["MP", "FP"])[:2])
        self.assertEqual((v_many, v_none), (4, 0))
        qs = [oracle.q_contract_navigation(v, 4, [0, 0, 0]) for v in (v_many, v_none)]
        expected = oracle.final_scores(qs)
        self.assertEqual(expected, [1000, 351])
        self.assertGreater(scores[0], scores[1], "the pilot with four points must outscore the one with none")
        self.assertEqual(scores, tuple(expected))

    @pytest.mark.xfail(
        strict=True,
        reason="S9 and F5 / S14: Qmax is the best Q of the task (Vmax the best V); the "
        "application scores each pilot against its worst case",
    )
    def test_two_pilots_in_the_same_task_are_scored_against_the_best(self):
        second = add_contestant(self.task).declare(FULL_DECLARATION)
        track_a = self.task.generate_track([SkipGate("D")])
        track_b = second.generate_track([SkipGate("C"), SkipGate("D"), TimeOffset("MP", 20)])
        a, b = self.task.run(track_a), second.run(track_b)
        v_a = oracle.contract_v(*flown_points(self.task, track_a, self.declared)[:2])
        v_b = oracle.contract_v(*flown_points(second, track_b, self.declared)[:2])
        vmax = max(v_a, v_b)
        qs = [
            oracle.q_contract_navigation(v_a, vmax, flown_points(self.task, track_a, self.declared)[2]),
            oracle.q_contract_navigation(v_b, vmax, flown_points(second, track_b, self.declared)[2]),
        ]
        expected = oracle.final_scores(qs)
        self.assertEqual(expected[0], 1000)
        self.assertEqual((a.score, b.score), tuple(expected))
