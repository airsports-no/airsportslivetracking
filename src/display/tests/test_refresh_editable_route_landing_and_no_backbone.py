"""
Regression test (scorecard-system review roadmap, Phase 0 follow-up): NavigationTask.refresh_editable_route
was missing the LANDING case and the NO_BACKBONE_TASK_SUBTYPES branch that EditableRoute.create_route
(used at task-creation time) has - "Reload route" on the navigation task detail page reported
"Route refreshed" success while silently leaving the route unchanged for both cases.
"""

import datetime

from django.test import TestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import (
    get_default_scorecard as get_precision_scorecard,
)
from display.default_scorecards.default_scorecard_landing import get_default_scorecard as get_landing_scorecard
from display.models import Contest, EditableRoute, NavigationTask
from display.utilities.cima_task_type_definitions import CIRCLE

LANDING_GATE_FEATURE = {
    "type": "Feature",
    "properties": {"id": "ldg-1", "name": "LDG", "featureType": "landing_gate"},
    "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.0, 60.001]]},
}


class TestRefreshEditableRouteLandingAndNoBackbone(TestCase):
    def _create_contest(self, name):
        now = datetime.datetime.now(datetime.timezone.utc)
        return Contest.objects.create(
            name=name,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
            time_zone="Europe/Oslo",
        )

    def test_refresh_actually_rebuilds_the_route_for_a_landing_task(self):
        editable_route = EditableRoute.objects.create(
            name="Landing route",
            route={"type": "FeatureCollection", "features": [LANDING_GATE_FEATURE]},
        )
        scorecard = get_landing_scorecard()
        route = editable_route.create_route("landing", scorecard, None, None)
        navigation_task = NavigationTask.create(
            name="Landing refresh task",
            contest=self._create_contest("Landing refresh contest"),
            route=route,
            editable_route=editable_route,
            original_scorecard=scorecard,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
        )
        original_route_pk = navigation_task.route.pk

        navigation_task.refresh_editable_route()

        navigation_task.refresh_from_db()
        self.assertNotEqual(navigation_task.route.pk, original_route_pk)
        self.assertEqual(len(navigation_task.route.waypoints), 1)
        self.assertAlmostEqual(navigation_task.route.waypoints[0].latitude, 60.0, places=3)

    def test_refresh_rebuilds_the_placeholder_route_for_a_no_backbone_subtype(self):
        editable_route = EditableRoute.objects.create(
            name="Circle route",
            route={"type": "FeatureCollection", "features": []},
        )
        scorecard = get_precision_scorecard()
        route = editable_route.create_route("precision", scorecard, None, None, task_subtype=CIRCLE)
        navigation_task = NavigationTask.create(
            name="Circle refresh task",
            contest=self._create_contest("Circle refresh contest"),
            route=route,
            editable_route=editable_route,
            original_scorecard=scorecard,
            task_subtype=CIRCLE,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
        )
        original_route_pk = navigation_task.route.pk

        navigation_task.refresh_editable_route()

        navigation_task.refresh_from_db()
        self.assertNotEqual(navigation_task.route.pk, original_route_pk)
        self.assertEqual(navigation_task.route.waypoints, [])
