from django.test import TestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import EditableRoute, Route, Scorecard
from display.utilities.gate_definitions import SECRETPOINT


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
                        "id": "hg-1",
                        "name": "HG1",
                        "pointType": "tp",
                        "featureType": "hidden_gate",
                    },
                    "geometry": {"type": "Point", "coordinates": [11.5, 60.5]},
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

    def test_can_fetch_hidden_gates(self):
        result = self.editable_route.get_hidden_gates()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["properties"]["name"], "HG1")

    def test_can_fetch_unknown_leg_waypoints(self):
        result = self.editable_route.get_unknown_leg_waypoints()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["properties"]["name"], "UL1")

    def test_can_fetch_observation_photos(self):
        result = self.editable_route.get_observation_photos()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["properties"]["name"], "Photo 1")

    def test_get_hidden_gates_also_matches_ordinary_secret_points(self):
        """Canonicalization: get_hidden_gates() must treat an ordinary secret backbone point the
        same as the legacy hidden_gate pointType/featureType, since going forward CIMA hidden gates
        are authored as plain secret points."""
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


class TestEditableRouteHiddenGateNormalization(TestCase):
    """A legacy pointType: 'hidden_gate' backbone waypoint must normalize to the canonical secret
    point type when a real Route/Waypoint list is built, including when it's a standalone
    featureType: 'hidden_gate' marker with no authored width (see EditableRoute._create_waypoint_list)."""

    def setUp(self):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")

    def _build_route(self, hidden_gate_props: dict) -> "Route":
        editable_route = EditableRoute.objects.create(
            name="Legacy hidden_gate normalization",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1], [11.2, 60.2]]},
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
                        "properties": hidden_gate_props,
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
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
                            "sequence": 2,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                ],
            },
        )
        return editable_route.create_precision_route(use_procedure_turns=False, scorecard=self.scorecard)

    def test_hidden_gate_point_type_normalizes_to_secret(self):
        route = self._build_route(
            {
                "id": "hg-1",
                "name": "HG1",
                "pointType": "hidden_gate",
                "featureType": "route_waypoint",
                "width": 1852,
                "isTiming": False,
                "isPassing": True,
                "sequence": 1,
            }
        )
        self.assertIsNotNone(route)
        middle = route.waypoints[1]
        self.assertEqual(middle.name, "HG1")
        self.assertEqual(middle.type, SECRETPOINT)
        # Resolves against the ordinary secret GateScore with no separate hidden_gate row required.
        self.scorecard.get_gate_scorecard(middle.type)

    def test_standalone_hidden_gate_marker_without_width_gets_default_corridor_width(self):
        route = self._build_route(
            {
                "id": "hg-1",
                "name": "HG1",
                "pointType": "tp",
                "featureType": "hidden_gate",
            }
        )
        self.assertIsNotNone(route)
        middle = route.waypoints[1]
        self.assertEqual(middle.name, "HG1")
        self.assertAlmostEqual(middle.width, 0.5)
