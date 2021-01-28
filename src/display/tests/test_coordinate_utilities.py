from unittest import TestCase
from parameterized import parameterized

from display.coordinate_utilities import calculate_bearing, get_heading_difference, extend_line, \
    fraction_of_leg, Projector, get_procedure_turn_track, create_bisecting_line_between_segments, \
    create_bisecting_line_between_segments_corridor_width_lonlat, \
    create_bisecting_line_between_segments_corridor_width_xy


class TestCoordinateUtilities(TestCase):
    @parameterized.expand([
        ((60, 11), (62, 11), 0),
        ((60, 11), (58, 11), 180),
        ((60, 11), (60, 12), 89.5669845501348),
        ((60, 11), (60, 10), 270.4330154498652)
    ])
    def test_calculate_bearing(self, start, finish, expected_bearing):
        bearing = calculate_bearing(start, finish)
        self.assertEqual(expected_bearing, bearing)

    @parameterized.expand([
        (60, 90, 30),
        (90, 60, -30),
        (350, 10, 20),
        (10, 350, -20)
    ])
    def test_heading_difference(self, first_heading, second_heading, expected_difference):
        difference = get_heading_difference(first_heading, second_heading)
        self.assertEqual(expected_difference, difference)

    @parameterized.expand([
        ((60, 10), (61, 10), 120, (59, 10), (62, 10))
    ])
    def test_extend_line(self, original_start, original_finish, distance, expected_start, expected_finish):
        actual_start, actual_finish = extend_line(original_start, original_finish, distance)
        self.assertAlmostEqual(expected_start[0], actual_start[0], 2)
        self.assertAlmostEqual(expected_start[1], actual_start[1], 2)
        self.assertAlmostEqual(expected_finish[0], actual_finish[0], 2)
        self.assertAlmostEqual(expected_finish[1], actual_finish[1], 2)

    def test_pyproj_line_intersect(self):
        projector = Projector(60, 11)
        intersection = projector.intersect((60, 11), (62, 11), (61, 10), (61, 12))
        print(intersection)
        self.assertAlmostEqual(intersection[0], 61.0036, 3)
        self.assertAlmostEqual(intersection[1], 11)

    @parameterized.expand([
        ((60, 10), (60, 12), (60, 11), 0.5, "horizontal"),
        ((60, 10), (62, 10), (61, 10), 0.5, "vertical")
    ])
    def test_fraction_of_leg(self, start, finish, intersect, expected_fraction, direction):
        fraction = fraction_of_leg(start, finish, intersect)
        self.assertAlmostEqual(expected_fraction, fraction, 4, msg=direction)

    @parameterized.expand([
        (60, 11, 61, 12, 60, 13, 4000,
         [[61.02520768017186, 11.999976690645374], [60.97479231982813, 12.000023309350894]]),
        (0, 0, 1, 1, 0, 2, 100000, [[1.63726937165459, 0.999950488100371], [0.36273062834540976, 1.0000495118720374]]),
        (-1, 0, 0, 1, 1, 0, 100000, [[0.0, 1.6371766699682373], [0.0, 0.36269796585943964]])
    ])
    def test_create_bisecting_line_between_segments(self, x1, y1, x2, y2, x3, y3, length, expected):
        gate_line = create_bisecting_line_between_segments(x1, y1, x2, y2, x3, y3, length)
        self.assertListEqual(expected, gate_line)

    @parameterized.expand([
        (11, 60, 12, 61, 13, 60, 4000, [[12.0, 61.01971740758599], [12.0, 60.98027030481011]]),
        # (60, 11, 61, 12, 60, 13, 4000, [[61.03537209933487, 11.999967291682234], [60.96462790066512, 12.000032708312075]]),
        (0, 0, 1, 1, 2, 0, 100000,
         [[0.9999999999999998, 1.637190822291303], [0.9999999999999998, 0.36268380796690464]]),
        # (0, 0, 1, 1, 0, 2, 100000,  [[1.9041833503535694, 0.9999297505358952], [0.09581664964643055, 1.0000702494357498]]),
        (0, -1, 1, 0, 0, 1, 100000, [[0.36266760209343246, 0.0], [1.6373323979065675, 0.0]])
        # (-1, 0, 0, 1, 1, 0, 100000, [[0.0, 1.8980610511265397], [0.0, 0.10168989378111135]])
    ])
    def test_create_bisecting_line_between_segments_corridor_width(self, x1, y1, x2, y2, x3, y3, length, expected):
        gate_line = create_bisecting_line_between_segments_corridor_width_lonlat(x1, y1, x2, y2, x3, y3, length)
        self.assertListEqual(expected, gate_line)

    @parameterized.expand([
        (0, 0, 1, 1, 2, 0, 1, [[1.0, 1.7071067811865475], [1.0, 0.2928932188134524]]),
        (0, 0, 0, 1, 0, 2.01, 1, [[-0.5, 1.0], [0.5, 1.0]])
    ])
    def test_create_bisecting_line_between_segments_corridor_width_xy(self, x1, y1, x2, y2, x3, y3, length, expected):
        gate_line = create_bisecting_line_between_segments_corridor_width_xy(x1, y1, x2, y2, x3, y3, length)
        self.assertListEqual(expected, gate_line)


class TestProcedureTurnPoints(TestCase):
    def test_simple(self):
        points = get_procedure_turn_track(60, 11, 270, 30, 0.05)
        print(points)
