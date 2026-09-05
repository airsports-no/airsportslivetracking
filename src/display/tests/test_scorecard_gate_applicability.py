"""
Regression tests for get_applicable_gate_types() (Scorecard Phase 3), the new helper behind
the organizer-facing scorecard editor's "only show gate types that matter for this task"
filtering.

Fixtures build a minimal Route directly (hand-constructed Waypoint objects) rather than
running a navigation task through the full EditableRoute/CSV pipeline - the function under
test only ever reads navigation_task.effective_task_subtype and
navigation_task.route.{waypoints,takeoff_gates,landing_gates}, so a minimal fixture that
controls exactly those three inputs is both faster and a more precise test of the function's
actual contract.
"""

import datetime

from django.test import TestCase

from display.default_scorecards.default_scorecard_fai_anr_2017 import get_default_scorecard as get_anr_scorecard
from display.default_scorecards.default_scorecard_fai_precision_2020 import (
    get_default_scorecard as get_precision_scorecard,
)
from display.default_scorecards.default_scorecard_landing import get_default_scorecard as get_landing_scorecard
from display.default_scorecards.default_scorecard_poker_run import get_default_scorecard as get_poker_scorecard
from display.models import Contest, NavigationTask, Route
from display.services.scorecard_gate_applicability import get_applicable_gate_types
from display.utilities.cima_task_type_definitions import (
    CIRCLE,
    DURATION,
    LIMITED_FUEL_TURNPOINT_HUNT,
    TURNPOINT_HUNT,
)
from display.utilities.gate_definitions import (
    ANR_TP,
    CIRCLE_ENTRY,
    CIRCLE_EXIT,
    CIRCLE_START,
    DUMMY,
    FINISHPOINT,
    LANDING_GATE,
    SECRETPOINT,
    STARTINGPOINT,
    TAKEOFF_GATE,
    TURNPOINT,
    UNKNOWN_LEG,
)
from display.waypoint import Waypoint


def make_waypoint(gate_type: str, name: str = "wp", on_curved_segment: bool = False) -> Waypoint:
    waypoint = Waypoint(name)
    waypoint.type = gate_type
    waypoint.on_curved_segment = on_curved_segment
    return waypoint


class TestScorecardGateApplicability(TestCase):
    def setUp(self):
        self.contest = Contest.objects.create(
            name="Applicability test contest",
            start_time=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
        )

    def _make_navigation_task(
        self,
        scorecard,
        waypoints=None,
        takeoff_gates=None,
        landing_gates=None,
        task_subtype=None,
    ) -> NavigationTask:
        route = Route.objects.create(
            name="test route",
            waypoints=waypoints or [],
            takeoff_gates=takeoff_gates or [],
            landing_gates=landing_gates or [],
        )
        return NavigationTask.create(
            name="test task",
            contest=self.contest,
            route=route,
            original_scorecard=scorecard,
            start_time=datetime.datetime(2026, 1, 1, 6, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 1, 16, tzinfo=datetime.timezone.utc),
            task_subtype=task_subtype,
        )

    def test_precision_task_uses_sp_tp_fp_secret_and_gate_lines(self):
        navigation_task = self._make_navigation_task(
            get_precision_scorecard(),
            waypoints=[
                make_waypoint(STARTINGPOINT),
                make_waypoint(TURNPOINT),
                make_waypoint(SECRETPOINT),
                make_waypoint(FINISHPOINT),
            ],
            takeoff_gates=[make_waypoint(TAKEOFF_GATE)],
            landing_gates=[make_waypoint(LANDING_GATE)],
        )
        self.assertEqual(
            {STARTINGPOINT, TURNPOINT, SECRETPOINT, FINISHPOINT, TAKEOFF_GATE, LANDING_GATE},
            get_applicable_gate_types(navigation_task),
        )

    def test_dummy_waypoints_are_never_applicable(self):
        navigation_task = self._make_navigation_task(
            get_precision_scorecard(),
            waypoints=[make_waypoint(STARTINGPOINT), make_waypoint(DUMMY), make_waypoint(FINISHPOINT)],
        )
        self.assertNotIn(DUMMY, get_applicable_gate_types(navigation_task))

    def test_curve_interpolation_secret_waypoints_are_excluded_but_authored_secret_gates_are_not(self):
        navigation_task = self._make_navigation_task(
            get_precision_scorecard(),
            waypoints=[
                make_waypoint(STARTINGPOINT),
                make_waypoint(SECRETPOINT, name="authored hidden turnpoint", on_curved_segment=False),
                make_waypoint(SECRETPOINT, name="curve interpolation point", on_curved_segment=True),
                make_waypoint(FINISHPOINT),
            ],
        )
        # SECRETPOINT is still applicable (from the authored waypoint) - the point is that the
        # on_curved_segment filter doesn't accidentally drop the whole gate type, only the
        # synthesized interpolation points that happen to share its type.
        self.assertIn(SECRETPOINT, get_applicable_gate_types(navigation_task))

    def test_curve_interpolation_only_secretpoint_is_excluded_with_no_authored_gate_present(self):
        # The other test above only exercises the "still included" side (an authored
        # SECRETPOINT masks whether the curved one was actually filtered). With no authored
        # SECRETPOINT at all, the curved-only one must not make the gate type applicable.
        navigation_task = self._make_navigation_task(
            get_precision_scorecard(),
            waypoints=[
                make_waypoint(STARTINGPOINT),
                make_waypoint(SECRETPOINT, name="curve interpolation point", on_curved_segment=True),
                make_waypoint(FINISHPOINT),
            ],
        )
        self.assertNotIn(SECRETPOINT, get_applicable_gate_types(navigation_task))

    def test_anr_task_uses_sp_anrtp_fp_and_gate_lines_not_secret_or_dummy(self):
        navigation_task = self._make_navigation_task(
            get_anr_scorecard(),
            waypoints=[
                make_waypoint(STARTINGPOINT),
                make_waypoint(ANR_TP),
                make_waypoint(SECRETPOINT, name="curve interpolation point", on_curved_segment=True),
                make_waypoint(FINISHPOINT),
            ],
            takeoff_gates=[make_waypoint(TAKEOFF_GATE)],
            landing_gates=[make_waypoint(LANDING_GATE)],
        )
        self.assertEqual(
            {STARTINGPOINT, ANR_TP, FINISHPOINT, TAKEOFF_GATE, LANDING_GATE},
            get_applicable_gate_types(navigation_task),
        )

    def test_landing_task_uses_only_ldg(self):
        navigation_task = self._make_navigation_task(
            get_landing_scorecard(),
            waypoints=[make_waypoint(LANDING_GATE)],
            landing_gates=[make_waypoint(LANDING_GATE)],
        )
        self.assertEqual({LANDING_GATE}, get_applicable_gate_types(navigation_task))

    def test_unknown_leg_task_includes_ul(self):
        navigation_task = self._make_navigation_task(
            get_precision_scorecard(),
            waypoints=[
                make_waypoint(STARTINGPOINT),
                make_waypoint(UNKNOWN_LEG),
                make_waypoint(DUMMY),
                make_waypoint(FINISHPOINT),
            ],
        )
        gate_types = get_applicable_gate_types(navigation_task)
        self.assertIn(UNKNOWN_LEG, gate_types)
        self.assertNotIn(DUMMY, gate_types)

    def test_poker_run_task_only_includes_gates_actually_on_its_route(self):
        # The Poker Run default scorecard configures all 16 GATE_TYPES identically
        # (default_scorecard_poker_run.py) - a real poker task's route only ever uses a
        # handful of them, and applicability must reflect the route, not the scorecard.
        navigation_task = self._make_navigation_task(
            get_poker_scorecard(),
            waypoints=[make_waypoint(STARTINGPOINT), make_waypoint(TURNPOINT), make_waypoint(FINISHPOINT)],
        )
        self.assertEqual({STARTINGPOINT, TURNPOINT, FINISHPOINT}, get_applicable_gate_types(navigation_task))

    def test_circle_subtype_uses_static_table_not_empty_route(self):
        navigation_task = self._make_navigation_task(get_precision_scorecard(), task_subtype=CIRCLE)
        self.assertEqual(
            {CIRCLE_START, CIRCLE_ENTRY, CIRCLE_EXIT},
            get_applicable_gate_types(navigation_task),
        )

    def test_turnpoint_hunt_subtype_uses_static_table(self):
        navigation_task = self._make_navigation_task(get_precision_scorecard(), task_subtype=TURNPOINT_HUNT)
        self.assertEqual({TURNPOINT}, get_applicable_gate_types(navigation_task))

    def test_limited_fuel_turnpoint_hunt_subtype_uses_static_table(self):
        navigation_task = self._make_navigation_task(
            get_precision_scorecard(), task_subtype=LIMITED_FUEL_TURNPOINT_HUNT
        )
        self.assertEqual({TURNPOINT}, get_applicable_gate_types(navigation_task))

    def test_duration_subtype_uses_static_table(self):
        navigation_task = self._make_navigation_task(get_precision_scorecard(), task_subtype=DURATION)
        self.assertEqual({TAKEOFF_GATE, LANDING_GATE}, get_applicable_gate_types(navigation_task))
