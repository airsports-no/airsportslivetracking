"""A hidden gate on a curved leg of an editable route: the route editor saves it as a secret waypoint that ends a curved
segment, between two curved segments that together are the old curve (see curve_with_hidden_gates_route_geojson)."""

import math

from django.test import TestCase

from display.calculators.tests.flight_simulator import curve_with_hidden_gates_route_geojson
from display.models import EditableRoute, Scorecard
from display.utilities.task_types import PRECISION

# SP, HG1, HG2, TP1 (the two gates on the curve of the first leg), TP2, FP
CURVE_PARAMETERS = (0.3, 0.7)


def local_metres(latitude: float, longitude: float, origin_latitude: float = 60.0) -> tuple[float, float]:
    return longitude * 111320.0 * math.cos(math.radians(origin_latitude)), latitude * 110540.0


class HiddenGateOnCurvedLegRouteTest(TestCase):
    def setUp(self):
        from display.default_scorecards.create_scorecards import create_scorecards

        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="CIMA Precision")
        self.geojson = curve_with_hidden_gates_route_geojson(CURVE_PARAMETERS, hidden_timing=True)
        self.editable_route = EditableRoute.objects.create(name="Gates on a curve", route=self.geojson)

    def properties(self, name: str) -> dict:
        return next(item["properties"] for item in self.geojson["features"] if item["properties"].get("name") == name)

    def check_waypoints(self, waypoints):
        names = [waypoint.name for waypoint in waypoints]
        self.assertEqual(len(names), len(set(names)), "waypoint names collide")
        by_name = {waypoint.name: waypoint for waypoint in waypoints}
        real = [name for name in names if not name.startswith("Curve ")]
        self.assertEqual(real, ["SP", "HG1", "HG2", "TP1", "TP2", "FP"])

        # 19 generated points before each of the gates and the turn point that end a curved segment, in order
        for gate, before in (("HG1", "Curve 1."), ("HG2", "Curve 2."), ("TP1", "Curve 3.")):
            index = names.index(gate)
            self.assertEqual(names[index - 19 : index], [f"{before}{number}" for number in range(1, 20)])
        for name in names:
            if name.startswith("Curve "):
                curve_point = by_name[name]
                self.assertTrue(curve_point.on_curved_segment)
                self.assertFalse(curve_point.time_check)
                self.assertFalse(curve_point.gate_check)
                self.assertEqual(curve_point.type, "secret")

        for gate in ("HG1", "HG2"):
            hidden = by_name[gate]
            self.assertEqual(hidden.type, "secret")
            self.assertFalse(hidden.on_curved_segment)
            self.assertTrue(hidden.end_curved)
            self.assertTrue(hidden.time_check, f"{gate} is not timed")
            self.assertTrue(hidden.gate_check, f"{gate} is not checked")
            properties = self.properties(gate)
            self.assertEqual(
                (hidden.control_latitude, hidden.control_longitude),
                (properties["controlLat"], properties["controlLng"]),
            )
        # The turn point after them still ends a curved segment, with the second half of the curve
        self.assertTrue(by_name["TP1"].end_curved)
        self.assertEqual(
            (by_name["TP1"].control_latitude, by_name["TP1"].control_longitude),
            (self.properties("TP1")["controlLat"], self.properties("TP1")["controlLng"]),
        )
        return by_name

    def test_the_generic_waypoint_builder_makes_the_curve_points_before_and_after_each_gate(self):
        self.check_waypoints(self.editable_route._create_waypoint_list())
        self.check_waypoints(self.editable_route._create_waypoint_list(precision_mode=True))

    def test_the_precision_route_has_the_gates_between_the_curve_points(self):
        route = self.editable_route.create_precision_route(self.scorecard.use_procedure_turns, self.scorecard)
        self.check_waypoints(route.waypoints)
        route = self.editable_route.create_route(PRECISION, self.scorecard, None, None)
        self.check_waypoints(route.waypoints)

    def test_the_gate_line_of_a_hidden_gate_on_the_curve_is_square_to_the_curve(self):
        route = self.editable_route.create_precision_route(self.scorecard.use_procedure_turns, self.scorecard)
        by_name = {waypoint.name: waypoint for waypoint in route.waypoints}
        for gate, next_name in (("HG1", "HG2"), ("HG2", "TP1")):
            waypoint = by_name[gate]
            # The direction of the curve at the gate is from the control point before it to the one after it
            first = self.properties(gate)
            second = self.properties(next_name)
            tangent = (
                local_metres(second["controlLat"], second["controlLng"])[0]
                - local_metres(first["controlLat"], first["controlLng"])[0],
                local_metres(second["controlLat"], second["controlLng"])[1]
                - local_metres(first["controlLat"], first["controlLng"])[1],
            )
            (lat_a, lon_a), (lat_b, lon_b) = waypoint.gate_line
            line = (
                local_metres(lat_b, lon_b)[0] - local_metres(lat_a, lon_a)[0],
                local_metres(lat_b, lon_b)[1] - local_metres(lat_a, lon_a)[1],
            )
            cosine = (tangent[0] * line[0] + tangent[1] * line[1]) / (math.hypot(*tangent) * math.hypot(*line))
            angle_from_square = abs(90.0 - math.degrees(math.acos(max(-1.0, min(1.0, cosine)))))
            self.assertLess(
                angle_from_square, 3.0, f"{gate}: the gate line is {angle_from_square:.1f} degrees off square"
            )
            self.assertAlmostEqual(math.hypot(*line), waypoint.width * 1852, delta=waypoint.width * 1852 * 0.01)
