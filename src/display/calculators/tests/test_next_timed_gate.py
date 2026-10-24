"""
The next timed gate the gate calculator stores for the app's training countdown: only gates the pilot is shown and that
have a time check, and with an adaptive start only once the starting point is crossed.
"""

import datetime
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock

from display.calculators.gate_calculator import GateCalculator

T0 = datetime.datetime(2026, 10, 24, 12, 0, tzinfo=datetime.timezone.utc)


def gate(name, minutes, time_check=True, visible=True, passed=False):
    return SimpleNamespace(
        name=name,
        expected_time=T0 + datetime.timedelta(minutes=minutes),
        time_check=time_check,
        is_visible=visible,
        has_been_passed=lambda: passed,
    )


def calculator(gates, adaptive_start=False, starting_line_crossed=False, live_processing=True):
    calc = GateCalculator.__new__(GateCalculator)
    calc.contestant = MagicMock(adaptive_start=adaptive_start)
    calc.outstanding_gates = list(gates)
    calc.starting_line = SimpleNamespace(has_infinite_been_passed=lambda: starting_line_crossed)
    calc.live_processing = live_processing
    calc._published_next_timed_gate = None
    return calc


class TestNextTimedGate(TestCase):
    def test_skips_secret_gates_and_gates_without_a_time_check(self):
        calc = calculator([gate("SC1", 2, visible=False), gate("TP1", 3, time_check=False), gate("TP2", 5)])
        self.assertEqual(calc._next_timed_gate().name, "TP2")

    def test_skips_a_gate_already_missed(self):
        calc = calculator([gate("TP1", 3, passed=True), gate("TP2", 5)])
        self.assertEqual(calc._next_timed_gate().name, "TP2")

    def test_none_after_the_last_timed_gate(self):
        self.assertIsNone(calculator([gate("SC9", 30, visible=False)])._next_timed_gate())

    def test_adaptive_start_waits_for_the_starting_point_and_never_counts_down_to_it(self):
        gates = [gate("SP", 0), gate("TP1", 3)]
        self.assertIsNone(calculator(gates, adaptive_start=True)._next_timed_gate())
        crossed = calculator(gates, adaptive_start=True, starting_line_crossed=True)
        crossed.starting_line = gates[0]
        gates[0].has_infinite_been_passed = lambda: True
        self.assertEqual(crossed._next_timed_gate().name, "TP1")

    def test_a_fixed_start_counts_down_to_the_starting_point(self):
        gates = [gate("SP", 0), gate("TP1", 3)]
        calc = calculator(gates)
        calc.starting_line = gates[0]
        self.assertEqual(calc._next_timed_gate().name, "SP")

    def test_publishes_again_when_the_adaptive_start_moves_the_gate_times(self):
        tp1 = gate("TP1", 3)
        calc = calculator([tp1], adaptive_start=True, starting_line_crossed=True)
        track = calc.contestant.contestanttrack
        calc.publish_next_timed_gate()
        tp1.expected_time = T0 + datetime.timedelta(hours=8, minutes=9)  # the crossing set the start minute
        calc.publish_next_timed_gate()
        track.update_next_timed_gate.assert_called_with("TP1", T0 + datetime.timedelta(hours=8, minutes=9))
        self.assertEqual(track.update_next_timed_gate.call_count, 2)

    def test_publishes_only_when_the_gate_or_its_time_changes(self):
        calc = calculator([gate("SP", 0), gate("TP1", 3)])
        track = calc.contestant.contestanttrack
        calc.publish_next_timed_gate()
        calc.publish_next_timed_gate()
        track.update_next_timed_gate.assert_called_once_with("SP", T0)
        calc.outstanding_gates.pop(0)
        calc.publish_next_timed_gate()
        track.update_next_timed_gate.assert_called_with("TP1", T0 + datetime.timedelta(minutes=3))
        calc.outstanding_gates.pop(0)
        calc.publish_next_timed_gate()
        track.update_next_timed_gate.assert_called_with("", None)
        self.assertEqual(track.update_next_timed_gate.call_count, 3)

    def test_nothing_is_published_when_recalculating_a_track(self):
        calc = calculator([gate("SP", 0)], live_processing=False)
        calc.publish_next_timed_gate()
        calc.contestant.contestanttrack.update_next_timed_gate.assert_not_called()
