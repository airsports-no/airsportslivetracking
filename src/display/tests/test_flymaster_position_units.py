"""Positions from a Flymaster file are stored in the same units as every other source: metres and knots."""

from unittest.mock import patch

from django.test import SimpleTestCase

from display.flymaster_position_builder import build_positions_from_flymaster

FILE = "ABC123,x\n0,1750000000,60.0,11.0,455.0,92.6,180\n0,1750000001,60.0,11.0,460.0,92.6,180\n\n"


class TestFlymasterPositionUnits(SimpleTestCase):
    @patch("display.models.contestant.Contestant.get_contestant_for_device_at_time", return_value=[])
    def test_altitude_stays_in_metres_and_speed_becomes_knots(self, _):
        _, identifier, positions = build_positions_from_flymaster(FILE)
        self.assertEqual("ABC123", identifier)
        self.assertEqual(455.0, positions[0]["altitude"])
        self.assertAlmostEqual(50.0, positions[0]["speed"], places=3)
