"""
Regression test: build_navigation_task_information's handling of "legacy_*" task subtypes -
i.e. essentially every real navigation task, since task_subtype is only ever set for tasks
explicitly authored under the newer CIMA task-subtype system - produced only a generic
one-line "This task uses the X family." fallback (plus, at best, a couple of scorecard-driven
lines for precision/ANR), even though the 2026-08-01 rewrite (commit 0b7217b8) that introduced
task_information.py was meant to be the sole source for TaskInfoModal.tsx's rules text,
replacing the older React About*.tsx components (AboutPrecisionFlying, AboutANR, AboutAirsports,
AboutAirsportChallenge, AboutPilotPokerRun) which read scorecard values directly and rendered
full rules text - those components became orphaned/unwired at that point and their content was
never ported over for legacy tasks. This restores equivalent rich, scorecard-driven content for
every legacy family.

Also covers a bug caught while restoring this: corridor_maximum_penalty's -1 sentinel ("no
maximum configured", ConfigField(-1)'s default) used to render as "Maximum corridor penalty is
-1 points." whenever a scorecard hadn't set a real maximum, because the guarding check
(`if getattr(scorecard, "corridor_maximum_penalty", 0):`) tested the truthiness of the value,
not whether it was actually configured - and -1 is truthy.
"""

import datetime

from django.test import TestCase

from display.default_scorecards.default_scorecard_airsport_challenge import (
    get_default_scorecard as get_airsport_challenge_scorecard,
)
from display.default_scorecards.default_scorecard_airsports import get_default_scorecard as get_airsports_scorecard
from display.default_scorecards.default_scorecard_fai_anr_2017 import get_default_scorecard as get_anr_scorecard
from display.default_scorecards.default_scorecard_fai_precision_2020 import (
    get_default_scorecard as get_precision_scorecard,
)
from display.default_scorecards.default_scorecard_landing import get_default_scorecard as get_landing_scorecard
from display.default_scorecards.default_scorecard_poker_run import get_default_scorecard as get_poker_scorecard
from display.models import Contest, NavigationTask, Route, Scorecard
from display.utilities.gate_definitions import (
    ANR_TP,
    FINISHPOINT,
    LANDING_GATE,
    STARTINGPOINT,
    TAKEOFF_GATE,
    TURNPOINT,
)
from display.utilities.navigation_task_type_definitions import ANR_CORRIDOR
from display.utilities.task_information import build_navigation_task_information
from display.waypoint import Waypoint


def make_waypoint(gate_type: str, name: str = "wp") -> Waypoint:
    waypoint = Waypoint(name)
    waypoint.type = gate_type
    waypoint.width = 1.0
    return waypoint


class TestLegacyTaskInformationRestored(TestCase):
    def setUp(self):
        self.contest = Contest.objects.create(
            name="Legacy task info test contest",
            start_time=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
        )

    def _make_navigation_task(
        self, scorecard, waypoints=None, takeoff_gates=None, landing_gates=None
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
        )

    def test_legacy_precision_gets_rich_objective_and_overrides(self):
        navigation_task = self._make_navigation_task(
            get_precision_scorecard(),
            waypoints=[make_waypoint(STARTINGPOINT), make_waypoint(TURNPOINT), make_waypoint(FINISHPOINT)],
            takeoff_gates=[make_waypoint(TAKEOFF_GATE)],
        )
        info = build_navigation_task_information(navigation_task)
        self.assertNotIn("This task uses the", info["objective"])
        self.assertTrue(any("Timed gates currently score" in line for line in info["overrides"]))
        self.assertTrue(any("extended starting line" in line for line in info["overrides"]))
        self.assertTrue(any("takeoff gate" in line for line in info["overrides"]))

    def test_legacy_anr_corridor_gets_rich_objective_and_overrides(self):
        navigation_task = self._make_navigation_task(
            get_anr_scorecard(),
            waypoints=[make_waypoint(STARTINGPOINT), make_waypoint(ANR_TP), make_waypoint(FINISHPOINT)],
        )
        info = build_navigation_task_information(navigation_task)
        self.assertNotIn("This task uses the", info["objective"])
        self.assertTrue(any("Missing the starting point" in line for line in info["overrides"]))
        self.assertTrue(any("Missing the finish point" in line for line in info["overrides"]))

    def test_legacy_airsports_gets_rich_objective_and_overrides(self):
        navigation_task = self._make_navigation_task(
            get_airsports_scorecard(),
            waypoints=[make_waypoint(STARTINGPOINT), make_waypoint(TURNPOINT), make_waypoint(FINISHPOINT)],
        )
        info = build_navigation_task_information(navigation_task)
        self.assertNotIn("This task uses the", info["objective"])
        self.assertTrue(any("Regular gates currently score" in line for line in info["overrides"]))
        self.assertTrue(any("Secret gates currently score" in line for line in info["overrides"]))

    def test_legacy_airsport_challenge_gets_rich_objective(self):
        navigation_task = self._make_navigation_task(get_airsport_challenge_scorecard())
        info = build_navigation_task_information(navigation_task)
        self.assertNotIn("This task uses the", info["objective"])

    def test_legacy_poker_gets_rich_objective_and_summary(self):
        navigation_task = self._make_navigation_task(get_poker_scorecard())
        info = build_navigation_task_information(navigation_task)
        self.assertNotIn("This task uses the", info["objective"])
        self.assertTrue(any("poker hand" in line for line in info["summary"]))

    def test_legacy_landing_gets_an_objective(self):
        navigation_task = self._make_navigation_task(
            get_landing_scorecard(), landing_gates=[make_waypoint(LANDING_GATE)]
        )
        info = build_navigation_task_information(navigation_task)
        self.assertNotIn("This task uses the", info["objective"])

    def test_corridor_maximum_penalty_sentinel_is_not_rendered_as_a_line(self):
        # corridor_maximum_penalty defaults to -1 ("no maximum configured", ConfigField(-1))
        # and must never be printed as "Maximum corridor penalty is -1 points."
        scorecard = Scorecard.objects.create(
            name="Bare ANR test", shortcut_name="bare-anr-test", calculator=ANR_CORRIDOR
        )
        self.assertEqual(-1, scorecard.corridor_maximum_penalty)
        navigation_task = self._make_navigation_task(
            scorecard,
            waypoints=[make_waypoint(STARTINGPOINT), make_waypoint(ANR_TP), make_waypoint(FINISHPOINT)],
        )
        info = build_navigation_task_information(navigation_task)
        self.assertFalse(any("-1 points" in line for line in info["overrides"]), info["overrides"])

    def test_corridor_maximum_penalty_is_rendered_once_actually_configured(self):
        scorecard = Scorecard.objects.create(
            name="Configured ANR test", shortcut_name="configured-anr-test", calculator=ANR_CORRIDOR
        )
        scorecard.corridor_maximum_penalty = 250
        scorecard.save()
        navigation_task = self._make_navigation_task(
            scorecard,
            waypoints=[make_waypoint(STARTINGPOINT), make_waypoint(ANR_TP), make_waypoint(FINISHPOINT)],
        )
        info = build_navigation_task_information(navigation_task)
        self.assertTrue(
            any("Maximum corridor penalty is 250 points" in line for line in info["overrides"]), info["overrides"]
        )
