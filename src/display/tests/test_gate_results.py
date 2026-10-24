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
    def results(self, planned, actual, entries, display_secrets=True):
        c = contestant(planned, actual, entries)
        c.navigation_task.display_secrets = display_secrets
        with patch("display.services.gate_results.get_effective_route_waypoints", return_value=ROUTE):
            return {r["gate"]: r for r in gate_results_for(c)}

    def test_a_task_that_hides_secrets_does_not_send_them(self):
        planned = {"SP": at(0), "SC1": at(450)}
        actual = {"SP": at(0), "SC1": at(452)}
        entries = [entry("SC1", "passing gate (+2 s)", 0.0, planned=at(450), actual=at(452))]
        self.assertIn("SC1", self.results(planned, actual, entries))
        self.assertNotIn("SC1", self.results(planned, actual, entries, display_secrets=False))

    def test_several_timing_entries_at_a_gate_add_up(self):
        entries = [
            entry("SP", "passing gate (+3 s)", 3.0, planned=at(0), actual=at(3)),
            entry("SP", "passing gate (+5 s)", 5.0, planned=at(0), actual=at(5)),
        ]
        self.assertEqual(self.results({"SP": at(0)}, {"SP": at(5)}, entries)["SP"]["points"], 8.0)

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


class TestScoreLogBroadcast(TestCase):
    def test_the_log_entries_go_out_even_if_the_gate_results_cannot_be_built(self):
        from websocket_channels import WebsocketFacade

        contestant = MagicMock()
        contestant.navigation_task.pk = 5
        contestant.scorelogentry_set.filter.return_value = []
        facade = WebsocketFacade.__new__(WebsocketFacade)
        facade._safe_group_send = MagicMock()
        with (
            patch("display.services.gate_results.gate_results_for", side_effect=RuntimeError("no route")),
            patch("websocket_channels.generate_contestant_data_block", return_value={"score_log_entries": []}),
        ):
            facade.transmit_score_log_entry(contestant)  # must not raise
        facade._safe_group_send.assert_called_once()
        message = facade._safe_group_send.call_args.args[1]["data"]
        self.assertEqual(message["type"], "score_log")
        self.assertNotIn("gate_results", message["data"])


class TestHiddenGatesStayOnTheServer(TestCase):
    def block(self, display_secrets):
        from websocket_channels import generate_contestant_data_block

        c = MagicMock(adaptive_start=True, gate_times={"SP": 1, "SC1": 2})
        c.navigation_task.display_secrets = display_secrets
        with patch("display.services.gate_results.get_effective_route_waypoints", return_value=ROUTE):
            return generate_contestant_data_block(
                c,
                annotations=[{"gate": "SC1", "gate_type": "secret"}, {"gate": "SP", "gate_type": "sp"}],
                log_entries=[{"gate": "SC1"}, {"gate": "SP"}],
                gate_scores=[{"gate": "SC1"}, {"gate": "SP"}],
            )

    def test_nothing_about_a_secret_gate_leaves_when_the_task_hides_secrets(self):
        data = self.block(False)
        self.assertEqual([a["gate"] for a in data["annotations"]], ["SP"])
        self.assertEqual([a["gate"] for a in data["score_log_entries"]], ["SP"])
        self.assertEqual([a["gate"] for a in data["gate_scores"]], ["SP"])
        self.assertEqual(list(data["gate_times"]), ["SP"])

    def test_everything_goes_when_the_task_shows_secrets(self):
        data = self.block(True)
        self.assertEqual(len(data["score_log_entries"]), 2)
        self.assertIn("SC1", data["gate_times"])


class TestWaypointCache(TestCase):
    def test_a_compiled_route_is_rehydrated_once_per_configuration_version(self):
        from display.services import gate_results

        gate_results._waypoint_cache.clear()
        c = MagicMock()
        config = c.contestanttaskconfiguration
        config.is_valid = True
        config.pk, config.updated_at = 5, "v1"
        config.compiled_effective_route_payload = {"effective_waypoints": [{"name": "SP"}]}
        with patch("display.services.gate_results.get_effective_route_waypoints", return_value=ROUTE) as rehydrate:
            gate_results.effective_waypoints_for(c)
            gate_results.effective_waypoints_for(c)
            self.assertEqual(rehydrate.call_count, 1)
            config.updated_at = "v2"
            gate_results.effective_waypoints_for(c)
            self.assertEqual(rehydrate.call_count, 2)
