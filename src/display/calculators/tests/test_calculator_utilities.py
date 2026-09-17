from collections import deque
from types import SimpleNamespace
from unittest import TestCase

from display.calculators.calculator_utilities import project_position, travel_bearing_from_track, PolygonHelper


def _pos(lat, lon):
    return SimpleNamespace(latitude=lat, longitude=lon)


class TestTravelBearingFromTrack(TestCase):
    """
    Regression tests for issue #801: a naive bearing_between(track[-2], track[-1]) is
    unreliable when those two positions are near-duplicates (e.g. a retried/duplicate position
    report, or GPS noise) - the direction of a displacement of only a metre or two is dominated
    by positional noise, not the aircraft's real heading. travel_bearing_from_track walks back
    for a pair separated by a real baseline instead.

    Tracks are built as collections.deque, not list: the live orchestrator's own track
    (Orchestrator.track) is a bounded deque, which supports negative indexing but NOT slicing -
    an earlier version of this function used a slice and passed every list-based test here
    while raising TypeError against any real, deque-backed track in production.
    """

    def test_returns_none_for_a_track_shorter_than_two_positions(self):
        self.assertIsNone(travel_bearing_from_track(deque([_pos(60.0, 11.0)])))
        self.assertIsNone(travel_bearing_from_track(deque()))

    def test_normal_well_separated_positions_use_the_immediate_pair(self):
        # ~1.1km apart (0.01 degrees longitude at 60N) - well above the noise floor, so the
        # immediate pair is used directly, same as the old naive calculation would.
        track = deque([_pos(60.0, 11.00), _pos(60.0, 11.01)])
        bearing = travel_bearing_from_track(track)
        self.assertAlmostEqual(bearing, 90.0, delta=1.0)

    def test_near_duplicate_final_position_is_skipped_in_favour_of_a_real_baseline(self):
        # Production incident (issue #801, contestant 3489/Yago): the final position is a
        # near-duplicate of the one before it (~1m away - below the noise floor), which alone
        # would produce an essentially random bearing. Walking back one more step finds a pair
        # ~1.1km apart on the same real heading (~90 degrees/due east).
        track = deque(
            [
                _pos(60.0, 11.00),
                _pos(60.0, 11.01),
                _pos(60.00000001, 11.0100001),  # near-duplicate of the position above
            ]
        )
        bearing = travel_bearing_from_track(track)
        self.assertAlmostEqual(bearing, 90.0, delta=1.0)

    def test_returns_none_when_the_entire_lookback_window_is_too_tightly_bunched(self):
        # Every position in the window is within a metre or two of the last one (e.g. the
        # aircraft is genuinely stationary/holding) - no reliable bearing can be determined.
        track = deque([_pos(60.0 + i * 0.0000001, 11.0 + i * 0.0000001) for i in range(5)])
        self.assertIsNone(travel_bearing_from_track(track, maximum_lookback=5))

    def test_respects_the_lookback_bound(self):
        # track[0] is a real, well-separated baseline, but it's followed by a run of
        # tightly-bunched positions (e.g. the aircraft briefly stopped moving). With an
        # unbounded lookback it would still be found; a small maximum_lookback must exclude it
        # rather than scanning the whole track history.
        track = deque([_pos(60.0, 11.00)] + [_pos(60.0 + i * 0.0000001, 11.01 + i * 0.0000001) for i in range(4)])
        self.assertIsNotNone(travel_bearing_from_track(track, maximum_lookback=10))
        self.assertIsNone(travel_bearing_from_track(track, maximum_lookback=2))


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
        from display.utilities.coordinate_utilities import Projector

        projector = Projector(60, 11)
        helper = PolygonHelper(projector)
        polygon = helper.build_polygon([(11, 60), (12, 60), (12, 61), (11, 61)])

        # Mandatory projected coordinates
        p = projector.project_point(59.999, 11.5)

        intersection_times = helper.time_to_intersection(
            [("test", polygon)], 0, 6, 0, 600, projected_x=p.projected_x, projected_y=p.projected_y
        )
        print(intersection_times)
        self.assertEqual({"test": 72}, intersection_times)
