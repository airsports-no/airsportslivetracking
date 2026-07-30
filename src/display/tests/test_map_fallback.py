from django.utils import timezone
import unittest
from unittest.mock import patch
import requests
from display.flight_order_and_maps.map_plotter import LocalMapServer, plot_route
from display.utilities.route_building_utilities import build_waypoint
from display.models import NavigationTask, Route, Contest
from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from django.test import TestCase

class MapFallbackTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.contest = Contest.objects.create(
            name="Test Contest",
            start_time=now,
            finish_time=now + timezone.timedelta(days=1)
        )
        self.route = Route.objects.create(name="Test Route")
        self.task = NavigationTask.objects.create(
            name="Test Task",
            route=self.route,
            contest=self.contest,
            original_scorecard=get_default_scorecard(),
            start_time=now,
            finish_time=now + timezone.timedelta(days=1)
        )

    @patch('display.flight_order_and_maps.map_plotter.get_map_details')
    def test_local_map_server_raises_on_unavailable(self, mock_get_details):
        mock_get_details.return_value = {}
        with self.assertRaises(requests.RequestException):
            LocalMapServer("nonexistent_map")

    @patch('display.flight_order_and_maps.map_plotter.LocalMapServer')
    @patch('display.flight_order_and_maps.map_plotter.OSM')
    def test_plot_route_falls_back_to_osm(self, mock_osm, mock_local_server):
        # LocalMapServer fails to initialize
        mock_local_server.side_effect = requests.RequestException("Server down")
        
        # We need to mock the imagery object returned by OSM
        from unittest.mock import MagicMock
        mock_osm_instance = MagicMock()
        mock_osm.return_value = mock_osm_instance
        
        # Mock other dependencies for plot_route to get far enough
        from display.flight_order_and_maps.map_constants import A4
        with patch('display.flight_order_and_maps.map_plotter.plt.figure'), \
             patch('display.flight_order_and_maps.map_plotter.ccrs.PlateCarree'), \
             patch('display.utilities.coordinate_utilities.calculate_bounding_box', return_value=(0,1,0,1)):
            
            try:
                plot_route(self.task, A4, map_source="some_map")
            except Exception:
                # We expect some failure downstream because we didn't mock everything,
                # but we want to check if OSM was instantiated as fallback.
                pass
                
        mock_osm.assert_called()

    @patch('display.flight_order_and_maps.map_plotter.plot_catalogue_targets')
    @patch('display.flight_order_and_maps.map_plotter.get_task_catalogue_targets', return_value=[{"name": "A", "coordinates": [11.0, 60.0]}])
    @patch('display.flight_order_and_maps.map_plotter.get_effective_route_waypoints', return_value=[])
    @patch('display.flight_order_and_maps.map_plotter.plot_prohibited_zones')
    @patch('display.flight_order_and_maps.map_plotter.plot_precision_track', return_value=[])
    @patch('display.flight_order_and_maps.map_plotter.scale_bar_y')
    @patch('display.flight_order_and_maps.map_plotter.utm_from_lat_lon')
    @patch('display.flight_order_and_maps.map_plotter.OSM')
    @patch('display.flight_order_and_maps.map_plotter.plt')
    @patch('display.flight_order_and_maps.map_plotter.ccrs')
    def test_plot_route_adds_catalogue_targets_for_generic_task_map(
        self,
        mock_ccrs,
        mock_plt,
        mock_osm,
        mock_utm,
        _mock_scale_bar,
        mock_plot_precision_track,
        _mock_plot_prohibited,
        mock_get_effective_waypoints,
        mock_get_catalogue_targets,
        mock_plot_catalogue_targets,
    ):
        from unittest.mock import MagicMock
        from display.flight_order_and_maps.map_constants import A4

        mock_osm_instance = MagicMock()
        mock_osm.return_value = mock_osm_instance
        mock_ax = MagicMock()
        mock_fig = MagicMock()
        mock_fig.patch = MagicMock()
        mock_plt.figure.return_value = mock_fig
        mock_fig.add_axes.return_value = mock_ax
        mock_ccrs.PlateCarree.return_value = MagicMock()
        mock_ax.get_extent.return_value = (10.0, 11.0, 60.0, 61.0)
        mock_utm_instance = MagicMock()
        mock_utm_instance.transform_point.side_effect = [(0, 0), (1000, 1000), (10.0, 60.0), (11.0, 61.0)]
        mock_utm.return_value = mock_utm_instance

        try:
            plot_route(self.task, A4, scale=0)
        except Exception:
            pass

        mock_get_effective_waypoints.assert_called_once()
        mock_get_catalogue_targets.assert_called_once_with(self.task)
        mock_plot_catalogue_targets.assert_called_once()
        self.assertEqual(mock_plot_precision_track.call_args.kwargs["render_waypoints"], [])

    def test_plot_leg_bearing_skips_zero_length_leg(self):
        from display.flight_order_and_maps.map_plotter import plot_leg_bearing

        start = build_waypoint("A", 60.0, 11.0, "tp", 1.0, False, True)
        finish = build_waypoint("B", 60.0, 11.0, "tp", 1.0, False, True)
        start.bearing_next = 90
        start.gate_line = [(60.0, 11.0), (60.0, 11.0)]
        start.original_gate_line = start.gate_line
        finish.gate_line = [(60.0, 11.0), (60.0, 11.0)]
        finish.original_gate_line = finish.gate_line

        with patch('display.flight_order_and_maps.map_plotter.plt.text') as mock_text:
            plot_leg_bearing(start, finish, 80, 0, 0)

        mock_text.assert_not_called()

    def test_waypoint_centre_track_segments_use_procedure_turn_points(self):
        from display.waypoint import Waypoint

        waypoint = Waypoint("PT")
        waypoint.latitude = 60.0
        waypoint.longitude = 11.0
        waypoint.is_procedure_turn = True
        waypoint.bearing_from_previous = 0
        waypoint.bearing_next = 90

        segments = waypoint.get_centre_track_segments()

        self.assertGreater(len(segments), 1)
        self.assertTrue(any(point != segments[0] for point in segments[1:]))
