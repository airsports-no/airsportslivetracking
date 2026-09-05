"""
Tests for get_cima_gate_qmax (cima_score_normalization.py) - the catalogue's Qmax term for
2.A1/2.A2's "P = 1000 * Q / Qmax" formula, restricted to the gate-crossing component. See that
module's docstring for the full rationale (why only these two subtypes, why backtracking/
procedure-turn penalties are excluded from the sum).

Uses a real Scorecard (from create_scorecards()) so get_gate_scorecard()'s config-backed lookups
behave exactly as they do in production, but a lightweight SimpleNamespace for the navigation
task/route - get_cima_gate_qmax only reads effective_task_subtype, scorecard, and
route.waypoints/takeoff_gates/landing_gates, so a full NavigationTask/Contest/Contestant chain
would only add unrelated DB setup noise.
"""

from types import SimpleNamespace

from django.test import TestCase

from display.calculators.cima_score_normalization import get_cima_gate_qmax
from display.models import Scorecard
from display.utilities.cima_task_type_definitions import (
    ANR_CATALOGUE,
    CURVE_NAVIGATION_TIME_ESTIMATION,
    PRECISION_NAVIGATION,
)
from display.utilities.gate_definitions import DUMMY, LANDING_GATE, TAKEOFF_GATE, TURNPOINT
from display.waypoint import Waypoint


class TestGetCimaGateQmax(TestCase):
    def setUp(self):
        # A freshly-created, saved Scorecard (real pk) rather than mutating a shared original in
        # place - get_gate_scorecard() caches GateScoreValue per (pk, gate_type) keyed off a
        # per-pk cache-version string (SCORECARD_CACHE/_gate_scorecard_cache_version), so an
        # unsaved (pk=None) or reused/shared scorecard risks reading another test's stale cached
        # config. See test_gate_score_form_save.py for the same hazard.
        Scorecard.SCORECARD_CACHE.clear()
        self.scorecard = Scorecard.objects.create(
            name="qmax-test-scorecard",
            shortcut_name="qmax-test-scorecard",
            config={
                "gates": {
                    TURNPOINT: {"missed_penalty": 200, "maximum_penalty": 150},
                    "secret": {"missed_penalty": 50, "maximum_penalty": 50},
                    TAKEOFF_GATE: {"missed_penalty": 75, "maximum_penalty": 40},
                    LANDING_GATE: {"missed_penalty": 30, "maximum_penalty": 60},
                }
            },
        )

    def tearDown(self):
        Scorecard.SCORECARD_CACHE.clear()

    @staticmethod
    def _waypoint(gate_type: str, on_curved_segment: bool = False) -> Waypoint:
        waypoint = Waypoint(gate_type)
        waypoint.type = gate_type
        waypoint.on_curved_segment = on_curved_segment
        return waypoint

    def _task(self, subtype: str, waypoints: list, takeoff_gates=None, landing_gates=None):
        route = SimpleNamespace(
            waypoints=waypoints,
            takeoff_gates=takeoff_gates or [],
            landing_gates=landing_gates or [],
        )
        return SimpleNamespace(effective_task_subtype=subtype, scorecard=self.scorecard, route=route)

    def test_ineligible_subtype_returns_none(self):
        task = self._task(ANR_CATALOGUE, [self._waypoint(TURNPOINT)])
        self.assertIsNone(get_cima_gate_qmax(task))

    def test_empty_route_returns_none(self):
        task = self._task(PRECISION_NAVIGATION, [])
        self.assertIsNone(get_cima_gate_qmax(task))

    def test_sums_worst_case_per_gate_using_the_worse_of_missed_and_maximum_penalty(self):
        # tp: worse of 200/150 = 200. secret: worse of 50/50 = 50. Two tp + one secret.
        task = self._task(
            PRECISION_NAVIGATION,
            [self._waypoint(TURNPOINT), self._waypoint("secret"), self._waypoint(TURNPOINT)],
        )
        self.assertEqual(get_cima_gate_qmax(task), 200 + 50 + 200)

    def test_dummy_and_curved_segment_waypoints_are_excluded(self):
        task = self._task(
            PRECISION_NAVIGATION,
            [
                self._waypoint(TURNPOINT),
                self._waypoint(DUMMY),
                self._waypoint(TURNPOINT, on_curved_segment=True),
            ],
        )
        self.assertEqual(get_cima_gate_qmax(task), 200)

    def test_takeoff_and_landing_gates_included_when_present(self):
        task = self._task(
            CURVE_NAVIGATION_TIME_ESTIMATION,
            [self._waypoint(TURNPOINT)],
            takeoff_gates=[object()],
            landing_gates=[object()],
        )
        # tp: 200, takeoff: worse of 75/40 = 75, landing: worse of 30/60 = 60.
        self.assertEqual(get_cima_gate_qmax(task), 200 + 75 + 60)
