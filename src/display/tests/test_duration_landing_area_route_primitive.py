from django.test import TestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import EditableRoute, Scorecard
from display.utilities.cima_task_type_definitions import DURATION
from display.utilities.navigation_task_type_definitions import PRECISION


class TestDurationLandingAreaRoutePrimitive(TestCase):
    def test_can_fetch_duration_landing_area_polygons(self):
        editable_route = EditableRoute.objects.create(
            name="Duration Landing Area",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "dla-1",
                            "name": "Duration Landing Area 1",
                            "featureType": "zone",
                            "polygonType": "duration_landing_area",
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[11.0, 60.0], [11.2, 60.0], [11.2, 60.2], [11.0, 60.2], [11.0, 60.0]]],
                        },
                    }
                ],
            },
        )

        result = editable_route.get_duration_landing_area_polygons()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["properties"]["name"], "Duration Landing Area 1")


class TestDurationRouteCreation(TestCase):
    def test_creating_a_template_shaped_duration_task_produces_a_usable_route(self):
        # The 2.B3 template (taskTemplates.ts cima_b3) authors only optional
        # takeoff/landing gates and a duration_landing_area polygon - no
        # track waypoints at all. Before DURATION was added to
        # NO_BACKBONE_TASK_SUBTYPES, this fell through to
        # create_precision_route, which returns None for a route with no
        # track, so a template-shaped duration task could not be created.
        create_scorecards()
        scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        editable_route = EditableRoute.objects.create(
            name="Duration route creation",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"id": "to-1", "name": "Takeoff 1", "featureType": "takeoff_gate"},
                        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.001, 60.0]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "ldg-1", "name": "Landing 1", "featureType": "landing_gate"},
                        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.1], [11.001, 60.1]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "dla-1",
                            "name": "Duration Landing Area 1",
                            "featureType": "zone",
                            "polygonType": "duration_landing_area",
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[11.0, 60.0], [11.2, 60.0], [11.2, 60.2], [11.0, 60.2], [11.0, 60.0]]],
                        },
                    },
                ],
            },
        )

        route = editable_route.create_route(PRECISION, scorecard, None, None, task_subtype=DURATION)

        self.assertIsNotNone(route)
        self.assertEqual(route.waypoints, [])
        self.assertEqual(len(route.takeoff_gates), 1)
        self.assertEqual(len(route.landing_gates), 1)
        landing_area_zones = route.prohibited_set.filter(type="duration_landing_area")
        self.assertEqual(landing_area_zones.count(), 1)
        self.assertEqual(landing_area_zones.first().name, "Duration Landing Area 1")
