from collections import deque
from types import SimpleNamespace
from unittest import TestCase

from display.calculators.positions_and_gates import Gate


def _pos(lat, lon):
    return SimpleNamespace(latitude=lat, longitude=lon)


def _make_gate(gate_heading: float) -> Gate:
    # Bypasses Gate.__init__ (which needs a full Waypoint) - is_passed_in_correct_direction_track
    # and its helper only ever read self.gate_heading.
    gate = Gate.__new__(Gate)
    gate.gate_heading = gate_heading
    return gate


class TestGateDirectionFromTrack(TestCase):
    """
    Regression tests for issue #801: is_passed_in_correct_direction_track used to compute a
    naive bearing_between(track[-2], track[-1]) - unreliable when those two positions are
    near-duplicates, which could wrongly accept or reject a genuine gate crossing. It now goes
    through travel_bearing_from_track, which walks back for a real baseline.

    Tracks are built as collections.deque, not list: the live orchestrator's own track
    (Orchestrator.track) is a bounded deque, which supports negative indexing but NOT slicing.
    """

    def test_insufficient_track_is_not_confirmed(self):
        gate = _make_gate(gate_heading=90.0)
        self.assertFalse(gate.is_passed_in_correct_direction_track(deque([_pos(60.0, 11.0)])))
        self.assertFalse(gate.is_passed_in_correct_direction_track(deque()))

    def test_normal_well_separated_track_confirms_correct_direction(self):
        gate = _make_gate(gate_heading=90.0)  # expects an eastward crossing
        track = deque([_pos(60.0, 11.00), _pos(60.0, 11.01)])
        self.assertTrue(gate.is_passed_in_correct_direction_track(track))

    def test_normal_well_separated_track_rejects_wrong_direction(self):
        gate = _make_gate(gate_heading=90.0)  # expects an eastward crossing
        track = deque([_pos(60.0, 11.01), _pos(60.0, 11.00)])  # travelling west
        self.assertFalse(gate.is_passed_in_correct_direction_track(track))

    def test_near_duplicate_final_position_does_not_flip_the_direction_verdict(self):
        # The final position is a near-duplicate of the one before it (~1m away) whose own
        # point-to-point bearing would be unreliable. Walking back to the real point[0]->point[1]
        # baseline (~1.1km, genuinely eastward) preserves the correct "passed eastward" verdict.
        gate = _make_gate(gate_heading=90.0)
        track = deque(
            [
                _pos(60.0, 11.00),
                _pos(60.0, 11.01),
                _pos(60.0, 11.0100001),
            ]
        )
        self.assertTrue(gate.is_passed_in_correct_direction_track(track))

    def test_entirely_bunched_track_is_not_confirmed(self):
        # No pair in the track is separated by a real baseline (e.g. the aircraft is
        # essentially stationary right at the gate) - direction can't be reliably determined.
        gate = _make_gate(gate_heading=90.0)
        track = deque([_pos(60.0, 11.00), _pos(60.0000001, 11.0000001)])
        self.assertFalse(gate.is_passed_in_correct_direction_track(track))
