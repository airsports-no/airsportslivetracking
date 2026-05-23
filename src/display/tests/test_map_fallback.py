from django.utils import timezone
import unittest
from unittest.mock import patch
import requests
from display.flight_order_and_maps.map_plotter import LocalMapServer, plot_route
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
