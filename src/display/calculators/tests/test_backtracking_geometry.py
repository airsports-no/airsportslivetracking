"""Unit tests of the geometry of FAI Section 10, 4.24.5 (display.calculators.backtracking_geometry): where backtracking
counts is inside the corridor of the active leg and outside the turn point radius. Pure geometry in metres, no database.
"""

import math
import unittest

from display.calculators.backtracking_geometry import (
    CorridorVertex,
    active_leg,
    backtracking_counts_here,
    build_corridor_legs,
    is_inside_corridor,
    is_inside_turn_point_radius,
    turn_point_radius,
)

HALF_WIDTH = 926.0  # a gate one nautical mile wide


def vertex(x, y, half_width=HALF_WIDTH, name=""):
    return CorridorVertex(x, y, half_width, name)


class TurnPointRadiusTest(unittest.TestCase):
    def test_a_straight_line_has_the_half_width_as_its_radius(self):
        self.assertAlmostEqual(turn_point_radius(HALF_WIDTH, 180.0), HALF_WIDTH)

    def test_a_right_angle_turn_reaches_the_outer_corner_of_the_two_corridors(self):
        # The corridors |y| <= w and |x| <= w meet in a square whose outer corner is w x sqrt(2) from the centre
        self.assertAlmostEqual(turn_point_radius(HALF_WIDTH, 90.0), HALF_WIDTH * math.sqrt(2))

    def test_a_sharper_turn_has_a_larger_radius(self):
        radii = [turn_point_radius(HALF_WIDTH, angle) for angle in (180.0, 135.0, 90.0, 45.0)]
        self.assertEqual(radii, sorted(radii))
        self.assertLess(radii[0], radii[-1])

    def test_a_turn_back_on_itself_is_limited(self):
        self.assertAlmostEqual(turn_point_radius(HALF_WIDTH, 0.0), 10 * HALF_WIDTH)


class CorridorLegsTest(unittest.TestCase):
    def setUp(self):
        # SP(0, 0) -> TP1(6000, 0) -> TP2(6000, 5000) (a right turn at TP1 of 90 degrees) -> FP(12000, 5000)
        self.vertices = [
            vertex(0, 0, name="SP"),
            vertex(6000, 0, name="TP1"),
            vertex(6000, 5000, name="TP2"),
            vertex(12000, 5000, name="FP"),
        ]
        self.legs = build_corridor_legs(self.vertices)

    def test_one_leg_between_each_pair_of_vertices(self):
        self.assertEqual(
            [(leg.start.name, leg.end.name) for leg in self.legs], [("SP", "TP1"), ("TP1", "TP2"), ("TP2", "FP")]
        )

    def test_the_ends_of_the_route_have_the_half_width_as_radius_and_the_turns_have_the_outer_corner(self):
        first, second, third = self.legs
        self.assertAlmostEqual(first.start_radius_m, HALF_WIDTH)
        self.assertAlmostEqual(first.end_radius_m, HALF_WIDTH * math.sqrt(2))
        self.assertAlmostEqual(second.start_radius_m, HALF_WIDTH * math.sqrt(2))
        self.assertAlmostEqual(third.end_radius_m, HALF_WIDTH)

    def test_the_corridor_is_as_wide_as_the_gate_the_leg_leaves(self):
        vertices = [vertex(0, 0, 500.0), vertex(6000, 0, 200.0), vertex(12000, 0, 200.0)]
        first, second = build_corridor_legs(vertices)
        self.assertEqual((first.half_width_m, second.half_width_m), (500.0, 200.0))
        # the turn point (here a straight line) takes the wider of the two corridors
        self.assertAlmostEqual(first.end_radius_m, 500.0)

    def test_inside_the_corridor(self):
        leg = self.legs[0]
        self.assertTrue(is_inside_corridor(3000, 0, leg))
        self.assertTrue(is_inside_corridor(3000, HALF_WIDTH - 1, leg))
        self.assertFalse(is_inside_corridor(3000, HALF_WIDTH + 1, leg))
        self.assertFalse(is_inside_corridor(3000, -HALF_WIDTH - 1, leg))

    def test_the_corridor_is_a_strip_around_the_leg_and_rounded_at_its_ends(self):
        leg = self.legs[0]
        self.assertTrue(is_inside_corridor(-HALF_WIDTH + 1, 0, leg))
        self.assertFalse(is_inside_corridor(-HALF_WIDTH - 1, 0, leg))

    def test_the_turn_point_radius_of_either_end_of_the_leg(self):
        leg = self.legs[0]
        self.assertTrue(is_inside_turn_point_radius(HALF_WIDTH - 1, 0, leg))  # near SP
        self.assertFalse(is_inside_turn_point_radius(HALF_WIDTH + 1, 0, leg))
        radius = HALF_WIDTH * math.sqrt(2)
        self.assertTrue(is_inside_turn_point_radius(6000 - radius + 1, 0, leg))  # near TP1
        self.assertFalse(is_inside_turn_point_radius(6000 - radius - 1, 0, leg))

    def test_backtracking_counts_in_the_corridor_outside_the_turn_point_radius(self):
        leg = self.legs[0]
        self.assertTrue(backtracking_counts_here(3000, 0, leg))
        self.assertTrue(backtracking_counts_here(3000, HALF_WIDTH - 1, leg))

    def test_backtracking_does_not_count_outside_the_corridor(self):
        self.assertFalse(backtracking_counts_here(3000, HALF_WIDTH + 1, self.legs[0]))

    def test_backtracking_does_not_count_within_the_turn_point_radius(self):
        leg = self.legs[0]
        self.assertFalse(backtracking_counts_here(200, 0, leg))
        self.assertFalse(backtracking_counts_here(6000, 100, leg))
        # inside the outer corner of the turn at TP1, though beyond one half-width from the leg
        self.assertFalse(backtracking_counts_here(6000 + 600, -600, self.legs[1]))

    def test_the_active_leg_is_the_nearest_from_the_first_leg_given(self):
        self.assertIs(active_leg(3000, 100, self.legs), self.legs[0])
        self.assertIs(active_leg(6100, 2500, self.legs), self.legs[1])
        self.assertIs(active_leg(9000, 5100, self.legs), self.legs[2])
        # a leg before the first one allowed is not an option, even if it is nearer
        self.assertIs(active_leg(3000, 100, self.legs, first_leg_index=1), self.legs[1])

    def test_no_legs_no_active_leg(self):
        self.assertIsNone(active_leg(0, 0, []))
