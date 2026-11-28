"""2.A8 (Precision navigation Air Nav Race) against the catalogue, and the FAI ANR task type next to it unchanged (S20).

The catalogue: Q = 2000 - penalties and P = 1000 x Q / 2000 (absolute, not scaled by the best pilot); the time gates at
SP and FP are 0.6 NM wide, one second either way is free and then 3 points per full second with at most 200, and a gate
not crossed costs 200; taking off outside the given time costs 100; backtracking or circling costs 200 each.

2.A8 differs from FAI ANR 2022 (the legacy ANR task type, which shares the calculators) by registry flags and scorecard
values only; the second half of this file shows that the legacy task type still has its own behaviour for each.
"""

import datetime

from django.test import TestCase

from display.calculators.tests import catalogue_oracle as oracle
from display.calculators.tests.cima_scenario_support import CimaScenarioCase, first_crossing_errors
from display.calculators.tests.flight_simulator import (
    LateralOffset,
    MissGate,
    Orbit,
    Reverse,
    TimeOffset,
    add_contestant,
    build_task,
)
from display.calculators.tests.test_simulated_legacy_flights import GENTLE_LEGS, route_geojson
from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Scorecard
from display.utilities.task_types import (
    ANR_CATALOGUE,
    ANR_CORRIDOR,
    LEGACY_ANR_CORRIDOR,
    TASK_TYPE_REGISTRY,
)

TIME_GATE_HALF_WIDTH_M = 0.6 * 1852 / 2


def build_anr(subtype, shortcut, **options):
    return build_task(
        route_geojson(GENTLE_LEGS),
        task_type=ANR_CORRIDOR,
        task_subtype=subtype,
        scorecard_shortcut=shortcut,
        rounded_corners=False,
        corridor_width=1.0,
        whole_second_gate_times=True,
        **options,
    )


class CatalogueRegistryAndScorecardTest(TestCase):
    def setUp(self):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="CIMA ANR")

    def test_the_registry_has_the_catalogue_flags_only_for_2a8(self):
        for key, definition in TASK_TYPE_REGISTRY.items():
            expected = key == ANR_CATALOGUE
            self.assertEqual(expected, definition.start_point_must_be_crossed_in_gate, key)
            self.assertEqual(0.6 if expected else None, definition.start_finish_gate_width_nm, key)

    def test_sp_and_fp_have_one_second_of_grace_and_nothing_else_changed_for_them(self):
        fai = Scorecard.get_originals().get(shortcut_name="FAI ANR")
        for gate_type in ("sp", "fp"):
            gate, fai_gate = self.scorecard.get_gate_scorecard(gate_type), fai.get_gate_scorecard(gate_type)
            self.assertEqual((1, 1), (gate.graceperiod_before, gate.graceperiod_after))
            self.assertEqual((3, 200, 200), (gate.penalty_per_second, gate.maximum_penalty, gate.missed_penalty))
            self.assertEqual((2, 2), (fai_gate.graceperiod_before, fai_gate.graceperiod_after))

    def test_takeoff_outside_the_given_time_costs_a_hundred_points(self):
        gate = self.scorecard.get_gate_scorecard("to")
        planned = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)

        def penalty(seconds):
            return self.scorecard.get_gate_timing_score_for_gate_type(
                "to", planned, planned + datetime.timedelta(seconds=seconds)
            )

        self.assertEqual((0, 0, 0), (penalty(0), penalty(30), penalty(59)))
        self.assertEqual((100, 100, 100), (penalty(-1), penalty(70), penalty(600)))
        self.assertEqual(100, gate.missed_penalty)

    def test_backtracking_and_circling_have_no_maximum(self):
        fai = Scorecard.get_originals().get(shortcut_name="FAI ANR")
        self.assertEqual(200, self.scorecard.backtracking_penalty)
        self.assertEqual(-1, self.scorecard.backtracking_maximum_penalty)
        self.assertEqual(400, fai.backtracking_maximum_penalty)


class CatalogueFlightsTest(CimaScenarioCase):
    task_type = ANR_CORRIDOR

    def build(self):
        self.task = build_anr(ANR_CATALOGUE, "CIMA ANR")
        return self.task

    def fly(self, *deviations, **catalogue_inputs):
        track = self.task.generate_track(list(deviations))
        result = self.task.run(track)
        crossings = self.task.crossings(track, ["SP", "FP"])
        sp_error, fp_error = first_crossing_errors(crossings, ["SP", "FP"])
        inputs = {"sp_error": sp_error, "fp_error": fp_error, **catalogue_inputs}
        return result, oracle.anr_final_score(oracle.q_anr(**inputs))

    def test_the_time_gates_are_as_wide_as_the_catalogue_says_and_the_corridor_is_not(self):
        task = self.build()
        widths = {w.name: w.width for w in task.effective_waypoints}
        self.assertAlmostEqual(0.6, widths["SP"], places=6)
        self.assertAlmostEqual(0.6, widths["FP"], places=6)
        self.assertAlmostEqual(1.0, widths["TP1"], places=6)
        self.assertEqual(1.0, task.route.corridor_width)

    def test_start_point_missed_sideways_costs_two_hundred_with_an_explained_entry(self):
        self.build()
        result, expected = self.fly(LateralOffset("SP", TIME_GATE_HALF_WIDTH_M + 100), sp_error=None)
        self.assertEqual(900, expected)
        self.assert_final_score(result, expected, "SP crossed beside the gate")
        self.assertEqual(1800, result.raw_quality)
        (missed,) = [m for m in result.messages if m.gate.name == "SP" and m.message == "missing gate"]
        self.assertEqual(200, missed.score)

    def test_a_crossing_inside_the_time_gate_counts_also_near_its_edge(self):
        self.build()
        result, expected = self.fly(LateralOffset("SP", TIME_GATE_HALF_WIDTH_M - 60))
        self.assertEqual(1000, expected)
        self.assert_final_score(result, expected, "SP crossed near the edge of the gate")

    def test_finish_point_crossed_outside_the_time_gate_is_not_crossed(self):
        self.build()
        result, expected = self.fly(LateralOffset("FP", TIME_GATE_HALF_WIDTH_M + 100), fp_error=None)
        self.assertEqual(900, expected)
        self.assert_final_score(result, expected, "FP crossed beside the gate")

    def test_one_second_at_sp_is_free_and_two_seconds_cost_three_points(self):
        self.build()
        result, expected = self.fly(TimeOffset("SP", 1))
        self.assert_final_score(result, 1000, "SP 1 s late")
        track = self.task.generate_track([TimeOffset("SP", 2)])
        two_seconds = self.task.run(track)
        self.assertEqual(1997, two_seconds.raw_quality)
        # 1000 x 1997 / 2000 = 998.5, rounded half up
        self.assertEqual(oracle.anr_final_score(oracle.q_anr(sp_error=2, fp_error=0)), 999)
        self.assertEqual(999, two_seconds.score)

    def test_the_score_is_absolute_a_better_pilot_does_not_rescale_it(self):
        task = self.build()
        other = add_contestant(task)
        late = task.run(task.generate_track([TimeOffset("SP", 90)]))
        self.assertEqual(900, late.score)
        perfect = other.run(other.generate_track([]))
        self.assertEqual(1000, perfect.score)
        self.assertEqual(900, late.score, "the late pilot is still 1000 x 1800 / 2000, not divided by the best Q")
        self.assertEqual(2000, perfect.raw_quality)

    def test_three_backtracks_cost_two_hundred_each_without_the_legacy_maximum_of_four_hundred(self):
        self.build()
        result, expected = self.fly(
            Reverse("SP", seconds=10),
            Orbit("TP1", radius_m=300),
            Reverse("TP2", seconds=10),
            backtracking_or_circling=3,
        )
        self.assertEqual(700, expected)
        self.assert_final_score(result, expected, "three backtracks")


class LegacyAnrIsUnaffectedTest(TestCase):
    """FAI ANR 2022 on the legacy task type: the infinite starting line, the corridor-wide gates and two seconds of grace."""

    def build(self):
        self.task = build_anr(None, "FAI ANR")
        return self.task

    def test_the_registry_says_nothing_special_of_the_legacy_task_type(self):
        definition = TASK_TYPE_REGISTRY[LEGACY_ANR_CORRIDOR]
        self.assertFalse(definition.start_point_must_be_crossed_in_gate)
        self.assertIsNone(definition.start_finish_gate_width_nm)

    def test_the_waypoints_keep_the_width_of_the_corridor(self):
        task = self.build()
        widths = {w.name: w.width for w in task.effective_waypoints}
        self.assertEqual({1.0}, {widths["SP"], widths["FP"], widths["TP1"]})

    def test_the_start_point_crossed_beside_its_gate_still_counts_as_the_start(self):
        task = self.build()
        result = task.run(task.generate_track([LateralOffset("SP", TIME_GATE_HALF_WIDTH_M + 100)]))
        self.assertNotIn("SP", result.missed_gates)
        self.assertEqual([], [m for m in result.messages if m.score and m.gate.name == "SP"])

    def test_missing_the_start_point_sideways_still_costs_nothing(self):
        task = self.build()
        result = task.run(task.generate_track([MissGate("SP", margin_m=20)]))
        self.assertEqual([], [m for m in result.messages if m.score and m.gate.name == "SP"])

    def test_two_seconds_of_grace_at_sp(self):
        task = self.build()
        result = task.run(task.generate_track([TimeOffset("SP", 5)]))
        # round(5 - 2) x 3 points
        self.assertEqual(9, result.score)

    def test_the_scorecard_keeps_its_takeoff_penalty_and_backtracking_maximum(self):
        create_scorecards()
        fai = Scorecard.get_originals().get(shortcut_name="FAI ANR")
        takeoff = fai.get_gate_scorecard("to")
        self.assertEqual((200, 200, 0), (takeoff.penalty_per_second, takeoff.maximum_penalty, takeoff.missed_penalty))
        self.assertEqual(400, fai.backtracking_maximum_penalty)
