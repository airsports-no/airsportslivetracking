from django.test import TestCase

from display.convert_flightcontest_gpx import load_route_points_from_kml


class TestLoadRoutePointsFromKml(TestCase):
    def test_loading(self):
        with open("display/tests/test.kml", "r") as i:
            points = load_route_points_from_kml(i)
            print(points)
            self.assertListEqual([(60.39210026366186, 11.26190470147315), (60.33103186190058, 11.2715576258351),
                                  (60.32711037657219, 11.23462887156482), (60.38786590201709, 11.22294508482837),
                                  (60.40113552445987, 11.24451196077489)], points)
