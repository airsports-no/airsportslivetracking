"""Scenario tests: hidden gates on a curved leg (2.A1 Curve navigation, where a curved leg is required).

The first leg of the route is a curve with two hidden gates on it, as the route editor builds it when a hidden gate is
placed on a curved leg: the curve is split in two curved segments at each gate, and together they are the old curve (see
curve_with_hidden_gates_route_geojson). The flights follow the curve (through the generated curve points) and are scored
by the real calculators; the expected score is the catalogue's, as in test_simulated_cima_curve_precision_flights.py. The
scenarios that cannot be flown on a curved first leg there (Reverse, and a time offset of a gate, which need the
untimed curve points around it to move too) are not used here.
"""

from display.calculators.tests import catalogue_oracle as oracle
from display.calculators.tests.cima_scenario_support import (
    CimaScenarioCase,
    allow_brief_backtracking,
    correct_gate_count,
    first_crossing_errors,
)
from display.calculators.tests.flight_simulator import (
    LateralOffset,
    MissGate,
    build_task,
    curve_with_hidden_gates_route_geojson,
)
from display.utilities.task_types import CURVE_NAVIGATION_TIME_ESTIMATION

CURVE_GATES = ["HG1", "HG2"]


class HiddenGatesOnACurvedLegFlightsTest(CimaScenarioCase):
    TIME_GATES = ["TP1", "TP2"]
    PERFECT_Q = oracle.q_curve_navigation(len(CURVE_GATES), len(CURVE_GATES), [0, 0])

    def build(self):
        self.task = build_task(
            curve_with_hidden_gates_route_geojson((0.3, 0.7)),
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

    def fly(self, *deviations, **options):
        self.fly_reference_pilot()
        track = self.task.generate_track(list(deviations), **options)
        result = self.task.run(track)
        crossings = self.task.crossings(track, [*self.TIME_GATES, *CURVE_GATES])
        q = oracle.q_curve_navigation(
            len(CURVE_GATES),
            correct_gate_count(crossings, CURVE_GATES),
            first_crossing_errors(crossings, self.TIME_GATES),
        )
        return result, crossings, self.final_against_reference(q, self.PERFECT_Q)

    def test_the_route_has_the_gates_on_the_curve_between_generated_curve_points(self):
        self.build()
        names = [waypoint.name for waypoint in self.task.effective_waypoints]
        self.assertEqual(len(names), len(set(names)))
        for gate in CURVE_GATES:
            index = names.index(gate)
            self.assertTrue(names[index - 1].startswith("Curve "), names[index - 1])
            self.assertTrue(names[index + 1].startswith("Curve "), names[index + 1])

    def test_flying_along_the_curve_crosses_the_gates_on_time(self):
        self.build()
        result, crossings, expected = self.fly()
        for gate in CURVE_GATES:
            self.assertEqual(len(crossings[gate]), 1, f"{gate} is not crossed once")
            self.assertLess(abs(crossings[gate][0].error_s), 1.0, f"{gate} is not crossed on time")
        self.assertEqual(expected, 1000)
        self.assert_final_score(result, expected, "perfect flight along the curve")

    def test_a_flight_that_misses_a_gate_on_the_curve_loses_it(self):
        self.build()
        for gate, other in (("HG1", "HG2"), ("HG2", "HG1")):
            with self.subTest(gate=gate):
                self.build()
                result, crossings, expected = self.fly(MissGate(gate, margin_m=100))
                self.assertEqual(correct_gate_count(crossings, CURVE_GATES), 1)
                self.assertTrue(crossings[other], f"{other} should still be crossed")
                self.assertEqual(expected, oracle.round_half_up(1000 * (500 + 360) / 1360))
                self.assert_final_score(result, expected, f"{gate} missed on the curve")

    def test_a_flight_that_cuts_the_curve_on_the_inside_misses_the_gate(self):
        self.build()
        # The curve bows to the right of the leg: the inside of the bend is to the left of the flight
        result, crossings, expected = self.fly(LateralOffset("HG1", -300))
        self.assertFalse(crossings.get("HG1"), "HG1 was crossed")
        self.assertEqual(expected, oracle.round_half_up(1000 * (500 + 360) / 1360))
        self.assert_final_score(result, expected, "HG1 passed 300 m inside the curve")
