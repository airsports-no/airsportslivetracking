"""Regression test for flight-order maps silently degrading to (mostly) blank tiles.

Every tile-fetch failure mode in map_plotter.py (rate limiting, request errors, the
_background_fetch_aborted short-circuit after repeated rate limiting) returns a blank
placeholder tile instead of propagating the failure. Nothing checked those failures
after rendering, so a map that came back e.g. 400/410 blank tiles was still returned
as a normal PDF - stored, marked completed, and emailed to the contestant as their
competition navigation map with no diagnostic anywhere.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.flight_order_and_maps.map_plotter import (
    AirsportsOSM,
    BLANK_TILE_ABORT_FRACTION,
    MapTileRenderingDegradedError,
    TILE_RATE_LIMIT_ABORT_THRESHOLD,
    check_tile_fetch_health,
)
from display.models import Contest, NavigationTask, Route


class TestCheckTileFetchHealth(TestCase):
    def test_raises_when_blank_fraction_exceeds_threshold(self):
        imagery = SimpleNamespace(_tile_fetch_count=410, _blank_tile_count=400)
        with self.assertRaises(MapTileRenderingDegradedError):
            check_tile_fetch_health(imagery)

    def test_does_not_raise_for_a_few_transient_blanks(self):
        # Below BLANK_TILE_ABORT_FRACTION - occasional single-tile blips shouldn't
        # fail an otherwise-good map.
        blank = int(100 * BLANK_TILE_ABORT_FRACTION) - 1
        imagery = SimpleNamespace(_tile_fetch_count=100, _blank_tile_count=blank)
        check_tile_fetch_health(imagery)  # must not raise

    def test_does_not_raise_when_imagery_has_no_tracking_attributes(self):
        # e.g. UserUploadedMBTiles, which isn't instrumented (its blank tiles mean
        # "no tile at this coordinate in the uploaded file", not a fetch failure).
        check_tile_fetch_health(object())  # must not raise

    def test_real_imagery_instance_accumulates_blank_count_across_rate_limited_fetches(self):
        imagery = AirsportsOSM(user_agent="airsports.no, support@airsports.no")
        response = MagicMock()
        response.status_code = 429
        response.content = b""

        with patch("display.flight_order_and_maps.map_plotter.requests.get", return_value=response):
            for index in range(TILE_RATE_LIMIT_ABORT_THRESHOLD + 1):
                imagery.get_image((index % 2, 0, 1))

        self.assertEqual(imagery._tile_fetch_count, TILE_RATE_LIMIT_ABORT_THRESHOLD + 1)
        self.assertEqual(imagery._blank_tile_count, TILE_RATE_LIMIT_ABORT_THRESHOLD + 1)
        with self.assertRaises(MapTileRenderingDegradedError):
            check_tile_fetch_health(imagery)


class TestPlotRouteRejectsDegradedMap(TestCase):
    def setUp(self):
        now = timezone.now()
        self.contest = Contest.objects.create(
            name="Tile health contest",
            start_time=now,
            finish_time=now + timezone.timedelta(days=1),
        )
        self.route = Route.objects.create(name="Tile health route")
        self.task = NavigationTask.objects.create(
            name="Tile health task",
            route=self.route,
            contest=self.contest,
            original_scorecard=get_default_scorecard(),
            start_time=now,
            finish_time=now + timezone.timedelta(days=1),
        )

    @patch("display.flight_order_and_maps.map_plotter.plot_catalogue_targets")
    @patch(
        "display.flight_order_and_maps.map_plotter.get_task_catalogue_targets",
        return_value=[{"name": "SP", "coordinates": [11.0, 60.0], "kind": "catalogue_turnpoint"}],
    )
    @patch("display.flight_order_and_maps.map_plotter.get_effective_route_waypoints", return_value=[])
    @patch("display.flight_order_and_maps.map_plotter.plot_prohibited_zones")
    @patch("display.flight_order_and_maps.map_plotter.plot_precision_track", return_value=[])
    @patch("display.flight_order_and_maps.map_plotter.scale_bar_y")
    @patch("display.flight_order_and_maps.map_plotter.utm_from_lat_lon")
    @patch("display.flight_order_and_maps.map_plotter.AirsportsOSM")
    @patch("display.flight_order_and_maps.map_plotter.plt")
    @patch("display.flight_order_and_maps.map_plotter.ccrs")
    def test_plot_route_raises_instead_of_returning_a_mostly_blank_map(
        self,
        mock_ccrs,
        mock_plt,
        mock_airsports_osm,
        mock_utm,
        _mock_scale_bar,
        mock_plot_precision_track,
        _mock_plot_prohibited,
        _mock_get_effective_waypoints,
        _mock_get_catalogue_targets,
        _mock_plot_catalogue_targets,
    ):
        from display.flight_order_and_maps.map_constants import A4
        from display.flight_order_and_maps.map_plotter import plot_route

        # A fully-rendered imagery source whose tile fetches were 400/410 blank -
        # exactly the scenario described in the finding.
        mock_osm_instance = MagicMock()
        mock_osm_instance._tile_fetch_count = 410
        mock_osm_instance._blank_tile_count = 400
        mock_airsports_osm.return_value = mock_osm_instance
        mock_ax = MagicMock()
        mock_fig = MagicMock()
        mock_fig.patch = MagicMock()
        mock_plt.figure.return_value = mock_fig
        mock_fig.add_axes.return_value = mock_ax
        mock_ccrs.PlateCarree.return_value = MagicMock()
        mock_ccrs.PlateCarree.return_value.transform_point.return_value = (11.0, 60.0)
        mock_ax.get_extent.return_value = (10.0, 11.0, 60.0, 61.0)
        mock_utm_instance = MagicMock()
        mock_utm_instance.transform_point.side_effect = [(0, 0), (1000, 1000), (10.0, 60.0), (11.0, 61.0)]
        mock_utm.return_value = mock_utm_instance

        with self.assertRaises(MapTileRenderingDegradedError):
            plot_route(self.task, A4, scale=0)
