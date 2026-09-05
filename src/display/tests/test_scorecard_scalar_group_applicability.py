"""
Regression tests for get_applicable_scalar_groups() (Scorecard Phase 3 follow-up), the helper
behind the organizer-facing scorecard editor's "only show scalar-field cards that matter for
this task" filtering - reported as missing after the editor shipped: a Legacy Air Sports Race
task showed cards (ANR route, Duration, Circle, Speed keeping) that no calculator in its
pipeline ever reads a value from.

Each expected mapping below is verified against the real calculator pipeline
(utilities/task_type_registry.py) and each calculator's own subtype gating - see the extensive
comment above get_applicable_scalar_groups (services/scorecard_gate_applicability.py) for the
exact code references, not just asserted here.
"""

import datetime

from django.test import TestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import (
    get_default_scorecard as get_precision_scorecard,
)
from display.models import Contest, NavigationTask, Route, Scorecard
from display.services.scorecard_gate_applicability import get_applicable_scalar_groups
from display.utilities.cima_task_type_definitions import (
    ANR_CATALOGUE,
    CIRCLE,
    DURATION,
    KNOWN_CIRCUIT,
    LIMITED_FUEL_TURNPOINT_HUNT,
    TURNPOINT_HUNT,
)
from display.utilities.navigation_task_type_definitions import (
    AIRSPORT_CHALLENGE,
    AIRSPORTS,
    ANR_CORRIDOR,
    LANDING,
    POKER,
    PRECISION,
)


class TestScorecardScalarGroupApplicability(TestCase):
    def setUp(self):
        self.contest = Contest.objects.create(
            name="Scalar group applicability test contest",
            start_time=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
        )

    def _make_navigation_task(self, calculator: str, task_subtype: str | None = None) -> NavigationTask:
        scorecard = Scorecard.objects.create(
            name=f"scalar-group-test-{calculator}-{task_subtype}",
            shortcut_name=f"scalar-group-test-{calculator}-{task_subtype}",
            calculator=calculator,
        )
        route = Route.objects.create(name="test route")
        return NavigationTask.create(
            name="test task",
            contest=self.contest,
            route=route,
            original_scorecard=scorecard,
            start_time=datetime.datetime(2026, 1, 1, 6, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 1, 16, tzinfo=datetime.timezone.utc),
            task_subtype=task_subtype,
        )

    def test_legacy_precision_shows_backtracking_and_zones_only(self):
        navigation_task = self._make_navigation_task(PRECISION)
        self.assertEqual(
            {"Backtracking", "Zones"},
            get_applicable_scalar_groups(navigation_task),
        )

    def test_circle_subtype_removes_backtracking_and_adds_circle(self):
        navigation_task = self._make_navigation_task(PRECISION, task_subtype=CIRCLE)
        groups = get_applicable_scalar_groups(navigation_task)
        self.assertNotIn("Backtracking", groups)
        self.assertIn("Circle", groups)
        self.assertEqual({"Zones", "Circle"}, groups)

    def test_duration_subtype_adds_duration_group(self):
        navigation_task = self._make_navigation_task(PRECISION, task_subtype=DURATION)
        groups = get_applicable_scalar_groups(navigation_task)
        self.assertIn("Duration", groups)
        self.assertIn("Backtracking", groups)  # only CIRCLE removes backtracking, not DURATION
        self.assertNotIn("Circle", groups)

    def test_turnpoint_hunt_subtypes_add_duration_group(self):
        for subtype in (TURNPOINT_HUNT, LIMITED_FUEL_TURNPOINT_HUNT):
            navigation_task = self._make_navigation_task(PRECISION, task_subtype=subtype)
            self.assertIn("Duration", get_applicable_scalar_groups(navigation_task), subtype)

    def test_known_circuit_subtype_adds_speed_keeping(self):
        navigation_task = self._make_navigation_task(PRECISION, task_subtype=KNOWN_CIRCUIT)
        groups = get_applicable_scalar_groups(navigation_task)
        self.assertIn("Speed keeping", groups)
        self.assertNotIn("Duration", groups)
        self.assertNotIn("Circle", groups)

    def test_legacy_anr_corridor_shows_backtracking_zones_and_corridor_but_not_anr_route(self):
        navigation_task = self._make_navigation_task(ANR_CORRIDOR)
        self.assertEqual(
            {"Backtracking", "Zones", "Corridor"},
            get_applicable_scalar_groups(navigation_task),
        )

    def test_anr_catalogue_subtype_adds_anr_route(self):
        navigation_task = self._make_navigation_task(ANR_CORRIDOR, task_subtype=ANR_CATALOGUE)
        groups = get_applicable_scalar_groups(navigation_task)
        self.assertIn("ANR route", groups)

    def test_legacy_airsports_matches_legacy_anr_corridor_shape_without_anr_route(self):
        # The bug report this test guards: a Legacy Air Sports Race task must not show ANR
        # route, Duration, Circle, or Speed keeping - none of those are backed by any
        # calculator that runs for the AIRSPORTS family.
        navigation_task = self._make_navigation_task(AIRSPORTS)
        groups = get_applicable_scalar_groups(navigation_task)
        self.assertEqual({"Backtracking", "Zones", "Corridor"}, groups)
        for irrelevant in ("ANR route", "Duration", "Circle", "Speed keeping"):
            self.assertNotIn(irrelevant, groups)

    def test_legacy_airsport_challenge_matches_airsports_shape(self):
        navigation_task = self._make_navigation_task(AIRSPORT_CHALLENGE)
        self.assertEqual(
            {"Backtracking", "Zones", "Corridor"},
            get_applicable_scalar_groups(navigation_task),
        )

    def test_legacy_poker_shows_only_zones(self):
        navigation_task = self._make_navigation_task(POKER)
        self.assertEqual({"Zones"}, get_applicable_scalar_groups(navigation_task))

    def test_legacy_landing_shows_no_scalar_groups_at_all(self):
        navigation_task = self._make_navigation_task(LANDING)
        self.assertEqual(set(), get_applicable_scalar_groups(navigation_task))

    def test_real_precision_default_scorecard_still_resolves_correctly(self):
        # Sanity check against a real, fully-populated default scorecard rather than only the
        # minimal bare fixtures used above.
        navigation_task = NavigationTask.create(
            name="real precision test task",
            contest=self.contest,
            route=Route.objects.create(name="real precision test route"),
            original_scorecard=get_precision_scorecard(),
            start_time=datetime.datetime(2026, 1, 1, 6, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 1, 16, tzinfo=datetime.timezone.utc),
        )
        self.assertEqual(
            {"Backtracking", "Zones"},
            get_applicable_scalar_groups(navigation_task),
        )
