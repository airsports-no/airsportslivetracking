import json

from django.test import TestCase

from display.convert_flightcontest_gpx import create_route_from_gpx
from display.serialisers import WaypointSerialiser, RouteSerialiser


class TestGPX(TestCase):
    def test_importing(self):
        with open("display/tests/flightcontest_curved_export.gpx", "r") as i:
            route = create_route_from_gpx(i)
            self.assertEqual("TP11", route.waypoints[53].name)
            self.assertTrue(route.waypoints[53].is_procedure_turn)

    def test_waypoint_serialiseing(self):
        with open("display/tests/flightcontest_curved_export.gpx", "r") as i:
            route = create_route_from_gpx(i)
            serialiser = WaypointSerialiser(route.waypoints, many=True)
            print(json.dumps(serialiser.data, sort_keys=True, indent=2))

    def test_route_serialiseing(self):
        with open("display/tests/flightcontest_curved_export.gpx", "r") as i:
            route = create_route_from_gpx(i)
            route_serialiser = RouteSerialiser(route)
            print(json.dumps(route_serialiser.data, sort_keys=True, indent=2))
