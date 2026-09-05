"""
Tests for get_cima_gate_qmax (cima_score_normalization.py) - the catalogue's Qmax term for
2.A1-2.A5's "P = 1000 * Q / Qmax" formula, restricted to the gate-crossing component. See that
module's docstring for the full rationale (why only these five subtypes, why backtracking/
speed-keeping/observation-evidence are excluded from the sum, and why gate_check/time_check -
not just gate type - determine a waypoint's worst-case contribution).

Uses a real Scorecard (from create_scorecards()) so get_gate_scorecard()'s config-backed lookups
behave exactly as they do in production, but a lightweight SimpleNamespace for the
contestant/navigation task/route - get_cima_gate_qmax only reads effective_task_subtype,
scorecard, and route.waypoints/takeoff_gates/landing_gates (via get_effective_route_waypoints,
which falls back to the shared route when the contestant has no
contestanttaskconfiguration - a SimpleNamespace contestant naturally exercises that fallback),
so a full NavigationTask/Contest/Contestant DB chain would only add unrelated setup noise here.
Contestant-declared effective-route behavior (the 2.A3 case where the fallback does NOT apply)
is covered separately in test_cima_descending_scoring.py against real DB models, since it needs
a real ContestantTaskConfiguration.
"""

from types import SimpleNamespace

from django.test import TestCase

from display.calculators.cima_score_normalization import get_cima_gate_qmax
from display.models import Scorecard
from display.utilities.cima_task_type_definitions import (
    ANR_CATALOGUE,
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    CURVE_NAVIGATION_TIME_ESTIMATION,
    KNOWN_CIRCUIT,
    PRECISION_NAVIGATION,
    UNKNOWN_LEGS,
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
    def _waypoint(
        gate_type: str, *, on_curved_segment: bool = False, gate_check: bool = True, time_check: bool = True
    ) -> Waypoint:
        # gate_check/time_check default True: matches how a normal scored CIMA turnpoint/secret
        # gate is authored, and preserves this test module's original expected sums for waypoints
        # that don't explicitly test the flags-off cases below.
        waypoint = Waypoint(gate_type)
        waypoint.type = gate_type
        waypoint.on_curved_segment = on_curved_segment
        waypoint.gate_check = gate_check
        waypoint.time_check = time_check
        return waypoint

    def _contestant(self, subtype: str, waypoints: list, takeoff_gates=None, landing_gates=None):
        route = SimpleNamespace(
            waypoints=waypoints,
            takeoff_gates=takeoff_gates or [],
            landing_gates=landing_gates or [],
        )
        navigation_task = SimpleNamespace(effective_task_subtype=subtype, scorecard=self.scorecard, route=route)
        # No contestanttaskconfiguration attribute at all - get_effective_route_waypoints falls
        # back to the shared route.waypoints, which is what every non-per-contestant-declared
        # subtype (everything tested in this file) actually does in production too.
        return SimpleNamespace(navigation_task=navigation_task)

    def test_ineligible_subtype_returns_none(self):
        contestant = self._contestant(ANR_CATALOGUE, [self._waypoint(TURNPOINT)])
        self.assertIsNone(get_cima_gate_qmax(contestant))

    def test_empty_route_returns_none(self):
        contestant = self._contestant(PRECISION_NAVIGATION, [])
        self.assertIsNone(get_cima_gate_qmax(contestant))

    def test_sums_worst_case_per_gate_using_the_worse_of_missed_and_maximum_penalty(self):
        # tp: worse of 200/150 = 200. secret: worse of 50/50 = 50. Two tp + one secret.
        contestant = self._contestant(
            PRECISION_NAVIGATION,
            [self._waypoint(TURNPOINT), self._waypoint("secret"), self._waypoint(TURNPOINT)],
        )
        self.assertEqual(get_cima_gate_qmax(contestant), 200 + 50 + 200)

    def test_dummy_and_curved_segment_waypoints_are_excluded(self):
        contestant = self._contestant(
            PRECISION_NAVIGATION,
            [
                self._waypoint(TURNPOINT),
                self._waypoint(DUMMY),
                self._waypoint(TURNPOINT, on_curved_segment=True),
            ],
        )
        self.assertEqual(get_cima_gate_qmax(contestant), 200)

    def test_takeoff_and_landing_gates_included_when_present_using_timing_cap_only(self):
        # Takeoff/landing have no "missed" scoring path at all (see module docstring), so their
        # worst case is maximum_penalty only, never missed_penalty: takeoff worse-of(0, 40) = 40,
        # not 75; landing worse-of(0, 60) = 60 (coincides with its missed_penalty here, but for
        # the right reason - verified via the takeoff case, which does NOT coincide).
        contestant = self._contestant(
            CURVE_NAVIGATION_TIME_ESTIMATION,
            [self._waypoint(TURNPOINT)],
            takeoff_gates=[object()],
            landing_gates=[object()],
        )
        self.assertEqual(get_cima_gate_qmax(contestant), 200 + 40 + 60)

    def test_waypoint_with_neither_check_flag_contributes_nothing(self):
        # Can never be missed-penalized (gate_check False) or timing-penalized (time_check
        # False, so on_gate_passed's "no time check" branch always scores 0) - counting its
        # missed_penalty/maximum_penalty would inflate Qmax for a scenario that can't happen.
        contestant = self._contestant(
            PRECISION_NAVIGATION,
            [
                self._waypoint(TURNPOINT),
                self._waypoint(TURNPOINT, gate_check=False, time_check=False),
            ],
        )
        self.assertEqual(get_cima_gate_qmax(contestant), 200)

    def test_gate_check_only_waypoint_uses_missed_penalty_only(self):
        contestant = self._contestant(
            PRECISION_NAVIGATION,
            [self._waypoint(TURNPOINT, gate_check=True, time_check=False)],
        )
        self.assertEqual(get_cima_gate_qmax(contestant), 200)  # missed_penalty, not maximum_penalty

    def test_time_check_only_waypoint_uses_maximum_penalty_only(self):
        contestant = self._contestant(
            PRECISION_NAVIGATION,
            [self._waypoint(TURNPOINT, gate_check=False, time_check=True)],
        )
        self.assertEqual(get_cima_gate_qmax(contestant), 150)  # maximum_penalty, not missed_penalty

    def test_all_qmax_eligible_subtypes_are_supported(self):
        for subtype in (
            CURVE_NAVIGATION_TIME_ESTIMATION,
            PRECISION_NAVIGATION,
            CONTRACT_NAVIGATION_TIME_CONTROLS,
            KNOWN_CIRCUIT,
            UNKNOWN_LEGS,
        ):
            with self.subTest(subtype=subtype):
                contestant = self._contestant(subtype, [self._waypoint(TURNPOINT)])
                self.assertEqual(get_cima_gate_qmax(contestant), 200)
