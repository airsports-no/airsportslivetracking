"""
Unit tests for ContestantProcessor.fill_in_missing_course.

These tests intentionally bypass the heavy DB-backed setup of the other
ContestantProcessor tests by constructing the processor with ``__new__`` and
exercising the pure-function method directly. The method only reads/writes
attributes on plain ``ContestantReceivedPosition`` instances, so we can use
unsaved model instances.
"""

import datetime
import unittest

from display.calculators.contestant_processor import (
    MIN_DISTANCE_FOR_BEARING_M,
    ContestantProcessor,
)
from display.models.contestant_utility_models import ContestantReceivedPosition


def _make_position(latitude: float, longitude: float, course: float = 0.0) -> ContestantReceivedPosition:
    return ContestantReceivedPosition(
        time=datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc),
        latitude=latitude,
        longitude=longitude,
        course=course,
        speed=0.0,
        altitude=0.0,
    )


class FillInMissingCourseTest(unittest.TestCase):
    """Tests for the heading-from-track fallback."""

    def setUp(self):
        # Bypass __init__ — fill_in_missing_course only operates on its arguments.
        self.processor = ContestantProcessor.__new__(ContestantProcessor)

    def test_no_previous_position_leaves_course_unchanged(self):
        position = _make_position(60.0, 11.0, course=0.0)
        self.processor.fill_in_missing_course(None, position)
        self.assertEqual(position.course, 0.0)

    def test_non_zero_course_is_preserved(self):
        previous = _make_position(60.0, 11.0)
        # Heading already set by the tracker — must not be overwritten even if
        # the bearing from previous to current would suggest something else.
        position = _make_position(60.1, 11.0, course=180.0)
        self.processor.fill_in_missing_course(previous, position)
        self.assertEqual(position.course, 180.0)

    def test_zero_course_short_distance_with_zero_prev_course_stays_at_zero(self):
        # ~0.1 m apart — well below the 5 m threshold. Previous course is also 0,
        # so we have nothing better to fall back to.
        previous = _make_position(60.0, 11.0, course=0.0)
        position = _make_position(60.0 + 1e-6, 11.0, course=0.0)
        self.processor.fill_in_missing_course(previous, position)
        self.assertEqual(position.course, 0.0)

    def test_zero_course_short_distance_inherits_previous_course(self):
        # Near-stationary aircraft (well below the 5 m threshold) should keep
        # the last known heading rather than snapping back to north.
        previous = _make_position(60.0, 11.0, course=137.5)
        position = _make_position(60.0 + 1e-6, 11.0, course=0.0)
        self.processor.fill_in_missing_course(previous, position)
        self.assertEqual(position.course, 137.5)

    def test_zero_course_north_movement_yields_zero_bearing(self):
        # Move ~111 m north — bearing should be close to 0 (north).
        # The result is technically still 0, but we exercise the path.
        previous = _make_position(60.0, 11.0)
        position = _make_position(60.001, 11.0, course=0.0)
        self.processor.fill_in_missing_course(previous, position)
        self.assertAlmostEqual(position.course, 0.0, places=1)

    def test_zero_course_east_movement_yields_ninety_degree_bearing(self):
        previous = _make_position(60.0, 11.0)
        # Roughly 50+ m east at this latitude.
        position = _make_position(60.0, 11.001, course=0.0)
        self.processor.fill_in_missing_course(previous, position)
        self.assertAlmostEqual(position.course, 90.0, places=1)

    def test_zero_course_south_movement_yields_one_eighty_bearing(self):
        previous = _make_position(60.0, 11.0)
        position = _make_position(59.999, 11.0, course=0.0)
        self.processor.fill_in_missing_course(previous, position)
        self.assertAlmostEqual(position.course, 180.0, places=1)

    def test_zero_course_west_movement_yields_two_seventy_bearing(self):
        previous = _make_position(60.0, 11.0)
        position = _make_position(60.0, 10.999, course=0.0)
        self.processor.fill_in_missing_course(previous, position)
        self.assertAlmostEqual(position.course, 270.0, places=1)

    def test_distance_threshold_is_respected(self):
        # Sanity-check the constant is a small, non-trivial value so we don't
        # accidentally drop it to 0 in a future refactor.
        self.assertGreater(MIN_DISTANCE_FOR_BEARING_M, 0.0)
        self.assertLess(MIN_DISTANCE_FOR_BEARING_M, 100.0)


if __name__ == "__main__":
    unittest.main()
