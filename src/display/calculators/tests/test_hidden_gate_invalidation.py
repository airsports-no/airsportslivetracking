"""Calculator-level tests of the invalidation of hidden gates (finding F1, slice S11) by the GateCalculator.

FAI Section 10 Annex 4 (2.A1, 2.A2, 2.A4, 2.A5): "Gates must be crossed in order and proper direction. Crossing the same
gate more than once in any direction invalidates the gate." The calculator is fed positions on a straight line of gates
(SP, three hidden gates, FP, in metres east of SP) and the events it returns are handled the way the orchestrator
does, so every test sees the score messages the calculator sends. No database.
"""

import datetime
import math
from queue import Empty, Queue
from unittest.mock import MagicMock, patch

from django.test import TestCase

from display.calculators.calculator import (
    GateMissedEvent,
    GatePassedEvent,
    NextGateExpectedEvent,
    OrchestratorState,
)
from display.calculators.gate_calculator import HIDDEN_GATE_INVALIDATED_SCORE_TYPE, GateCalculator
from display.calculators.positions_and_gates import Gate
from display.calculators.tests.synthetic_helpers import make_position, make_waypoint
from display.utilities.coordinate_utilities import Projector

UTC = datetime.timezone.utc
GATE_HALF_LENGTH = 150.0
MISSED_SCORE = 180.0
SPEED = 40.0  # metres per one second sample
START = datetime.datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
GATE_X = {"SP": 0.0, "HG1": 1000.0, "HG2": 2000.0, "HG3": 3000.0, "FP": 4000.0}


def sample(polyline, speed=SPEED):
    """The polyline (x, y metres) as positions one second apart at `speed` metres per second."""
    points = [polyline[0]]
    carried = 0.0
    for (x0, y0), (x1, y1) in zip(polyline, polyline[1:]):
        length = math.hypot(x1 - x0, y1 - y0)
        distance = speed - carried
        while distance <= length:
            fraction = distance / length
            points.append((x0 + fraction * (x1 - x0), y0 + fraction * (y1 - y0)))
            distance += speed
        carried = length - (distance - speed)
    return points


class HiddenGateInvalidationTest(TestCase):
    task_subtype = "curve_navigation_time_estimation"
    timed_hidden_gates = False

    def setUp(self):
        self.projector = Projector(60, 11)
        self.contestant = MagicMock()
        self.contestant.navigation_task.task_subtype = self.task_subtype
        self.contestant.gate_times = {}
        self.contestant.adaptive_start = False
        self.contestant.contestanttaskconfiguration.is_valid = False  # no declaration: no declared-route rules
        self._collected = []
        self.scorecard = MagicMock()
        self.scorecard.get_gate_timing_score_for_gate_type.side_effect = self.timing_score
        self.queue = Queue()
        self.gates = [self.make_gate(name, x) for name, x in GATE_X.items()]
        with patch.object(GateCalculator, "create_gates", return_value=self.gates):
            self.calculator = GateCalculator(
                self.contestant,
                self.scorecard,
                MagicMock(),
                self.queue,
                live_processing=False,
                projector=self.projector,
            )
        self.calculator.gates = self.gates
        self.calculator.starting_line = self.gates[0]
        self.calculator.starting_line.pass_infinite_gate(START, MagicMock())
        self.calculator.outstanding_gates = list(self.gates[1:])
        self.track = []
        self.state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )
        self.events = []

    @staticmethod
    def timing_score(gate_type, planned, actual):
        """180 for a gate not crossed, otherwise one point per second of error."""
        return MISSED_SCORE if actual is None else min(abs((actual - planned).total_seconds()), MISSED_SCORE)

    def to_lat_lon(self, x, y):
        longitude, latitude = self.projector.from_projection.transform(x, y)
        return latitude, longitude

    def make_gate(self, name, x):
        hidden = name.startswith("HG")
        gate_line = (self.to_lat_lon(x, -GATE_HALF_LENGTH), self.to_lat_lon(x, GATE_HALF_LENGTH))
        waypoint = make_waypoint(
            name=name,
            type="secret" if hidden else ("sp" if name == "SP" else "fp"),
            latitude=self.to_lat_lon(x, 0)[0],
            longitude=self.to_lat_lon(x, 0)[1],
            gate_line=gate_line,
            gate_line_infinite=gate_line,
            gate_line_extended=gate_line,
            gate_heading=90.0,
            time_check=(not hidden) or self.timed_hidden_gates,
            is_visible=not hidden,
        )
        # the flights start 200 m before SP at 40 m/s: a gate at x is flown at (x + 200) / 40 seconds
        gate = Gate(waypoint, START + datetime.timedelta(seconds=(x + 200) / SPEED), gate_line)
        gate.pre_project(self.projector)
        return gate

    def fly(self, polyline, speed=SPEED, continue_track=False):
        """Feed the calculator positions along the polyline and handle its events as the orchestrator does."""
        start_second = len(self.track)
        points = sample(polyline, speed)
        for index, (x, y) in enumerate(points[1:] if continue_track else points):
            latitude, longitude = self.to_lat_lon(x, y)
            self.track.append(
                make_position(
                    self.projector, latitude, longitude, START + datetime.timedelta(seconds=start_second + index)
                )
            )
            for event in self.calculator.check_intersections(self.track, self.state):
                self.events.append(event)
                if isinstance(event, GatePassedEvent):
                    self.calculator.on_gate_passed(event)
                elif isinstance(event, GateMissedEvent):
                    self.calculator.on_gate_missed(event)
                elif isinstance(event, NextGateExpectedEvent):
                    self.state.next_gate = event.gate

    def messages(self, gate=None, score_type=None):
        collected = []
        while True:
            try:
                collected.append(self.queue.get_nowait())
            except Empty:
                break
        self._collected = getattr(self, "_collected", []) + collected
        return [
            m
            for m in self._collected
            if (gate is None or m.gate.name == gate) and (score_type is None or m.score_type == score_type)
        ]

    def invalidations(self, gate=None):
        return self.messages(gate, HIDDEN_GATE_INVALIDATED_SCORE_TYPE)

    # -- a hidden gate crossed again ---------------------------------------------------------------------------------

    def test_a_gate_crossed_once_is_not_invalidated(self):
        self.fly([(-200, 0), (4500, 0)])
        self.assertEqual(self.invalidations(), [])
        self.assertEqual([m.score for m in self.messages() if m.score], [])

    def test_the_same_crossing_seen_on_two_consecutive_positions_is_one_crossing(self):
        # Crossings are found from the last three positions, so one crossing is seen twice; a gate is watched from the
        # moment it is passed and must not be invalidated by seeing its own crossing again.
        self.fly([(-200, 0), (1100, 0)], speed=7.0)
        self.assertEqual(self.invalidations(), [])

    def test_a_gate_crossed_again_in_the_same_direction_is_invalidated_once(self):
        # HG2 forwards, round the end of its line and back across it forwards
        self.fly([(-200, 0), (2100, 0), (2100, 300), (1900, 300), (1900, 0), (2200, 0), (4500, 0)])
        invalidations = self.invalidations()
        self.assertEqual([(m.gate.name, m.score) for m in invalidations], [("HG2", MISSED_SCORE)])
        self.assertEqual(invalidations[0].kind, "penalty")
        self.assertEqual(invalidations[0].message, "gate invalidated by repeated crossing")

    def test_a_gate_crossed_back_across_is_invalidated(self):
        self.fly([(-200, 0), (2100, 0), (1900, 0), (4500, 0)])
        self.assertEqual([m.gate.name for m in self.invalidations()], ["HG2"])

    def test_the_gate_is_invalidated_once_however_often_it_is_crossed(self):
        self.fly([(-200, 0), (2100, 0), (1900, 0), (2100, 0), (1900, 0), (2100, 0), (4500, 0)])
        self.assertEqual([m.gate.name for m in self.invalidations()], ["HG2"])

    def test_every_gate_crossed_twice_is_invalidated_once(self):
        self.fly([(-200, 0), (3100, 0), (900, 0), (4500, 0)])
        self.assertEqual(sorted(m.gate.name for m in self.invalidations()), ["HG1", "HG2", "HG3"])

    def test_the_invalidation_is_logged_at_the_time_of_the_second_crossing(self):
        self.fly([(-200, 0), (2100, 0), (2100, 300), (1900, 300), (1900, 0), (2200, 0), (4500, 0)])
        (message,) = self.invalidations()
        gate = self.gates[2]
        self.assertGreater(message.time, gate.passing_time + datetime.timedelta(seconds=5))
        self.assertEqual(message.planned, gate.expected_time)
        self.assertEqual(message.actual, gate.passing_time)  # the first crossing is where the timing comes from

    def test_the_first_crossing_stays_the_time_of_the_gate(self):
        self.fly([(-200, 0), (2100, 0), (1900, 0), (4500, 0)])
        first_crossing = START + datetime.timedelta(seconds=(2000 + 200) / SPEED)
        self.assertLessEqual(abs((self.gates[2].passing_time - first_crossing).total_seconds()), 1)

    def test_a_gate_crossed_after_the_finish_point_is_not_invalidated(self):
        self.fly([(-200, 0), (2100, 0)])
        self.state.has_passed_finishpoint = True
        self.fly([(2100, 0), (1900, 0), (2100, 0)], continue_track=True)
        self.assertEqual(self.invalidations(), [])

    def test_the_gates_are_not_watched_once_the_flight_is_finished(self):
        self.fly([(-200, 0), (2100, 0)])
        self.assertTrue(self.calculator._watched_hidden_gates)
        self.calculator.finalise(self.track)
        self.assertEqual(self.calculator._watched_hidden_gates, [])

    def test_only_the_passed_hidden_gates_are_watched(self):
        self.fly([(-200, 0), (2500, 0)])
        self.assertEqual([g.name for g in self.calculator._watched_hidden_gates], ["HG1", "HG2"])

    def test_the_gate_costs_what_a_gate_not_correctly_crossed_costs(self):
        self.fly([(-200, 0), (2100, 0), (1900, 0), (4500, 0)])
        (message,) = self.invalidations()
        self.assertEqual(message.score, self.scorecard.get_gate_timing_score_for_gate_type("secret", START, None))

    # -- a hidden gate first crossed against the route ---------------------------------------------------------------

    def test_a_gate_first_crossed_against_the_route_is_invalidated_as_it_is_crossed(self):
        # Round the end of HG2's line to the far side, back across it against the route, round the end again
        self.fly([(-200, 0), (1500, 0), (1500, 300), (2300, 300), (2300, 0), (1900, 0), (1900, 300), (4500, 300)])
        self.assertEqual([(m.gate.name, m.score) for m in self.invalidations()], [("HG2", MISSED_SCORE)])
        (message,) = self.invalidations()
        self.assertEqual(message.message, "hidden gate crossed against the route")
        self.assertTrue(self.gates[2].missed)
        self.assertIsNone(self.gates[2].passing_time)
        self.assertNotIn(self.gates[2], self.calculator.outstanding_gates)

    def test_a_gate_crossed_against_the_route_is_neither_scored_as_missed_nor_again(self):
        self.fly([(-200, 0), (1500, 0), (1500, 300), (2300, 300), (2300, 0), (1900, 0), (1900, 300), (4500, 300)])
        self.calculator.finalise(self.track)
        self.assertEqual([m.score_type for m in self.messages(gate="HG2")], [HIDDEN_GATE_INVALIDATED_SCORE_TYPE])

    def test_a_gate_crossed_against_the_route_and_then_correctly_does_not_count(self):
        self.fly([(-200, 0), (1500, 0), (1500, 300), (2300, 300), (2300, 0), (1900, 0), (2300, 0), (4500, 0)])
        self.assertEqual(self.invalidations("HG2")[0].message, "hidden gate crossed against the route")
        self.assertEqual(len(self.invalidations("HG2")), 1)
        self.assertIsNone(self.gates[2].passing_time)

    def test_the_next_gate_moves_on_when_the_next_gate_is_crossed_against_the_route(self):
        self.fly([(-200, 0), (1500, 0), (1500, 300), (2300, 300), (2300, 0), (1900, 0)])
        self.assertIs(self.state.next_gate, self.gates[3])

    # -- what is not invalidated -------------------------------------------------------------------------------------

    def test_a_task_type_without_the_rule_does_not_invalidate(self):
        for subtype in ("legacy_precision", "contract_navigation_time_controls", None):
            with self.subTest(subtype=subtype):
                self.setUp()
                self.contestant.navigation_task.task_subtype = subtype
                self.fly([(-200, 0), (2100, 0), (1900, 0), (2100, 0), (4500, 0)])
                self.assertEqual(self.invalidations(), [])
                self.assertEqual(self.calculator._watched_hidden_gates, [])

    def test_the_rule_applies_to_2_a1_2_a2_2_a4_and_2_a5(self):
        for subtype in ("curve_navigation_time_estimation", "precision_navigation", "known_circuit", "unknown_legs"):
            with self.subTest(subtype=subtype):
                self.setUp()
                self.contestant.navigation_task.task_subtype = subtype
                self.fly([(-200, 0), (2100, 0), (1900, 0), (4500, 0)])
                self.assertEqual([m.gate.name for m in self.invalidations()], ["HG2"])

    def test_a_turn_point_crossed_twice_is_not_invalidated(self):
        self.fly([(-200, 0), (4100, 0), (3900, 0), (4100, 0)])
        self.assertEqual(self.invalidations("FP"), [])


class TimedHiddenGateInvalidationTest(HiddenGateInvalidationTest):
    """2.A2: the hidden gates are time gates, and the timing of the first crossing stays what it was."""

    task_subtype = "precision_navigation"
    timed_hidden_gates = True

    def test_the_invalidation_costs_the_gate_less_what_its_timing_already_cost(self):
        # HG2 is crossed 10 s late (at 40 m/s: its time is 50 s after SP, flown at 60 s): 10 points for the timing, and
        # the gate is worth 180 in all
        self.fly([(-200, 0), (600, 0)], speed=SPEED)
        self.fly([(600, 0), (2400, 0)], speed=2000 / 60.0, continue_track=True)
        self.fly([(2400, 0), (1900, 0), (4500, 0)], speed=SPEED, continue_track=True)
        timing = [m for m in self.messages(gate="HG2") if m.score_type == "gate_score"]
        (invalidation,) = self.invalidations("HG2")
        self.assertGreater(timing[0].score, 0)
        self.assertEqual(timing[0].score + invalidation.score, MISSED_SCORE)
