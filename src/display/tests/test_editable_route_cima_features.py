from django.test import TestCase

from display.models import EditableRoute


class TestEditableRouteCimaFeatures(TestCase):
    def setUp(self):
        self.route_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"featureType": "route_path"},
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[11.0, 60.0], [11.1, 60.1]],
                    },
                },
                {
                    "type": "Feature",
                    "properties": {
                        "id": "sp-1",
                        "name": "SP",
                        "pointType": "sp",
                        "featureType": "route_waypoint",
                        "width": 1852,
                        "isTiming": True,
                        "isPassing": True,
                        "sequence": 0,
                    },
                    "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                },
                {
                    "type": "Feature",
                    "properties": {
                        "id": "fp-1",
                        "name": "FP",
                        "pointType": "fp",
                        "featureType": "route_waypoint",
                        "width": 1852,
                        "isTiming": True,
                        "isPassing": True,
                        "sequence": 1,
                    },
                    "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                },
                {
                    "type": "Feature",
                    "properties": {
                        "id": "cat-1",
                        "name": "TP-CAT",
                        "pointType": "tp",
                        "featureType": "catalogue_turnpoint",
                    },
                    "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                },
                {
                    "type": "Feature",
                    "properties": {
                        "id": "cm-1",
                        "name": "CM",
                        "pointType": "circle_center",
                        "featureType": "circle_center_marker",
                    },
                    "geometry": {"type": "Point", "coordinates": [11.3, 60.3]},
                },
                {
                    "type": "Feature",
                    "properties": {
                        "id": "cs-1",
                        "name": "SP-C",
                        "pointType": "circle_start",
                        "featureType": "circle_start_marker",
                    },
                    "geometry": {"type": "Point", "coordinates": [11.31, 60.31]},
                },
                {
                    "type": "Feature",
                    "properties": {
                        "id": "ce-1",
                        "name": "X",
                        "pointType": "circle_entry",
                        "featureType": "circle_entry_marker",
                    },
                    "geometry": {"type": "Point", "coordinates": [11.32, 60.32]},
                },
                {
                    "type": "Feature",
                    "properties": {
                        "id": "cx-1",
                        "name": "WP",
                        "pointType": "circle_exit",
                        "featureType": "circle_exit_marker",
                    },
                    "geometry": {"type": "Point", "coordinates": [11.33, 60.33]},
                },
                {
                    "type": "Feature",
                    "properties": {
                        "id": "rts-1",
                        "name": "Route to SP",
                        "featureType": "route_to_sp_path",
                    },
                    "geometry": {"type": "LineString", "coordinates": [[10.9, 59.9], [11.0, 60.0]]},
                },
                {
                    "type": "Feature",
                    "properties": {
                        "id": "rfp-1",
                        "name": "Route from FP",
                        "featureType": "route_from_fp_path",
                    },
                    "geometry": {"type": "LineString", "coordinates": [[11.1, 60.1], [11.2, 60.0]]},
                },
                {
                    "type": "Feature",
                    "properties": {
                        "id": "kg-1",
                        "name": "KT1",
                        "pointType": "tp",
                        "featureType": "known_time_gate",
                    },
                    "geometry": {"type": "Point", "coordinates": [11.4, 60.4]},
                },
                {
                    "type": "Feature",
                    "properties": {
                        "id": "ul-1",
                        "name": "UL1",
                        "pointType": "ul",
                        "featureType": "route_waypoint",
                        "width": 1852,
                        "isTiming": False,
                        "isPassing": False,
                        "sequence": 2,
                    },
                    "geometry": {"type": "Point", "coordinates": [11.55, 60.55]},
                },
                {
                    "type": "Feature",
                    "properties": {
                        "id": "obs-1",
                        "name": "Photo 1",
                        "featureType": "observation_photo",
                    },
                    "geometry": {"type": "Point", "coordinates": [11.6, 60.6]},
                },
            ],
        }
        self.editable_route = EditableRoute.objects.create(name="CIMA primitives", route=self.route_data)

    def test_can_fetch_catalogue_turnpoints(self):
        result = self.editable_route.get_catalogue_turnpoints()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["properties"]["name"], "TP-CAT")

    def test_can_fetch_circle_center_markers(self):
        result = self.editable_route.get_circle_center_markers()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["properties"]["name"], "CM")

    def test_can_fetch_circle_start_markers(self):
        result = self.editable_route.get_circle_start_markers()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["properties"]["name"], "SP-C")

    def test_can_fetch_circle_entry_markers(self):
        result = self.editable_route.get_circle_entry_markers()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["properties"]["name"], "X")

    def test_can_fetch_circle_exit_markers(self):
        result = self.editable_route.get_circle_exit_markers()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["properties"]["name"], "WP")

    def test_can_fetch_route_to_sp_paths(self):
        result = self.editable_route.get_route_to_sp_paths()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["properties"]["name"], "Route to SP")

    def test_can_fetch_route_from_fp_paths(self):
        result = self.editable_route.get_route_from_fp_paths()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["properties"]["name"], "Route from FP")

    def test_can_fetch_known_time_gates(self):
        result = self.editable_route.get_known_time_gates()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["properties"]["name"], "KT1")

    def test_can_fetch_unknown_leg_waypoints(self):
        result = self.editable_route.get_unknown_leg_waypoints()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["properties"]["name"], "UL1")

    def test_can_fetch_observation_photos(self):
        result = self.editable_route.get_observation_photos()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["properties"]["name"], "Photo 1")

    def test_get_hidden_gates_also_matches_ordinary_secret_points(self):
        """CIMA hidden gates are authored as plain secret points, so an ordinary secret backbone
        point is also counted under the hidden_gate primitive."""
        editable_route = EditableRoute.objects.create(
            name="Secret point as hidden gate",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "sec-1",
                            "name": "Secret 1.1",
                            "pointType": "secret",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": False,
                            "isPassing": True,
                            "sequence": 0,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.7, 60.7]},
                    },
                ],
            },
        )
        result = editable_route.get_hidden_gates()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["properties"]["name"], "Secret 1.1")
