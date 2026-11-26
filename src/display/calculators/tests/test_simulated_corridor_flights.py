"""Scenario tests: synthetic flights through the real calculators for the corridor task types.

ANR corridor (FAI ANR 2022) and Air Sports Race (the 2025 Annex 9 scorecard): gate timing, missed gates, the corridor,
backtracking, prohibited and penalty zones and the take-off gate. The helpers and the precision scenarios are in
test_simulated_legacy_flights.py.
"""

from display.calculators.tests.flight_simulator import (
    MissGate,
    Orbit,
    Reverse,
    SidewaysExcursion,
    SkipGate,
    TimeOffset,
)
from display.calculators.tests.test_simulated_legacy_flights import (
    BACKTRACKING,
    CORRIDOR,
    CORRIDOR_WIDTH_NM,
    GATE_SCORE,
    HALF_CORRIDOR_M,
    PENALTY_ZONE,
    PROHIBITED,
    ScenarioCase,
    backtracking_penalty,
    corridor_penalty,
    inside_runs,
    penalties,
    seconds_beyond,
    takeoff_gate_feature,
    timing_error,
    timing_penalty,
    zone_feature,
)
from display.utilities.navigation_task_type_definitions import AIRSPORTS, ANR_CORRIDOR

# ---------------------------------------------------------------------------------------------------------------------
# Corridor task types: ANR and Air Sports Race
# ---------------------------------------------------------------------------------------------------------------------

SHORT_ZONE_METRES = 60.0  # about 1.5 s at 75 knots
LONG_ZONE_METRES = 600.0  # about 15 s at 75 knots


class CorridorScenarios:
    """Scenarios shared by the ANR and Air Sports Race scorecards: the corridor, zones and backtracking."""

    def excursion(self, distance_m: float, duration_s: float):
        """A flight that leaves the straight line TP1 -> TP2 sideways by `distance_m` for `duration_s`."""
        return SidewaysExcursion("TP1", distance_m, duration_s, ramp_s=2.0)

    def test_perfect_flight_has_no_penalties(self):
        self.build()
        track, result = self.fly()
        self.assertNoPenalties(result)

    # -- corridor -------------------------------------------------------------------------------------------------

    def test_leaving_the_corridor_for_less_than_the_grace_time_is_free(self):
        self.build()
        track, result = self.fly(self.excursion(1500, 2))
        outside = seconds_beyond(self.task, track, "TP1", "TP2", HALF_CORRIDOR_M)
        self.assertLess(outside, self.scorecard.corridor_grace_time)
        self.assertNoPenalties(result)

    def test_leaving_the_corridor_for_longer_than_the_grace_time_costs_points_per_second_after_it(self):
        self.build()
        track, result = self.fly(self.excursion(1500, 20))
        outside = seconds_beyond(self.task, track, "TP1", "TP2", HALF_CORRIDOR_M)
        expected = corridor_penalty(self.scorecard, outside)
        self.assertGreater(outside, 15)
        self.assertGreater(expected, 0)
        self.assertEqual(penalties(result), [(CORRIDOR, "TP1", float(expected))])
        self.assertEqual(result.score, expected)

    def test_a_longer_excursion_costs_proportionally_more(self):
        self.build()
        track, result = self.fly(self.excursion(1500, 40))
        outside = seconds_beyond(self.task, track, "TP1", "TP2", HALF_CORRIDOR_M)
        expected = corridor_penalty(self.scorecard, outside)
        self.assertEqual(penalties(result), [(CORRIDOR, "TP1", float(expected))])
        self.assertEqual(
            expected, (round(outside) - self.scorecard.corridor_grace_time) * self.scorecard.corridor_outside_penalty
        )

    def test_moving_sideways_inside_the_corridor_is_free(self):
        self.build()
        track, result = self.fly(self.excursion(600, 30))
        self.assertNoPenalties(result)

    # -- backtracking ---------------------------------------------------------------------------------------------

    def test_flying_backwards_longer_than_the_grace_time_is_backtracking(self):
        self.build()
        track, result = self.fly(Reverse("SP", seconds=10))
        self.assertGreater(10, self.scorecard.backtracking_grace_time_seconds)
        self.assertEqual(penalties(result), [(BACKTRACKING, "SP", float(backtracking_penalty(self.scorecard)))])
        self.assertEqual(result.score, backtracking_penalty(self.scorecard))

    def test_a_full_orbit_is_backtracking(self):
        self.build()
        track, result = self.fly(Orbit("TP1", radius_m=300))
        self.assertEqual(penalties(result), [(BACKTRACKING, "TP1", float(backtracking_penalty(self.scorecard)))])

    # -- prohibited and penalty zones -----------------------------------------------------------------------------

    def test_entering_a_prohibited_zone_for_less_than_the_grace_time_is_free(self):
        zone = zone_feature("prohibited", "PZ", (2000, 2000 + SHORT_ZONE_METRES), (-100, 100))
        self.build(features=[zone])
        track, result = self.fly()
        ((first, last, _),) = inside_runs(self.task, track, zone)
        self.assertLess((last - first).total_seconds(), self.scorecard.prohibited_zone_grace_time)
        self.assertNoPenalties(result)

    def test_entering_a_prohibited_zone_for_longer_than_the_grace_time_costs_the_fixed_penalty(self):
        zone = zone_feature("prohibited", "PZ", (1000, 1000 + LONG_ZONE_METRES), (-100, 100))
        self.build(features=[zone])
        track, result = self.fly()
        ((first, last, _),) = inside_runs(self.task, track, zone)
        self.assertGreater((last - first).total_seconds(), self.scorecard.prohibited_zone_grace_time)
        penalty = float(self.scorecard.prohibited_zone_penalty)
        self.assertEqual(penalties(result), [(PROHIBITED + "PZ", "SP", penalty)])
        self.assertEqual(result.score, penalty)

    def test_entering_a_prohibited_zone_twice_costs_the_penalty_twice(self):
        zone = zone_feature("prohibited", "PZ", (1000, 5000), (-100, 100))
        self.build(features=[zone])
        track, result = self.fly(SidewaysExcursion("SP", 400, 10, ramp_s=2.0))
        runs = inside_runs(self.task, track, zone)
        self.assertEqual(len(runs), 2)
        self.assertTrue(
            all((last - first).total_seconds() > self.scorecard.prohibited_zone_grace_time for first, last, _ in runs)
        )
        penalty = float(self.scorecard.prohibited_zone_penalty)
        self.assertEqual(penalties(result), [(PROHIBITED + "PZ", "SP", penalty)] * 2)
        self.assertEqual(result.score, 2 * penalty)

    def test_time_inside_a_penalty_zone_costs_points_per_second_after_the_grace_time(self):
        zone = zone_feature("penalty", "PEN", (4000, 5000), (-100, 100))
        self.build(features=[zone])
        track, result = self.fly()
        ((first, _, left),) = inside_runs(self.task, track, zone)
        seconds = round((left - first).total_seconds()) - self.scorecard.penalty_zone_grace_time
        expected = seconds * self.scorecard.penalty_zone_penalty_per_second
        self.assertGreater(expected, 0)
        self.assertEqual(penalties(result), [(PENALTY_ZONE.rstrip("_"), "SP", float(expected))])
        self.assertEqual(result.score, expected)

    def test_same_track_gives_identical_messages(self):
        zone = zone_feature("prohibited", "PZ", (1000, 1600), (-100, 100))
        self.build(features=[zone])
        self.assertDeterministic(self.excursion(1500, 20), Reverse("SP", seconds=10))


class AnrCorridorScenariosTest(CorridorScenarios, ScenarioCase):
    """Legacy ANR corridor, FAI ANR 2022: only the start and finish points are timed."""

    task_type = ANR_CORRIDOR
    scorecard_shortcut = "FAI ANR"
    build_options = {"rounded_corners": False, "corridor_width": CORRIDOR_WIDTH_NM}

    def test_start_late_and_finish_early_outside_the_grace_period(self):
        self.build()
        track, result = self.fly(TimeOffset("SP", 5), TimeOffset("FP", -5))
        late, early = timing_error(result, self.task, "SP"), timing_error(result, self.task, "FP")
        self.assertAlmostEqual(late, 5, delta=1.0)
        self.assertAlmostEqual(early, -5, delta=1.0)
        expected = [
            (GATE_SCORE, "SP", timing_penalty(self.scorecard, "sp", late)),
            (GATE_SCORE, "FP", timing_penalty(self.scorecard, "fp", early)),
        ]
        self.assertTrue(all(points > 0 for _, _, points in expected))
        self.assertEqual(penalties(result), expected)
        self.assertEqual(result.score, sum(points for _, _, points in expected))

    def test_start_and_finish_a_little_off_time_are_free(self):
        self.build()
        track, result = self.fly(TimeOffset("SP", 0.5), TimeOffset("FP", -0.5))
        self.assertNoPenalties(result)

    def test_start_penalty_is_capped_at_the_maximum(self):
        self.build()
        track, result = self.fly(TimeOffset("SP", 90))
        gate = self.scorecard.get_gate_scorecard("sp")
        self.assertEqual(penalties(result), [(GATE_SCORE, "SP", float(gate.maximum_penalty))])
        self.assertEqual(result.score, gate.maximum_penalty)

    def test_finish_penalty_is_capped_at_the_maximum(self):
        self.build()
        track, result = self.fly(TimeOffset("FP", 90), lead_out_s=150)
        gate = self.scorecard.get_gate_scorecard("fp")
        self.assertEqual(penalties(result), [(GATE_SCORE, "FP", float(gate.maximum_penalty))])

    def test_turn_points_are_not_timed(self):
        self.build()
        track, result = self.fly(TimeOffset("TP1", 30), TimeOffset("TP2", -30))
        self.assertNoPenalties(result)

    def test_finish_point_missed_sideways_costs_the_missed_penalty(self):
        self.build()
        track, result = self.fly(MissGate("FP", margin_m=20))
        missed = self.scorecard.get_gate_scorecard("fp").missed_penalty
        self.assertEqual(result.missed_gates, ["FP"])
        self.assertEqual(penalties(result), [(GATE_SCORE, "FP", float(missed))])
        self.assertEqual(result.score, missed)

    def test_turn_point_missed_sideways_is_counted_as_missed_but_costs_nothing(self):
        self.build()
        track, result = self.fly(MissGate("TP1", margin_m=20))
        self.assertEqual(result.missed_gates, ["TP1"])
        self.assertEqual(penalties(result), [])
        self.assertEqual(result.score, self.scorecard.initial_score)

    def test_cutting_a_gentle_corner_still_passes_the_turn_point(self):
        self.build()
        track, result = self.fly(SkipGate("TP2"))
        self.assertNoPenalties(result)


class AirSportsRace2025ScenariosTest(CorridorScenarios, ScenarioCase):
    """Air Sports Race with the 2025 Annex 9 scorecard: TP1 is a known gate, TP2 a hidden one."""

    task_type = AIRSPORTS
    scorecard_shortcut = "Air Sports Race 2025"
    hidden = ("TP2",)
    build_options = {"rounded_corners": False}

    def test_known_gate_late_and_hidden_gate_early_outside_the_grace_period(self):
        self.build()
        track, result = self.fly(TimeOffset("TP1", 5), TimeOffset("TP2", -5))
        late, early = timing_error(result, self.task, "TP1"), timing_error(result, self.task, "TP2")
        self.assertAlmostEqual(late, 5, delta=1.0)
        self.assertAlmostEqual(early, -5, delta=1.0)
        expected = [
            (GATE_SCORE, "TP1", timing_penalty(self.scorecard, "tp", late)),
            (GATE_SCORE, "TP2", timing_penalty(self.scorecard, "secret", early)),
        ]
        self.assertTrue(all(points > 0 for _, _, points in expected))
        self.assertEqual(penalties(result), expected)
        self.assertEqual(result.score, sum(points for _, _, points in expected))

    def test_flying_backwards_shorter_than_the_grace_time_is_free(self):
        self.build()
        seconds = self.scorecard.backtracking_grace_time_seconds - 2
        track, result = self.fly(Reverse("SP", seconds=seconds))
        self.assertNoPenalties(result)

    def test_hidden_gates_cost_less_per_second_than_known_gates(self):
        self.build()
        known = self.scorecard.get_gate_scorecard("tp").penalty_per_second
        hidden = self.scorecard.get_gate_scorecard("secret").penalty_per_second
        self.assertLess(hidden, known)

    def test_gates_a_little_off_time_are_free(self):
        self.build()
        track, result = self.fly(TimeOffset("TP1", 0.5), TimeOffset("TP2", -0.5), TimeOffset("FP", 0.5))
        self.assertNoPenalties(result)

    def test_known_gate_penalty_is_capped_at_the_maximum(self):
        self.build()
        track, result = self.fly(TimeOffset("TP1", 110))
        gate = self.scorecard.get_gate_scorecard("tp")
        self.assertEqual(penalties(result), [(GATE_SCORE, "TP1", float(gate.maximum_penalty))])
        self.assertEqual(result.score, gate.maximum_penalty)

    def test_hidden_gate_penalty_is_capped_at_its_lower_maximum(self):
        self.build()
        track, result = self.fly(TimeOffset("TP2", 110))
        gate = self.scorecard.get_gate_scorecard("secret")
        self.assertLess(gate.maximum_penalty, self.scorecard.get_gate_scorecard("tp").maximum_penalty)
        self.assertEqual(penalties(result), [(GATE_SCORE, "TP2", float(gate.maximum_penalty))])

    def test_known_gate_missed_sideways_costs_the_missed_penalty(self):
        self.build()
        track, result = self.fly(MissGate("TP1", margin_m=20))
        missed = self.scorecard.get_gate_scorecard("tp").missed_penalty
        self.assertEqual(result.missed_gates, ["TP1"])
        self.assertEqual(penalties(result), [(GATE_SCORE, "TP1", float(missed))])
        self.assertEqual(result.score, missed)

    def test_hidden_gate_missed_sideways_costs_its_missed_penalty(self):
        self.build()
        # On the inside of the turn at TP2 (to the left): a small margin is enough to pass beside the gate line.
        track, result = self.fly(MissGate("TP2", margin_m=20, side="left"))
        missed = self.scorecard.get_gate_scorecard("secret").missed_penalty
        self.assertEqual(result.missed_gates, ["TP2"])
        self.assertEqual(penalties(result), [(GATE_SCORE, "TP2", float(missed))])

    def test_hidden_gate_skipped_by_cutting_a_sharp_corner_costs_its_missed_penalty(self):
        self.build(legs=((90.0, 6000.0), (130.0, 5000.0), (90.0, 6000.0)))
        track, result = self.fly(SkipGate("TP2"))
        missed = self.scorecard.get_gate_scorecard("secret").missed_penalty
        self.assertEqual(result.missed_gates, ["TP2"])
        self.assertIn((GATE_SCORE, "TP2", float(missed)), penalties(result))

    # -- take-off gate --------------------------------------------------------------------------------------------

    def build_with_takeoff_gate(self):
        # Two minutes from the gate to the start point at 75 knots is 4630 m: the same speed as along the route.
        self.build(features=[takeoff_gate_feature(-4630)], minutes_to_starting_point=2)

    def test_taking_off_on_time_is_free(self):
        self.build_with_takeoff_gate()
        track, result = self.fly_from_takeoff_gate()
        self.assertNoPenalties(result)
        self.assertLessEqual(abs(timing_error(result, self.task, "Takeoff 1")), 1.0)

    def test_taking_off_a_little_early_or_within_a_minute_late_is_free(self):
        self.build_with_takeoff_gate()
        for offset in (-2, 30, 55):
            with self.subTest(offset=offset):
                track, result = self.fly_from_takeoff_gate(TimeOffset("Takeoff 1", offset))
                self.assertAlmostEqual(timing_error(result, self.task, "Takeoff 1"), offset, delta=1.0)
                self.assertNoPenalties(result)

    def test_taking_off_ten_seconds_early_costs_the_take_off_penalty(self):
        self.build_with_takeoff_gate()
        track, result = self.fly_from_takeoff_gate(TimeOffset("Takeoff 1", -10))
        error = timing_error(result, self.task, "Takeoff 1")
        self.assertAlmostEqual(error, -10, delta=1.0)
        gate = self.scorecard.get_gate_scorecard("to")
        self.assertEqual(timing_penalty(self.scorecard, "to", error), gate.maximum_penalty)
        self.assertEqual(penalties(result), [(GATE_SCORE, "Takeoff 1", float(gate.maximum_penalty))])
        self.assertEqual(result.score, gate.maximum_penalty)

    def test_taking_off_more_than_a_minute_late_costs_the_take_off_penalty(self):
        self.build_with_takeoff_gate()
        track, result = self.fly_from_takeoff_gate(TimeOffset("Takeoff 1", 90))
        error = timing_error(result, self.task, "Takeoff 1")
        self.assertAlmostEqual(error, 90, delta=1.0)
        gate = self.scorecard.get_gate_scorecard("to")
        self.assertEqual(penalties(result), [(GATE_SCORE, "Takeoff 1", float(gate.maximum_penalty))])

    def test_flight_with_take_off_gate_gives_identical_messages_when_repeated(self):
        self.build_with_takeoff_gate()
        track, first = self.fly_from_takeoff_gate(TimeOffset("Takeoff 1", -10))
        second = self.task.run(track)
        self.assertTrue(first.messages)
        self.assertEqual(first.summary(), second.summary())
        self.assertEqual(first.score, second.score)

    def test_a_backtrack_on_each_of_two_legs_costs_the_task_maximum_once(self):
        self.build()
        track, result = self.fly(Reverse("SP", seconds=10), Orbit("TP1", radius_m=300))
        maximum = self.scorecard.backtracking_maximum_penalty
        self.assertEqual([entry[:2] for entry in penalties(result)], [(BACKTRACKING, "SP"), (BACKTRACKING, "TP1")])
        self.assertEqual(result.score_by_type[BACKTRACKING], maximum)
        self.assertEqual(result.score, maximum)
