"""Scenario tests: synthetic flights through the real calculators for CIMA 2.A8 (Precision navigation Air Nav Race).

The catalogue: the competitor starts with 2000 points and loses 3 points per full second beyond 5 s out of the
corridor (each excursion), 3 points per full second beyond one second of timing error at SP and FP with at most 200
(200 for a gate not crossed), and 200 for each backtracking or circling; P = 1000 x Q / 2000, an absolute score that is
not divided by the best pilot. The time gates at SP and FP are 0.6 NM wide.

Tests marked xfail(strict=True) are known disagreements of the application, with the finding and the slice of
docs/PLAN_task_scoring_reliability.md that will fix them.
"""

import pytest

from display.calculators.tests import catalogue_oracle as oracle
from display.calculators.tests.cima_scenario_support import CimaScenarioCase, first_crossing_errors
from display.calculators.tests.flight_simulator import (
    LateralOffset,
    MissGate,
    Orbit,
    Reverse,
    SidewaysExcursion,
    TimeOffset,
    add_contestant,
    build_task,
)
from display.calculators.tests.test_simulated_legacy_flights import (
    GENTLE_LEGS,
    HALF_CORRIDOR_M,
    route_geojson,
    seconds_beyond,
)
from display.utilities.task_types import ANR_CATALOGUE
from display.utilities.task_types import ANR_CORRIDOR

CORRIDOR_WIDTH_NM = 1.0
TIME_GATE_WIDTH_NM = 0.6
TIME_GATE_HALF_WIDTH_M = TIME_GATE_WIDTH_NM * 1852 / 2


class AnrCatalogueFlightsTest(CimaScenarioCase):
    task_type = ANR_CORRIDOR

    def build(self):
        self.task = build_task(
            route_geojson(GENTLE_LEGS),
            task_type=ANR_CORRIDOR,
            task_subtype=ANR_CATALOGUE,
            scorecard_shortcut="CIMA ANR",
            rounded_corners=False,
            corridor_width=CORRIDOR_WIDTH_NM,
            whole_second_gate_times=True,
        )
        self.assertTrue(self.task.contestant.contestanttaskconfiguration.is_valid)
        return self.task

    def fly(self, *deviations, **catalogue_inputs):
        """Fly, and the catalogue's final score for what was flown. SP and FP errors are those of the track's crossings
        unless the keyword inputs of `catalogue_oracle.q_anr` say otherwise."""
        track = self.task.generate_track(list(deviations))
        result = self.task.run(track)
        crossings = self.task.crossings(track, ["SP", "FP"])
        sp_error, fp_error = first_crossing_errors(crossings, ["SP", "FP"])
        inputs = {"sp_error": sp_error, "fp_error": fp_error, **catalogue_inputs}
        return track, result, oracle.anr_final_score(oracle.q_anr(**inputs))

    def test_perfect_flight_scores_a_thousand(self):
        self.build()
        track, result, expected = self.fly()
        self.assertEqual(expected, 1000)
        self.assert_final_score(result, expected, "perfect flight")

    def test_the_task_starts_with_two_thousand_points_scaled_to_a_thousand(self):
        self.build()
        track, result, expected = self.fly()
        self.assertEqual("desc", self.task.navigation_task.scorecard.score_sorting_direction)
        self.assertEqual(2000, result.raw_quality)  # Q = 2000 - penalties
        self.assertEqual(1000, result.score)  # P = 1000 x Q / 2000

    def test_start_and_finish_within_a_second_are_free(self):
        self.build()
        track, result, expected = self.fly(TimeOffset("SP", 1), TimeOffset("FP", -1))
        self.assertEqual(expected, 1000)
        self.assert_final_score(result, expected, "SP 1 s late, FP 1 s early")

    @pytest.mark.xfail(
        strict=True,
        reason="F16 / S20: the SP/FP grace time is the 2 s of FAI ANR 2022; the catalogue "
        "gives 1 s (5 s late costs 12 points in the catalogue, 9 in the application)",
    )
    def test_start_five_seconds_late_costs_three_points_per_second_beyond_the_first(self):
        self.build()
        track, result, expected = self.fly(TimeOffset("SP", 5))
        self.assertEqual(expected, 994)  # 2000 - 12 -> 994
        self.assert_final_score(result, expected, "SP 5 s late")

    @pytest.mark.xfail(
        strict=True,
        reason="F16 / S20: the SP/FP grace time is the 2 s of FAI ANR 2022; the catalogue "
        "gives 1 s (8 s early costs 21 points in the catalogue, 18 in the application)",
    )
    def test_finish_eight_seconds_early(self):
        self.build()
        track, result, expected = self.fly(TimeOffset("FP", -8))
        self.assert_final_score(result, expected, "FP 8 s early")

    def test_timing_error_is_capped_at_two_hundred_points(self):
        self.build()
        track, result, expected = self.fly(TimeOffset("SP", 90))
        self.assertEqual(expected, 900)
        self.assert_final_score(result, expected, "SP 90 s late")

    @pytest.mark.xfail(
        strict=True,
        reason="NEW: crossing SP outside the briefed 0.6 NM time gate is a valid crossing "
        "in the application, the gate is as wide as the corridor (1.0 NM); the "
        "catalogue gives 200 points for not crossing SP",
    )
    def test_start_point_crossed_outside_the_time_gate_is_not_crossed(self):
        self.build()
        offset = TIME_GATE_HALF_WIDTH_M + 150  # inside the 1 NM corridor and gate, outside the 0.6 NM time gate
        track, result, expected = self.fly(LateralOffset("SP", offset), sp_error=None)
        self.assertEqual(expected, 900)
        self.assertLess(offset, HALF_CORRIDOR_M)
        self.assert_final_score(result, expected, "SP crossed 700 m off centre")

    @pytest.mark.xfail(
        strict=True,
        reason="NEW: the start point missed sideways costs nothing in the application "
        "(no 'missing gate' score for SP); the catalogue gives 200 points",
    )
    def test_start_point_missed_costs_two_hundred_points(self):
        self.build()
        track, result, expected = self.fly(MissGate("SP", margin_m=20), sp_error=None)
        self.assertEqual(expected, 900)
        self.assert_final_score(result, expected, "SP missed")

    def test_finish_point_missed_costs_two_hundred_points(self):
        self.build()
        track, result, expected = self.fly(MissGate("FP", margin_m=20), fp_error=None)
        self.assertEqual(expected, 900)
        self.assert_final_score(result, expected, "FP missed")

    @pytest.mark.xfail(
        strict=True,
        reason="F16 / S20: the time gates at SP and FP are 0.6 NM wide in the catalogue; "
        "the application makes them as wide as the corridor (1.0 NM)",
    )
    def test_the_time_gates_are_six_tenths_of_a_nautical_mile_wide(self):
        task = self.build()
        widths = {w.name: w.width for w in task.effective_waypoints}
        self.assertAlmostEqual(widths["SP"], TIME_GATE_WIDTH_NM, places=2)
        self.assertAlmostEqual(widths["FP"], TIME_GATE_WIDTH_NM, places=2)

    def test_leaving_the_corridor_for_less_than_five_seconds_is_free(self):
        self.build()
        track = self.task.generate_track([SidewaysExcursion("TP1", 1500, 2, ramp_s=2.0)])
        outside = seconds_beyond(self.task, track, "TP1", "TP2", HALF_CORRIDOR_M)
        self.assertLess(outside, 5)
        result = self.task.run(track)
        self.assert_final_score(result, 1000, "2 s outside the corridor")

    def test_leaving_the_corridor_costs_three_points_per_full_second_beyond_five(self):
        self.build()
        track, result, expected = self.fly(SidewaysExcursion("TP1", 1500, 20, ramp_s=2.0), corridor_excursions_s=[])
        outside = seconds_beyond(self.task, track, "TP1", "TP2", HALF_CORRIDOR_M)
        expected = oracle.anr_final_score(oracle.q_anr(corridor_excursions_s=[outside], sp_error=0, fp_error=0))
        self.assertLess(expected, 1000)
        self.assert_final_score(result, expected, f"{outside:.0f} s outside the corridor")

    def test_backtracking_costs_two_hundred_points(self):
        self.build()
        track, result, expected = self.fly(Reverse("SP", seconds=10), backtracking_or_circling=1)
        self.assertEqual(expected, 900)
        self.assert_final_score(result, expected, "10 s backwards")

    def test_circling_costs_two_hundred_points(self):
        self.build()
        track, result, expected = self.fly(Orbit("TP1", radius_m=300), backtracking_or_circling=1)
        self.assertEqual(expected, 900)
        self.assert_final_score(result, expected, "a full circle")

    def test_the_score_is_absolute_and_not_divided_by_the_best_pilot(self):
        task = self.build()
        second = add_contestant(task)
        first_track = task.generate_track([Reverse("SP", seconds=10)])
        second_track = second.generate_track([Orbit("TP1", radius_m=300)])
        first, other = task.run(first_track), second.run(second_track)
        # Both lose points to backtracking, so nobody has 2000: the best pilot still scores 900, not 1000.
        self.assertEqual(oracle.anr_final_score(oracle.q_anr(backtracking_or_circling=1)), 900)
        self.assertEqual(first.score, 900)
        self.assertEqual(other.score, 900)

    def test_two_backtracks_on_two_legs_cost_two_hundred_points_each(self):
        self.build()
        track, result, expected = self.fly(
            Reverse("SP", seconds=10), Orbit("TP1", radius_m=300), backtracking_or_circling=2
        )
        self.assertEqual(expected, 800)
        self.assert_final_score(result, expected, "backtracking on two legs")
