from django.utils import timezone
import unittest
from unittest.mock import patch, MagicMock
import requests
from urllib.error import HTTPError
from display.flight_order_and_maps.map_plotter import AirsportsOSM, LocalMapServer, plot_route, get_plot_extent, plot_catalogue_targets, TILE_RATE_LIMIT_ABORT_THRESHOLD
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
    def test_plot_route_falls_back_to_osm(self, mock_local_server):
        # LocalMapServer fails to initialize
        mock_local_server.side_effect = requests.RequestException("Server down")

        # Mock other dependencies for plot_route to get far enough
        from display.flight_order_and_maps.map_constants import A4
        with patch('display.flight_order_and_maps.map_plotter.AirsportsOSM') as mock_airsports_osm, \
             patch('display.flight_order_and_maps.map_plotter.plt.figure'), \
             patch('display.flight_order_and_maps.map_plotter.ccrs.PlateCarree'), \
             patch('display.utilities.coordinate_utilities.calculate_bounding_box', return_value=(0,1,0,1)):

            mock_airsports_osm.return_value = MagicMock()
            try:
                plot_route(self.task, A4, map_source="some_map")
            except Exception:
                # We expect some failure downstream because we didn't mock everything,
                # but we want to check if OSM fallback imagery was instantiated.
                pass

        mock_airsports_osm.assert_called()

    def test_airsports_osm_abandons_background_after_repeated_429s(self):
        imagery = AirsportsOSM(user_agent="airsports.no, support@airsports.no")

        response = MagicMock()
        response.status_code = 429
        response.content = b""

        with patch('display.flight_order_and_maps.map_plotter.requests.get', return_value=response):
            for index in range(TILE_RATE_LIMIT_ABORT_THRESHOLD + 1):
                tile_x = index % 2
                img, _, _ = imagery.get_image((tile_x, 0, 1))
                self.assertEqual(img.size, (256, 256))

        self.assertTrue(imagery._background_fetch_aborted)
        self.assertEqual(imagery._tile_rate_limit_errors, TILE_RATE_LIMIT_ABORT_THRESHOLD + 1)

        with patch('display.flight_order_and_maps.map_plotter.requests.get') as mock_requests_get:
            imagery.get_image((1, 0, 1))
        mock_requests_get.assert_not_called()

    def test_flight_contest_abandons_background_after_repeated_429s(self):
        from display.flight_order_and_maps.map_plotter import FlightContest

        imagery = FlightContest(desired_tile_form="RGBA")
        rate_limited = HTTPError('https://example.invalid/tile.png', 429, 'Too Many Requests', hdrs=MagicMock(), fp=None)

        with patch('urllib.request.urlopen', side_effect=rate_limited):
            for index in range(TILE_RATE_LIMIT_ABORT_THRESHOLD + 1):
                tile_x = index % 2
                img, _, _ = imagery.get_image((tile_x, 0, 1))
                self.assertEqual(img.size, (256, 256))

        self.assertTrue(imagery._background_fetch_aborted)
        self.assertEqual(imagery._tile_rate_limit_errors, TILE_RATE_LIMIT_ABORT_THRESHOLD + 1)

        with patch('urllib.request.urlopen') as mock_urlopen:
            imagery.get_image((1, 0, 1))
        mock_urlopen.assert_not_called()

    @patch('display.flight_order_and_maps.map_plotter.plot_catalogue_targets')
    @patch('display.flight_order_and_maps.map_plotter.get_task_catalogue_targets', return_value=[{"name": "A", "coordinates": [11.0, 60.0], "kind": "catalogue_turnpoint"}])
    @patch('display.flight_order_and_maps.map_plotter.get_effective_route_waypoints', return_value=[])
    @patch('display.flight_order_and_maps.map_plotter.plot_prohibited_zones')
    @patch('display.flight_order_and_maps.map_plotter.plot_precision_track', return_value=[])
    @patch('display.flight_order_and_maps.map_plotter.scale_bar_y')
    @patch('display.flight_order_and_maps.map_plotter.utm_from_lat_lon')
    @patch('display.flight_order_and_maps.map_plotter.AirsportsOSM')
    @patch('display.flight_order_and_maps.map_plotter.plt')
    @patch('display.flight_order_and_maps.map_plotter.ccrs')
    def test_plot_route_adds_catalogue_targets_for_generic_task_map(
        self,
        mock_ccrs,
        mock_plt,
        mock_airsports_osm,
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
        mock_airsports_osm.return_value = mock_osm_instance
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

    @patch('display.flight_order_and_maps.map_plotter.plot_catalogue_targets')
    @patch('display.flight_order_and_maps.map_plotter.get_task_catalogue_targets', return_value=[{"name": "A", "coordinates": [11.0, 60.0], "kind": "catalogue_turnpoint"}])
    @patch('display.flight_order_and_maps.map_plotter.get_effective_route_waypoints', return_value=[])
    @patch('display.flight_order_and_maps.map_plotter.plot_prohibited_zones')
    @patch('display.flight_order_and_maps.map_plotter.plot_precision_track', return_value=[])
    @patch('display.flight_order_and_maps.map_plotter.scale_bar_y')
    @patch('display.flight_order_and_maps.map_plotter.utm_from_lat_lon')
    @patch('display.flight_order_and_maps.map_plotter.AirsportsOSM')
    @patch('display.flight_order_and_maps.map_plotter.plt')
    @patch('display.flight_order_and_maps.map_plotter.ccrs')
    def test_plot_route_contract_navigation_generic_map_hides_catalogue_and_lines(
        self,
        mock_ccrs,
        mock_plt,
        mock_airsports_osm,
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
        from display.utilities.cima_task_type_definitions import CONTRACT_NAVIGATION_TIME_CONTROLS

        self.task.task_subtype = CONTRACT_NAVIGATION_TIME_CONTROLS
        self.task.save(update_fields=["task_subtype"])

        mock_osm_instance = MagicMock()
        mock_airsports_osm.return_value = mock_osm_instance
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
            # contestant=None: the GENERAL map for 2.A3 must show only the
            # backbone (no freeway/catalogue points, no connecting lines).
            plot_route(self.task, A4, scale=0)
        except Exception:
            pass

        mock_get_catalogue_targets.assert_not_called()
        mock_plot_catalogue_targets.assert_called_once_with([], "#0000ff", self.task.scorecard)
        # waypoints_only is forced True (3rd positional arg) so no connecting
        # line is drawn, and use_circle_markers is True for CIMA tasks.
        self.assertTrue(mock_plot_precision_track.call_args.args[2])
        self.assertTrue(mock_plot_precision_track.call_args.kwargs["use_circle_markers"])

    @patch('display.flight_order_and_maps.map_plotter.plot_catalogue_targets')
    @patch('display.flight_order_and_maps.map_plotter.get_task_catalogue_targets')
    @patch('display.flight_order_and_maps.map_plotter.get_effective_route_waypoints', return_value=[])
    @patch('display.flight_order_and_maps.map_plotter.plot_prohibited_zones')
    @patch('display.flight_order_and_maps.map_plotter.plot_precision_track', return_value=[])
    @patch('display.flight_order_and_maps.map_plotter.scale_bar_y')
    @patch('display.flight_order_and_maps.map_plotter.utm_from_lat_lon')
    @patch('display.flight_order_and_maps.map_plotter.AirsportsOSM')
    @patch('display.flight_order_and_maps.map_plotter.plt')
    @patch('display.flight_order_and_maps.map_plotter.ccrs')
    def test_plot_route_renders_unknown_leg_navigation_segments_for_generic_map(
        self,
        mock_ccrs,
        mock_plt,
        mock_airsports_osm,
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
        from display.utilities.cima_task_type_definitions import UNKNOWN_LEGS

        self.task.task_subtype = UNKNOWN_LEGS
        self.task.save(update_fields=["task_subtype"])
        mock_get_catalogue_targets.return_value = [
            {"name": "SP", "coordinates": [11.0, 60.0], "kind": "catalogue_turnpoint", "segment_name": "segment_1"},
            {"name": "TRG1", "coordinates": [11.2, 60.2], "kind": "catalogue_turnpoint", "segment_name": "segment_1"},
            {"name": "TRG1-D1", "coordinates": [11.3, 60.3], "kind": "catalogue_turnpoint", "segment_name": "segment_1"},
            {"name": "B", "coordinates": [11.4, 60.4], "kind": "catalogue_turnpoint", "segment_name": "segment_2"},
            {"name": "FP", "coordinates": [11.5, 60.5], "kind": "catalogue_turnpoint", "segment_name": "segment_2"},
        ]

        mock_osm_instance = MagicMock()
        mock_airsports_osm.return_value = mock_osm_instance
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

        plot_calls = mock_plt.plot.call_args_list
        segment_calls = [call for call in plot_calls if call.kwargs.get('linestyle') == (0, (8, 6))]
        self.assertEqual(len(segment_calls), 2)
        self.assertEqual(tuple(segment_calls[0].args[0]), (11.0, 11.2, 11.3))
        self.assertEqual(tuple(segment_calls[0].args[1]), (60.0, 60.2, 60.3))
        self.assertEqual(tuple(segment_calls[1].args[0]), (11.4, 11.5))
        self.assertEqual(tuple(segment_calls[1].args[1]), (60.4, 60.5))
        mock_plot_catalogue_targets.assert_called_once()

    @patch('display.flight_order_and_maps.map_plotter.plot_catalogue_targets')
    @patch('display.flight_order_and_maps.map_plotter.get_task_catalogue_targets')
    @patch('display.flight_order_and_maps.map_plotter.get_effective_route_waypoints', return_value=[])
    @patch('display.flight_order_and_maps.map_plotter.plot_prohibited_zones')
    @patch('display.flight_order_and_maps.map_plotter.plot_precision_track', return_value=[])
    @patch('display.flight_order_and_maps.map_plotter.scale_bar_y')
    @patch('display.flight_order_and_maps.map_plotter.utm_from_lat_lon')
    @patch('display.flight_order_and_maps.map_plotter.AirsportsOSM')
    @patch('display.flight_order_and_maps.map_plotter.plt')
    @patch('display.flight_order_and_maps.map_plotter.ccrs')
    def test_plot_route_renders_unknown_leg_contestant_navigation_segments_as_solid_lines_without_trigger_marker(
        self,
        mock_ccrs,
        mock_plt,
        mock_airsports_osm,
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
        from display.utilities.cima_task_type_definitions import UNKNOWN_LEGS

        self.task.task_subtype = UNKNOWN_LEGS
        self.task.save(update_fields=["task_subtype"])
        contestant = MagicMock()
        contestant.navigation_task = self.task
        mock_get_effective_waypoints.return_value = [MagicMock(name="effective-waypoint")]
        mock_get_catalogue_targets.side_effect = [[], [
            {"name": "SP", "coordinates": [11.0, 60.0], "kind": "catalogue_turnpoint", "segment_name": "segment_1"},
            {"name": "TRG1", "coordinates": [11.2, 60.2], "kind": "catalogue_turnpoint", "segment_name": "segment_1", "is_unknown_leg_trigger": True},
            {"name": "TRG1-D1", "coordinates": [11.3, 60.3], "kind": "catalogue_turnpoint", "segment_name": "segment_1", "trigger_point_id": "TRG1", "branch_sequence": 0},
            {"name": "B", "coordinates": [11.4, 60.4], "kind": "catalogue_turnpoint", "segment_name": "segment_2"},
            {"name": "FP", "coordinates": [11.5, 60.5], "kind": "catalogue_turnpoint", "segment_name": "segment_2"},
        ]]

        mock_osm_instance = MagicMock()
        mock_airsports_osm.return_value = mock_osm_instance
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
            plot_route(self.task, A4, contestant=contestant, scale=0)
        except Exception:
            pass

        mock_plot_precision_track.assert_called_once()
        self.assertEqual(mock_plot_precision_track.call_args.kwargs["render_waypoints"], [])
        solid_segment_calls = [
            call
            for call in mock_plt.plot.call_args_list
            if call.kwargs.get('linestyle') is None and len(call.args) >= 2 and not isinstance(call.args[0], (int, float))
        ]
        self.assertGreaterEqual(len(solid_segment_calls), 2)
        self.assertEqual(tuple(solid_segment_calls[0].args[0]), (11.0, 11.2, 11.3))
        self.assertEqual(tuple(solid_segment_calls[0].args[1]), (60.0, 60.2, 60.3))
        self.assertEqual(tuple(solid_segment_calls[-1].args[0]), (11.4, 11.5))
        self.assertEqual(tuple(solid_segment_calls[-1].args[1]), (60.4, 60.5))
        mock_plot_catalogue_targets.assert_not_called()

    def test_get_task_catalogue_targets_unknown_legs_selected_contestant_includes_visible_segments_and_hidden_overlays(self):
        from types import SimpleNamespace
        from display.flight_order_and_maps.effective_route_rendering import get_task_catalogue_targets
        from display.utilities.cima_task_type_definitions import UNKNOWN_LEGS

        editable_route = EditableRoute.objects.create(
            name="Unknown legs target source",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1], [11.2, 60.2], [11.3, 60.3], [11.4, 60.4]]}},
                    {"type": "Feature", "properties": {"id": "sp-1", "name": "SP", "pointType": "sp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 0}, "geometry": {"type": "Point", "coordinates": [11.0, 60.0]}},
                    {"type": "Feature", "properties": {"id": "a-1", "name": "A", "pointType": "tp", "featureType": "route_waypoint", "width": 1852, "isTiming": False, "isPassing": True, "sequence": 1}, "geometry": {"type": "Point", "coordinates": [11.1, 60.1]}},
                    {"type": "Feature", "properties": {"id": "ul-1", "name": "TRG1", "pointType": "ul", "featureType": "route_waypoint", "width": 1852, "isTiming": False, "isPassing": True, "sequence": 2, "unknownLegHeading": 105}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "b-1", "name": "B", "pointType": "tp", "featureType": "route_waypoint", "width": 1852, "isTiming": False, "isPassing": True, "sequence": 4}, "geometry": {"type": "Point", "coordinates": [11.4, 60.4]}},
                    {"type": "Feature", "properties": {"id": "dummy-1", "name": "TRG1-D1", "pointType": "dummy", "featureType": "dummy_branch_waypoint", "width": 1852, "isTiming": False, "isPassing": True, "triggerPointId": "ul-1", "branchSequence": 0, "sequence": 5}, "geometry": {"type": "Point", "coordinates": [11.3, 60.3]}},
                ],
            },
        )
        self.task.editable_route = editable_route
        self.task.task_subtype = UNKNOWN_LEGS
        self.task.save(update_fields=["editable_route", "task_subtype"])

        contestant = SimpleNamespace(
            contestanttaskconfiguration=SimpleNamespace(
                is_valid=True,
                compiled_effective_route_payload={
                    "segments": [
                        {
                            "name": "segment_1",
                            "display_waypoint_names": ["SP", "A", "TRG1", "TRG1-D1"],
                            "display_coordinates_by_name": {
                                "SP": [11.0, 60.0],
                                "A": [11.1, 60.1],
                                "TRG1": [11.2, 60.2],
                                "TRG1-D1": [11.3, 60.3],
                            },
                            "dummy_branch_waypoints": [
                                {"name": "TRG1-D1", "coordinates": [11.3, 60.3], "trigger_point_id": "TRG1", "branch_sequence": 0}
                            ],
                        }
                    ],
                    "actual_route": {
                        "waypoints": [
                            {"name": "SP", "type": "sp", "coordinates": [11.0, 60.0]},
                            {"name": "A", "type": "tp", "coordinates": [11.1, 60.1]},
                            {"name": "TRG1", "type": "ul", "coordinates": [11.2, 60.2]},
                            {"name": "B", "type": "tp", "coordinates": [11.4, 60.4]},
                        ],
                        "unknown_leg_connectors": [
                            {"from": "TRG1", "to": "B", "from_coordinates": [11.2, 60.2], "to_coordinates": [11.4, 60.4]},
                        ],
                    },
                    "hidden_gates": [{"name": "HG1", "coordinates": [11.22, 60.22]}],
                },
            )
        )

        targets = get_task_catalogue_targets(self.task, contestant=contestant)

        self.assertEqual(
            targets,
            [
                {"name": "SP", "coordinates": [11.0, 60.0], "kind": "catalogue_turnpoint", "segment_name": "segment_1"},
                {"name": "A", "coordinates": [11.1, 60.1], "kind": "catalogue_turnpoint", "segment_name": "segment_1"},
                {"name": "TRG1", "coordinates": [11.2, 60.2], "kind": "catalogue_turnpoint", "segment_name": "segment_1", "is_unknown_leg_trigger": True},
                {"name": "TRG1-D1", "coordinates": [11.3, 60.3], "kind": "catalogue_turnpoint", "segment_name": "segment_1", "trigger_point_id": "TRG1", "branch_sequence": 0},
                {"name": "TRG1", "coordinates": [11.2, 60.2], "kind": "unknown_leg_trigger", "trigger_point_id": "TRG1"},
                {"name": "TRG1→B", "coordinates": [11.4, 60.4], "kind": "unknown_leg_connector_end", "trigger_point_id": "TRG1", "connector_to_name": "B", "segment_name": None},
                {"name": "HG1", "coordinates": [11.22, 60.22], "kind": "hidden_gate"},
            ],
        )

    @patch('display.flight_order_and_maps.map_plotter.plt')
    def test_plot_catalogue_targets_hides_unknown_leg_trigger_markers_on_visible_navigation_map(self, mock_plt):
        from display.flight_order_and_maps.map_plotter import plot_catalogue_targets

        plot_catalogue_targets(
            [
                {"name": "SP", "coordinates": [11.0, 60.0], "kind": "catalogue_turnpoint", "segment_name": "segment_1"},
                {"name": "TRG1", "coordinates": [11.2, 60.2], "kind": "catalogue_turnpoint", "segment_name": "segment_1", "is_unknown_leg_trigger": True},
                {"name": "TRG1-D1", "coordinates": [11.3, 60.3], "kind": "catalogue_turnpoint", "segment_name": "segment_1", "trigger_point_id": "TRG1", "branch_sequence": 0},
                {"name": "TRG1", "coordinates": [11.2, 60.2], "kind": "unknown_leg_trigger", "trigger_point_id": "TRG1"},
                {"name": "TRG1→B", "coordinates": [11.4, 60.4], "kind": "unknown_leg_connector_end", "trigger_point_id": "TRG1", "connector_to_name": "B", "segment_name": None},
                {"name": "HG1", "coordinates": [11.22, 60.22], "kind": "hidden_gate"},
            ],
            "#0000ff",
        )

        plotted_points = [call.args[:2] for call in mock_plt.plot.call_args_list if len(call.args) >= 2 and isinstance(call.args[0], (int, float))]
        labelled_names = [call.args[2].strip() for call in mock_plt.text.call_args_list if len(call.args) >= 3]

        self.assertIn((11.0, 60.0), plotted_points)
        self.assertIn((11.3, 60.3), plotted_points)
        self.assertNotIn((11.2, 60.2), plotted_points)
        self.assertIn("SP", labelled_names)
        self.assertIn("TRG1-D1", labelled_names)
        self.assertNotIn("TRG1", labelled_names)

    @patch('display.flight_order_and_maps.map_plotter.plot_catalogue_targets')
    @patch('display.flight_order_and_maps.map_plotter.get_task_catalogue_targets')
    @patch('display.flight_order_and_maps.map_plotter.get_effective_route_waypoints')
    @patch('display.flight_order_and_maps.map_plotter.plot_prohibited_zones')
    @patch('display.flight_order_and_maps.map_plotter.plot_precision_track', return_value=[])
    @patch('display.flight_order_and_maps.map_plotter.scale_bar_y')
    @patch('display.flight_order_and_maps.map_plotter.utm_from_lat_lon')
    @patch('display.flight_order_and_maps.map_plotter.AirsportsOSM')
    @patch('display.flight_order_and_maps.map_plotter.plt')
    @patch('display.flight_order_and_maps.map_plotter.ccrs')
    def test_plot_route_unknown_legs_generic_map_uses_segment_order_without_backbone_route(
        self,
        mock_ccrs,
        mock_plt,
        mock_airsports_osm,
        mock_utm,
        _mock_scale_bar,
        mock_plot_precision_track,
        _mock_plot_prohibited,
        mock_get_effective_waypoints,
        mock_get_catalogue_targets,
        _mock_plot_catalogue_targets,
    ):
        from unittest.mock import MagicMock
        from display.flight_order_and_maps.map_constants import A4
        from display.utilities.cima_task_type_definitions import UNKNOWN_LEGS

        self.task.task_subtype = UNKNOWN_LEGS
        self.task.save(update_fields=["task_subtype"])
        mock_get_effective_waypoints.return_value = [MagicMock(name="legacy-waypoint")]
        mock_get_catalogue_targets.return_value = [
            {"name": "SP", "coordinates": [11.0, 60.0], "kind": "catalogue_turnpoint", "segment_name": "segment_1"},
            {"name": "TRG9", "coordinates": [11.2, 60.2], "kind": "catalogue_turnpoint", "segment_name": "segment_1", "is_unknown_leg_trigger": True},
            {"name": "AAA", "coordinates": [11.3, 60.3], "kind": "catalogue_turnpoint", "segment_name": "segment_1", "trigger_point_id": "TRG9", "branch_sequence": 0},
        ]

        mock_osm_instance = MagicMock()
        mock_airsports_osm.return_value = mock_osm_instance
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

        mock_plot_precision_track.assert_called_once()
        self.assertEqual(mock_plot_precision_track.call_args.kwargs["render_waypoints"], [])
        segment_calls = [
            call
            for call in mock_plt.plot.call_args_list
            if call.kwargs.get('linestyle') == (0, (8, 6))
        ]
        self.assertEqual(len(segment_calls), 1)
        self.assertEqual(tuple(segment_calls[0].args[0]), (11.0, 11.2, 11.3))
        self.assertEqual(tuple(segment_calls[0].args[1]), (60.0, 60.2, 60.3))

    def test_get_task_catalogue_targets_unknown_legs_route_backbone_hidden_gates(self):
        from types import SimpleNamespace
        from display.flight_order_and_maps.effective_route_rendering import get_task_catalogue_targets
        from display.utilities.cima_task_type_definitions import UNKNOWN_LEGS

        editable_route = EditableRoute.objects.create(
            name="Unknown legs route-backbone hidden gates",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1], [11.2, 60.2], [11.3, 60.3], [11.4, 60.4]]}},
                    {"type": "Feature", "properties": {"id": "sp-1", "name": "SP", "pointType": "sp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 0}, "geometry": {"type": "Point", "coordinates": [11.0, 60.0]}},
                    {"type": "Feature", "properties": {"id": "hg-1", "name": "HG1", "pointType": "secret", "featureType": "route_waypoint", "width": 1852, "isTiming": False, "isPassing": True, "sequence": 1}, "geometry": {"type": "Point", "coordinates": [11.1, 60.1]}},
                    {"type": "Feature", "properties": {"id": "ul-1", "name": "TRG1", "pointType": "ul", "featureType": "route_waypoint", "width": 1852, "isTiming": False, "isPassing": True, "sequence": 2, "unknownLegHeading": 105}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                    {"type": "Feature", "properties": {"id": "fp-1", "name": "FP", "pointType": "fp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 4}, "geometry": {"type": "Point", "coordinates": [11.4, 60.4]}},
                    {"type": "Feature", "properties": {"id": "dummy-1", "name": "TRG1-D1", "pointType": "dummy", "featureType": "dummy_branch_waypoint", "width": 1852, "isTiming": False, "isPassing": True, "triggerPointId": "ul-1", "branchSequence": 0, "sequence": 5}, "geometry": {"type": "Point", "coordinates": [11.3, 60.3]}},
                ],
            },
        )
        self.task.editable_route = editable_route
        self.task.task_subtype = UNKNOWN_LEGS
        self.task.save(update_fields=["editable_route", "task_subtype"])

        contestant = SimpleNamespace(
            contestanttaskconfiguration=SimpleNamespace(
                is_valid=True,
                compiled_effective_route_payload={
                    "segments": [
                        {
                            "name": "segment_1",
                            "display_waypoint_names": ["SP", "HG1", "TRG1", "TRG1-D1"],
                            "display_coordinates_by_name": {
                                "SP": [11.0, 60.0],
                                "HG1": [11.1, 60.1],
                                "TRG1": [11.2, 60.2],
                                "TRG1-D1": [11.3, 60.3],
                            },
                            "dummy_branch_waypoints": [
                                {"name": "TRG1-D1", "coordinates": [11.3, 60.3], "trigger_point_id": "TRG1", "branch_sequence": 0}
                            ],
                        }
                    ],
                    "actual_route": {
                        "waypoints": [
                            {"name": "SP", "type": "sp", "coordinates": [11.0, 60.0]},
                            {"name": "HG1", "type": "secret", "coordinates": [11.1, 60.1]},
                            {"name": "TRG1", "type": "ul", "coordinates": [11.2, 60.2]},
                            {"name": "FP", "type": "fp", "coordinates": [11.4, 60.4]},
                        ],
                        "unknown_leg_connectors": [
                            {"from": "TRG1", "to": "FP", "from_coordinates": [11.2, 60.2], "to_coordinates": [11.4, 60.4]},
                        ],
                    },
                    "hidden_gates": [{"name": "HG1", "coordinates": [11.1, 60.1]}],
                },
            )
        )

        targets = get_task_catalogue_targets(self.task, contestant=contestant)

        self.assertIn({"name": "HG1", "coordinates": [11.1, 60.1], "kind": "catalogue_turnpoint", "segment_name": "segment_1"}, targets)
        self.assertIn({"name": "HG1", "coordinates": [11.1, 60.1], "kind": "hidden_gate"}, targets)

    def test_unknown_legs_selected_contestant_targets_include_segment_name(self):
        from types import SimpleNamespace
        from display.flight_order_and_maps.effective_route_rendering import get_task_catalogue_targets
        from display.utilities.cima_task_type_definitions import UNKNOWN_LEGS

        editable_route = EditableRoute.objects.create(
            name="Unknown legs segment name source",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1], [11.2, 60.2]]}},
                    {"type": "Feature", "properties": {"id": "sp-1", "name": "SP", "pointType": "sp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 0}, "geometry": {"type": "Point", "coordinates": [11.0, 60.0]}},
                    {"type": "Feature", "properties": {"id": "ul-1", "name": "TRG1", "pointType": "ul", "featureType": "route_waypoint", "width": 1852, "isTiming": False, "isPassing": True, "sequence": 1}, "geometry": {"type": "Point", "coordinates": [11.1, 60.1]}},
                    {"type": "Feature", "properties": {"id": "fp-1", "name": "FP", "pointType": "fp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 2}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                ],
            },
        )
        self.task.editable_route = editable_route
        self.task.task_subtype = UNKNOWN_LEGS
        self.task.save(update_fields=["editable_route", "task_subtype"])

        contestant = SimpleNamespace(
            contestanttaskconfiguration=SimpleNamespace(
                is_valid=True,
                compiled_effective_route_payload={
                    "segments": [
                        {
                            "name": "segment_1",
                            "display_waypoint_names": ["SP", "TRG1", "TRG1-D1"],
                            "display_coordinates_by_name": {
                                "SP": [11.0, 60.0],
                                "TRG1": [11.1, 60.1],
                                "TRG1-D1": [11.15, 60.15],
                            },
                            "dummy_branch_waypoints": [
                                {"name": "TRG1-D1", "coordinates": [11.15, 60.15], "trigger_point_id": "TRG1", "branch_sequence": 0}
                            ],
                        }
                    ],
                    "actual_route": {
                        "waypoints": [
                            {"name": "SP", "type": "sp", "coordinates": [11.0, 60.0]},
                            {"name": "TRG1", "type": "ul", "coordinates": [11.1, 60.1]},
                            {"name": "FP", "type": "fp", "coordinates": [11.2, 60.2]},
                        ],
                        "unknown_leg_connectors": [
                            {"from": "TRG1", "to": "FP", "from_coordinates": [11.1, 60.1], "to_coordinates": [11.2, 60.2]},
                        ],
                    },
                    "hidden_gates": [],
                    "map_rendering_mode": "unknown_legs_split",
                },
            )
        )

        targets = get_task_catalogue_targets(self.task, contestant=contestant)
        self.assertIn({"name": "TRG1-D1", "coordinates": [11.15, 60.15], "kind": "catalogue_turnpoint", "segment_name": "segment_1", "trigger_point_id": "TRG1", "branch_sequence": 0}, targets)

    def test_get_task_catalogue_targets_unknown_legs_uses_task_payload_without_contestant(self):
        from types import SimpleNamespace
        from display.flight_order_and_maps.effective_route_rendering import get_task_catalogue_targets
        from display.utilities.cima_task_type_definitions import UNKNOWN_LEGS

        editable_route = EditableRoute.objects.create(
            name="Unknown legs task payload source",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1], [11.2, 60.2]]}},
                    {"type": "Feature", "properties": {"id": "sp-1", "name": "SP", "pointType": "sp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 0}, "geometry": {"type": "Point", "coordinates": [11.0, 60.0]}},
                    {"type": "Feature", "properties": {"id": "ul-1", "name": "TRG1", "pointType": "ul", "featureType": "route_waypoint", "width": 1852, "isTiming": False, "isPassing": True, "sequence": 1}, "geometry": {"type": "Point", "coordinates": [11.1, 60.1]}},
                    {"type": "Feature", "properties": {"id": "fp-1", "name": "FP", "pointType": "fp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 2}, "geometry": {"type": "Point", "coordinates": [11.2, 60.2]}},
                ],
            },
        )
        self.task.editable_route = editable_route
        self.task.task_subtype = UNKNOWN_LEGS
        self.task.save(update_fields=["editable_route", "task_subtype"])
        from display.models.compiled_navigation_task import CompiledNavigationTask
        CompiledNavigationTask.objects.update_or_create(
            navigation_task=self.task,
            defaults={
                "compiled_payload": {
                    "unknown_legs_segments": [
                        {
                            "name": "segment_1",
                            "display_waypoint_names": ["SP", "TRG1", "TRG1-D1"],
                            "display_coordinates_by_name": {
                                "SP": [11.0, 60.0],
                                "TRG1": [11.1, 60.1],
                                "TRG1-D1": [11.15, 60.15],
                            },
                            "dummy_branch_waypoints": [
                                {"name": "TRG1-D1", "coordinates": [11.15, 60.15], "trigger_point_id": "TRG1", "branch_sequence": 0}
                            ],
                        }
                    ],
                    "unknown_legs_actual_route": {
                        "unknown_leg_connectors": [
                            {"from": "TRG1", "to": "FP", "from_coordinates": [11.1, 60.1], "to_coordinates": [11.2, 60.2]},
                        ],
                    },
                    "unknown_legs_hidden_gates": [{"name": "HG1", "coordinates": [11.12, 60.12]}],
                }
            },
        )

        targets = get_task_catalogue_targets(self.task)

        self.assertIn({"name": "TRG1-D1", "coordinates": [11.15, 60.15], "kind": "catalogue_turnpoint", "segment_name": "segment_1", "trigger_point_id": "TRG1", "branch_sequence": 0}, targets)
        self.assertIn({"name": "TRG1", "coordinates": [11.1, 60.1], "kind": "unknown_leg_trigger", "trigger_point_id": "TRG1"}, targets)
        self.assertIn({"name": "TRG1→FP", "coordinates": [11.2, 60.2], "kind": "unknown_leg_connector_end", "trigger_point_id": "TRG1", "connector_to_name": "FP", "segment_name": None}, targets)
        self.assertIn({"name": "HG1", "coordinates": [11.12, 60.12], "kind": "hidden_gate"}, targets)

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

    @patch('display.flight_order_and_maps.map_plotter.plt')
    @patch('display.flight_order_and_maps.map_plotter.ccrs')
    def test_plot_catalogue_targets_renders_circle_geometry_like_live_map(self, mock_ccrs, mock_plt):
        mock_ccrs.PlateCarree.return_value = MagicMock()

        targets = [
            {"name": "SP", "coordinates": [11.0, 60.0], "kind": "circle_start_marker"},
            {"name": "IN", "coordinates": [11.01, 60.01], "kind": "circle_entry_marker"},
            {"name": "CM", "coordinates": [11.02, 60.02], "kind": "circle_center_marker"},
            {"name": "OUT", "coordinates": [11.03, 60.03], "kind": "circle_exit_marker"},
        ]

        plot_catalogue_targets(
            targets,
            "#0000ff",
            scorecard=MagicMock(circle_radius_min_m=250, circle_radius_max_m=500),
        )

        plot_calls = mock_plt.plot.call_args_list
        circle_calls = [
            call
            for call in plot_calls
            if len(call.args) >= 2 and isinstance(call.args[0], tuple) and len(call.args[0]) > 10 and call.kwargs.get("linestyle") in {(0, (3, 3)), (0, (10, 4))}
        ]
        self.assertEqual(len(circle_calls), 2)
        self.assertEqual(len(circle_calls[0].args[0]), 73)
        self.assertEqual(len(circle_calls[1].args[0]), 73)

        # Regression guard for radius_min/max_m being read from task_config
        # (which never carries them - always the 200/750 defaults) instead of
        # the scorecard: pin the actual measured ring radius against the
        # scorecard's configured 250/500, not the default.
        from display.utilities.coordinate_utilities import calculate_distance_lat_lon

        center = (60.02, 11.02)
        min_ring_lons, min_ring_lats = circle_calls[0].args[0], circle_calls[0].args[1]
        max_ring_lons, max_ring_lats = circle_calls[1].args[0], circle_calls[1].args[1]
        min_ring_radius_m = calculate_distance_lat_lon(center, (min_ring_lats[0], min_ring_lons[0]))
        max_ring_radius_m = calculate_distance_lat_lon(center, (max_ring_lats[0], max_ring_lons[0]))
        self.assertAlmostEqual(min_ring_radius_m, 250, delta=1)
        self.assertAlmostEqual(max_ring_radius_m, 500, delta=1)
        self.assertEqual(circle_calls[0].kwargs["color"], "#0f9d58")
        self.assertEqual(circle_calls[1].kwargs["color"], "#b91c1c")
        self.assertEqual(circle_calls[0].kwargs["linewidth"], 2.4)
        self.assertEqual(circle_calls[1].kwargs["linewidth"], 1.6)
        rendered_segments = {
            tuple((round(arg[0], 5), round(arg[1], 5)) for arg in call.args[:2])
            for call in plot_calls
            if len(call.args) >= 2 and isinstance(call.args[0], tuple) and isinstance(call.args[1], tuple)
        }
        self.assertIn(((11.0, 11.01), (60.0, 60.01)), rendered_segments)
        self.assertIn(((11.01, 11.02), (60.01, 60.02)), rendered_segments)
        self.assertIn(((11.02, 11.03), (60.02, 60.03)), rendered_segments)

    @patch('display.flight_order_and_maps.map_plotter.plt')
    @patch('display.flight_order_and_maps.map_plotter.ccrs')
    def test_plot_catalogue_targets_with_circle_marker_and_no_scorecard_does_not_raise(self, mock_ccrs, mock_plt):
        # Regression test: plot_catalogue_targets defaults scorecard=None (NavigationTask.scorecard
        # is nullable), but CimaScoringConfig.from_scorecard(None) would raise AttributeError -
        # falls back to CimaScoringConfig()'s own defaults (200/750) instead.
        mock_ccrs.PlateCarree.return_value = MagicMock()
        targets = [{"name": "CM", "coordinates": [11.02, 60.02], "kind": "circle_center_marker"}]

        try:
            plot_catalogue_targets(targets, "#0000ff", scorecard=None)
        except AttributeError:
            self.fail("plot_catalogue_targets must not raise when scorecard is None")

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
