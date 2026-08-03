from django.utils import timezone
import unittest
from unittest.mock import patch
import requests
from display.flight_order_and_maps.map_plotter import LocalMapServer, plot_route, get_plot_extent
from display.utilities.route_building_utilities import build_waypoint
from display.models import NavigationTask, Route, Contest, EditableRoute
from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from django.test import TestCase
from display.models import Photo
from display.services.photo_management import get_navigation_task_photo_targets, revert_photo_to_satellite


class PhotoManagementPageTargetsTest(TestCase):
    def test_turnpoint_hunt_photo_targets_include_backbone_and_catalogue_turnpoints(self):
        now = timezone.now()
        contest = Contest.objects.create(
            name="Photo target contest",
            start_time=now,
            finish_time=now + timezone.timedelta(days=1),
            time_zone="Europe/Oslo",
        )
        route = Route.objects.create(name="Photo target route")
        task = NavigationTask.objects.create(
            name="Photo target task",
            route=route,
            contest=contest,
            original_scorecard=get_default_scorecard(),
            start_time=now,
            finish_time=now + timezone.timedelta(days=1),
            task_subtype="turnpoint_hunt",
        )
        editable_route = EditableRoute.objects.create(
            name="Photo target primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1], [11.2, 60.2]]}},
                    {"type": "Feature", "properties": {"id": "wp-sp", "name": "SP", "pointType": "sp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 0}, "geometry": {"type": "Point", "coordinates": [11.0, 60.0]}},
                    {"type": "Feature", "properties": {"id": "wp-mp", "name": "MP", "pointType": "tp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 1}, "geometry": {"type": "Point", "coordinates": [11.1, 60.1]}},
                    {"type": "Feature", "properties": {"id": "wp-fp", "name": "FP", "pointType": "fp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 2}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "cat-1", "name": "TP 1", "pointType": "tp", "featureType": "catalogue_turnpoint"}, "geometry": {"type": "Point", "coordinates": [11.25, 60.25]}},
                ],
            },
        )
        task.editable_route = editable_route
        task.save(update_fields=["editable_route"])

        targets = get_navigation_task_photo_targets(task)

        self.assertEqual(
            [(item["name"], item["target_kind"]) for item in targets],
            [
                ("SP", "route_waypoint"),
                ("MP", "route_waypoint"),
                ("FP", "route_waypoint"),
                ("TP 1", "catalogue_turnpoint"),
            ],
        )

    def test_revert_photo_to_satellite_regenerates_generated_image(self):
        route = Route.objects.create(name="Generated photo route")
        photo = Photo.objects.create(name="SP", route=route, latitude=60.0, longitude=11.0)

        class DummyFile:
            def __init__(self):
                self.deleted = False

            def delete(self, save=False):
                self.deleted = True

        dummy_file = DummyFile()
        photo.file = dummy_file  # type: ignore[assignment]

        with patch.object(photo, "save") as mock_save, patch.object(photo, "generate_image") as mock_generate, patch.object(photo, "refresh_from_db") as mock_refresh:
            reverted = revert_photo_to_satellite(photo)

        self.assertIs(reverted, photo)
        self.assertTrue(dummy_file.deleted)
        self.assertFalse(bool(photo.file))
        mock_save.assert_called_once_with(update_fields=["file"])
        mock_generate.assert_called_once_with(force=True)
        mock_refresh.assert_called_once_with()

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
    @patch('display.flight_order_and_maps.map_plotter.get_task_catalogue_targets', return_value=[{"name": "A", "coordinates": [11.0, 60.0], "kind": "catalogue_turnpoint"}])
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

    def test_get_task_catalogue_targets_includes_circle_markers(self):
        from display.flight_order_and_maps.effective_route_rendering import get_task_catalogue_targets
        from display.utilities.cima_task_type_definitions import CIRCLE
        from display.models import EditableRoute

        editable_route = EditableRoute.objects.create(
            name="Circle target source",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "cm-1", "name": "CM", "pointType": "circle_center", "featureType": "circle_center_marker"},
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "cs-1", "name": "SP-C", "pointType": "circle_start", "featureType": "circle_start_marker"},
                        "geometry": {"type": "Point", "coordinates": [11.21, 60.21]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "ce-1", "name": "IN", "pointType": "circle_entry", "featureType": "circle_entry_marker"},
                        "geometry": {"type": "Point", "coordinates": [11.22, 60.22]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "cx-1", "name": "OUT", "pointType": "circle_exit", "featureType": "circle_exit_marker"},
                        "geometry": {"type": "Point", "coordinates": [11.23, 60.23]},
                    },
                ],
            },
        )
        self.task.editable_route = editable_route
        self.task.task_subtype = CIRCLE
        self.task.save(update_fields=["editable_route", "task_subtype"])

        targets = get_task_catalogue_targets(self.task)

        self.assertEqual(
            targets,
            [
                {"name": "CM", "coordinates": [11.2, 60.2], "kind": "circle_center_marker"},
                {"name": "SP-C", "coordinates": [11.21, 60.21], "kind": "circle_start_marker"},
                {"name": "IN", "coordinates": [11.22, 60.22], "kind": "circle_entry_marker"},
                {"name": "OUT", "coordinates": [11.23, 60.23], "kind": "circle_exit_marker"},
            ],
        )

    def test_get_plot_extent_uses_rendered_waypoints_and_catalogue_targets(self):
        from unittest.mock import MagicMock

        route = MagicMock()
        route.waypoints = []
        route.prohibited_set.all.return_value = []
        route.get_extent.return_value = (60.0, 60.0, 11.0, 11.0)
        visible = build_waypoint("SP", 60.0, 11.0, "tp", 1.0, True, True)
        visible.gate_line = [(59.99, 10.99), (60.01, 11.01)]
        declared = build_waypoint("A", 60.6, 11.6, "tp", 1.0, False, True)
        declared.gate_line = [(60.59, 11.59), (60.61, 11.61)]

        extent = get_plot_extent(
            route,
            render_waypoints=[visible, declared],
            task_catalogue_targets=[{"name": "CAT", "coordinates": [12.0, 61.0], "kind": "catalogue_turnpoint"}],
        )

        self.assertEqual(extent, (59.99, 61.0, 10.99, 12.0))

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

    def test_waypoint_centre_track_segments_keep_procedure_turn_as_single_point(self):
        from display.waypoint import Waypoint

        waypoint = Waypoint("PT")
        waypoint.latitude = 60.0
        waypoint.longitude = 11.0
        waypoint.is_procedure_turn = True
        waypoint.bearing_from_previous = 0
        waypoint.bearing_next = 90

        segments = waypoint.get_centre_track_segments()

        self.assertEqual(segments, [(60.0, 11.0)])
        self.assertGreater(len(waypoint.procedure_turn_points), 1)
