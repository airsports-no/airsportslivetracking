import json

from django.test import TestCase

from display.convert_flightcontest_gpx import create_track_from_gpx
from display.serialisers import WaypointSerialiser, TrackSerialiser


class TestGPX(TestCase):
    def test_importing(self):
        with open("display/tests/flightcontest_curved_export.gpx", "r") as i:
            track = create_track_from_gpx("test_track", i)
            self.assertEqual("TP11", track.waypoints[53].name)
            self.assertTrue(track.waypoints[53].is_procedure_turn)

    def test_waypoint_serialiseing(self):
        with open("display/tests/flightcontest_curved_export.gpx", "r") as i:
            track = create_track_from_gpx("test_track", i)
            serialiser = WaypointSerialiser(track.waypoints, many=True)
            print(json.dumps(serialiser.data, sort_keys=True, indent=2))

    def test_track_serialiseing(self):
        with open("display/tests/flightcontest_curved_export.gpx", "r") as i:
            track = create_track_from_gpx("test_track", i)
            track_serialiser = TrackSerialiser(track)
            print(json.dumps(track_serialiser.data, sort_keys=True, indent=2))
