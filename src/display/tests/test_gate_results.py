"""
gate_results_for: each gate of the route with how it went, for the live map's flight list, gates table and replay.
"""

import datetime
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from display.services.gate_results import gate_results_for

T0 = datetime.datetime(2026, 10, 24, 12, 0, tzinfo=datetime.timezone.utc)


def at(seconds):
    return T0 + datetime.timedelta(seconds=seconds)


def waypoint(name, type_, time_check):
    return SimpleNamespace(name=name, type=type_, time_check=time_check, on_curved_segment=False)


def entry(gate, message, points=0.0, planned=None, actual=None):
    return SimpleNamespace(gate=gate, message=message, points=points, planned=planned, actual=actual)


def contestant(planned, actual, entries):
    c = MagicMock()
    c.gate_times = planned
    c.gate_times_actual = actual
    c.scorelogentry_set.order_by.return_value = entries
    return c


ROUTE = [
    waypoint("SP", "sp", True),
    waypoint("TP1", "tp", False),
    waypoint("SC1", "secret", True),
    waypoint("TP2", "tp", False),
    waypoint("Dummy", "dummy", False),
    waypoint("FP", "fp", True),
]


class TestGateResults(TestCase):
    def results(self, planned, actual, entries):
        with patch("display.services.gate_results.get_effective_route_waypoints", return_value=ROUTE):
            return {r["gate"]: r for r in gate_results_for(contestant(planned, actual, entries))}

    def test_timed_untimed_and_missed_gates(self):
        planned = {"SP": at(0), "TP1": at(300), "SC1": at(450), "TP2": at(600), "FP": at(900)}
        actual = {"SP": at(3), "TP1": at(310), "SC1": at(452), "FP": at(870)}
        entries = [
            entry("SP", "passing gate (+3 s)", 3.0, planned=at(0), actual=at(3)),
            entry("TP1", "passing gate (no time check) (+10 s)", planned=at(300), actual=at(310)),
            entry("SC1", "passing gate (+2 s)", 0.0, planned=at(450), actual=at(452)),
            entry("TP2", "missing gate", 100.0),
            entry("FP", "passing gate (-30 s)", 84.0, planned=at(900), actual=at(870)),
        ]
        results = self.results(planned, actual, entries)
        self.assertNotIn("Dummy", results)  # never crossed
        self.assertEqual(results["SP"]["offset_seconds"], 3)
        self.assertEqual(results["SP"]["points"], 3.0)
        # No time check: crossed, but no offset
        self.assertIsNone(results["TP1"]["offset_seconds"])
        self.assertFalse(results["TP1"]["missed"])
        self.assertIsNotNone(results["TP1"]["actual"])
        # A secret gate is there, marked, for the map to hide
        self.assertTrue(results["SC1"]["hidden"])
        self.assertFalse(results["SP"]["hidden"])
        self.assertTrue(results["TP2"]["missed"])
        self.assertEqual(results["TP2"]["points"], 100.0)
        self.assertEqual(results["FP"]["offset_seconds"], -30)

    def test_adaptive_start_is_on_time_by_definition(self):
        # The crossing sets the start minute: the result's own times say 0 s, whatever the plan said before.
        planned = {"SP": at(-30), "FP": at(900)}
        actual = {"SP": at(0)}
        entries = [entry("SP", "adaptive start set (0 s)", planned=at(0), actual=at(0))]
        results = self.results(planned, actual, entries)
        self.assertEqual(results["SP"]["offset_seconds"], 0)
        self.assertIsNone(results["FP"]["actual"])
        self.assertFalse(results["FP"]["missed"])  # not reached yet, not missed

    def test_a_gate_missed_while_outside_the_corridor_scores_nothing(self):
        results = self.results({"TP1": at(300)}, {}, [entry("TP1", "missed TP1 while outside corridor")])
        self.assertTrue(results["TP1"]["missed"])
        self.assertEqual(results["TP1"]["points"], 0)
