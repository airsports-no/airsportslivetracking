"""
Regression test for Sentry PYTHON-DJANGO-1B: EditableRouteSerialiser's `route` field help_text
still documents the pre-0120_auto_20251228_2126 legacy list format (feature_type/layer_type/
track_points), but nothing converted it any more once the model's internal representation moved
to a GeoJSON FeatureCollection - a client still submitting exactly what the field describes got
an unhandled TypeError 500 deep in the post_save signal (calculate_editable_route_statistics ->
get_track() -> self.route["features"] on a list) instead of either a clean error or it actually
working. EditableRouteSerialiser.validate_route() now converts a legacy list submission via the
same convert_legacy_json() the migration used, and rejects anything that's neither shape with a
clean 400 instead of crashing.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from rest_framework.test import APIClient

from display.models import EditableRoute


class TestEditableRouteLegacyFormatApi(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="editable-route-legacy@example.com")
        self.user.user_permissions.add(Permission.objects.get(codename="add_editableroute"))
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_creating_a_route_from_the_documented_legacy_list_format_succeeds(self):
        payload = {
            "name": "Legacy format route",
            "settings": {},
            "route": [
                {
                    "feature_type": "track",
                    "layer_type": "polyline",
                    "name": "Track",
                    "tooltip_position": [0, 0],
                    "track_points": [
                        {
                            "name": "SP",
                            "gateType": "sp",
                            "timeCheck": True,
                            "gateWidth": 1,
                            "position": {"lat": 60.0, "lng": 11.0},
                        },
                        {
                            "name": "FP",
                            "gateType": "fp",
                            "timeCheck": True,
                            "gateWidth": 1,
                            "position": {"lat": 60.1, "lng": 11.1},
                        },
                    ],
                    "geojson": {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]},
                    },
                }
            ],
        }

        response = self.client.post("/api/v1/editableroutes/", payload, format="json")

        self.assertEqual(201, response.status_code, response.content)
        route = EditableRoute.objects.get(name="Legacy format route")
        self.assertEqual(route.route["type"], "FeatureCollection")
        feature_types = {f["properties"]["featureType"] for f in route.route["features"]}
        self.assertIn("route_path", feature_types)
        self.assertIn("route_waypoint", feature_types)
        # The regression itself: this used to crash with an unhandled 500 inside
        # calculate_editable_route_statistics instead of reaching this point at all.
        self.assertEqual(route.number_of_waypoints, 2)

    def test_creating_a_route_with_neither_geojson_nor_legacy_list_is_rejected_cleanly(self):
        payload = {"name": "Malformed route", "settings": {}, "route": "not a route"}

        response = self.client.post("/api/v1/editableroutes/", payload, format="json")

        self.assertEqual(400, response.status_code, response.content)
        self.assertIn("route", response.json())
        self.assertFalse(EditableRoute.objects.filter(name="Malformed route").exists())

    def test_creating_a_route_with_a_geojson_feature_collection_still_works(self):
        payload = {
            "name": "GeoJSON route",
            "settings": {},
            "route": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]},
                    },
                ],
            },
        }

        response = self.client.post("/api/v1/editableroutes/", payload, format="json")

        self.assertEqual(201, response.status_code, response.content)
        route = EditableRoute.objects.get(name="GeoJSON route")
        self.assertEqual(route.route["type"], "FeatureCollection")


class TestEditableRouteIntendedTaskTypesApi(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="editable-route-intent@example.com")
        self.user.user_permissions.add(Permission.objects.get(codename="add_editableroute"))
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.route_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"featureType": "route_path"},
                    "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]},
                },
                {
                    "type": "Feature",
                    "properties": {
                        "id": "TP-1",
                        "name": "TP",
                        "pointType": "tp",
                        "featureType": "route_waypoint",
                        "width": 1852,
                        "isTiming": True,
                        "isPassing": True,
                        "sequence": 0,
                    },
                    "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                },
            ],
        }

    def test_writes_store_what_is_sent_and_reads_return_it(self):
        response = self.client.post(
            "/api/v1/editableroutes/",
            {"name": "Intent route", "settings": {}, "route": self.route_data, "intended_task_types": []},
            format="json",
        )
        self.assertEqual(201, response.status_code, response.content)
        route = EditableRoute.objects.get(name="Intent route")
        self.assertEqual([], response.json()["intended_task_types"])
        compatible = list(route.compatible_task_types)
        self.assertGreater(len(compatible), 1)

        # An explicit declaration of every compatible type is kept, and read back as declared.
        route.intended_task_types = compatible
        route.save()
        route.refresh_from_db()
        self.assertEqual(set(compatible), set(route.intended_task_types))
        detail = self.client.get(f"/api/v1/editableroutes/{route.pk}/")
        self.assertEqual(200, detail.status_code, detail.content)
        self.assertEqual(set(compatible), set(detail.json()["intended_task_types"]))

        # A deliberate choice round-trips through a save.
        patch = self.client.patch(
            f"/api/v1/editableroutes/{route.pk}/", {"intended_task_types": compatible[:1]}, format="json"
        )
        self.assertEqual(200, patch.status_code, patch.content)
        self.assertEqual(compatible[:1], patch.json()["intended_task_types"])
        route.refresh_from_db()
        self.assertEqual(compatible[:1], route.intended_task_types)
