from unittest import TestCase

from display.calculators.calculator_utilities import project_position, PolygonHelper


class TestProjectPosition(TestCase):
    def test_project_circle(self):
        destination = project_position(60, 11, 0, 1, 600, 360)
        self.assertAlmostEqual(60, destination[0])
        self.assertAlmostEqual(11, destination[1])

    def test_project_half_circle_half_rate(self):
        destination = project_position(60, 11, 0, 0.5, 600, 360)
        print(destination)
        self.assertAlmostEqual(59.364521086097525, destination[0], 4)
        self.assertAlmostEqual(11, destination[1], 4)

    def test_project_half_circle_half_time(self):
        destination = project_position(60, 11, 0, 1, 1200, 180)
        print(destination)
        self.assertAlmostEqual(59.364521086097525, destination[0], 4)
        self.assertAlmostEqual(11, destination[1], 4)

    def test_project_almost_straight(self):
        destination = project_position(60, 11, 0, 0.0001, 60, 3600)
        self.assertAlmostEqual(60.9981859828, destination[0])
        self.assertAlmostEqual(11.012935383763349, destination[1])

    def test_project_straight(self):
        destination = project_position(60, 11, 0, 0, 60, 3600)
        self.assertAlmostEqual(60.9982012, destination[0], 4)
        self.assertAlmostEqual(10.99999999, destination[1], 4)


class TestPolygonHelper(TestCase):
    def test_time_to_intersection(self):
        helper = PolygonHelper(60, 11)
        polygon = helper.build_polygon([(60, 11), (60, 12), (61, 12), (61, 11)])
        intersection_times = helper.time_to_intersection([("test", polygon)], 59.999, 11.5, 0, 6000, 0, 600)
        print(intersection_times)
        self.assertEqual({'test': 130}, intersection_times)
