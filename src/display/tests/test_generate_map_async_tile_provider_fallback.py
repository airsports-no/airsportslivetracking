"""
generate_map_async previously let a MapTileRenderingDegradedError (raised by
check_tile_fetch_health when too many of a rendered map's tiles came back blank due to fetch
failures/rate limiting - e.g. Sentry PYTHON-DJANGO-P/Q/R, a sustained outage on the external
CyclOSM tile server) propagate straight to the async job's "error" status, leaving the user with
no map at all until the external provider recovered.

It now retries the same render once with the "osm" fallback provider (a different backend
entirely) when the originally-requested map source degrades, and surfaces an unobtrusive warning
in the job's result so the user knows a fallback style was used instead of silently swapping it.
"""

import datetime
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Contest, NavigationTask, Route
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestGenerateMapAsyncTileProviderFallback(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        now = datetime.datetime.now(datetime.timezone.utc)
        self.contest = Contest.objects.create(
            name="Fallback Contest",
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
            location="60, 11",
        )
        route = Route.objects.create(name="Fallback Route")
        self.navigation_task = NavigationTask.create(
            name="Fallback Task",
            original_scorecard=get_default_scorecard(),
            route=route,
            contest=self.contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
        )
        self.user = self._make_user()
        self.map_params = {
            "size": "A4",
            "zoom_level": 12,
            "landscape": True,
            "annotations": True,
            "waypoints_only": False,
            "dpi": 150,
            "scale": 200,
            "map_source": "cyclosm",
            "line_width": 0.5,
            "minute_mark_line_width": 0.5,
            "colour": "#0000ff",
            "include_meridians_and_parallels_lines": True,
            "include_openaip_overlay": False,
            "margin": 10,
        }

    def _make_user(self):
        from django.contrib.auth import get_user_model

        return get_user_model().objects.create(email="fallback-test@example.com")

    def _run(self):
        from display.tasks import generate_map_async

        cache_key = f"map_gen_result_{self.navigation_task.pk}_None_{self.user.pk}"
        cache.delete(cache_key)
        generate_map_async(self.navigation_task.pk, None, self.map_params, self.user.pk)
        return cache.get(cache_key)

    @patch("display.flight_order_and_maps.generate_flight_orders.embed_map_in_pdf", return_value=b"%PDF-fake")
    @patch("display.flight_order_and_maps.map_plotter.plot_route")
    def test_degraded_primary_provider_falls_back_to_osm_with_warning(self, mock_plot_route, mock_embed_pdf, *args):
        from display.flight_order_and_maps.map_plotter import MapTileRenderingDegradedError

        fake_image = MagicMock()
        fake_image.read.return_value = b"fake-image-bytes"
        mock_plot_route.side_effect = [
            MapTileRenderingDegradedError("21/24 map tiles (88%) came back blank"),
            fake_image,
        ]

        with (
            patch("django.core.files.storage.default_storage.save", return_value="generated_maps/1/fake.pdf"),
            patch("django.core.files.storage.default_storage.url", return_value="/media/generated_maps/1/fake.pdf"),
        ):
            result = self._run()

        self.assertEqual(mock_plot_route.call_count, 2)
        first_call_kwargs = mock_plot_route.call_args_list[0].kwargs
        second_call_kwargs = mock_plot_route.call_args_list[1].kwargs
        self.assertEqual(first_call_kwargs["map_source"], "cyclosm")
        self.assertEqual(second_call_kwargs["map_source"], "osm")

        self.assertEqual(result["status"], "complete")
        self.assertIn("warning", result)
        self.assertIn("fallback", result["warning"].lower())

    @patch("display.flight_order_and_maps.map_plotter.plot_route")
    def test_degraded_osm_fallback_itself_does_not_retry_again(self, mock_plot_route, *args):
        from display.flight_order_and_maps.map_plotter import MapTileRenderingDegradedError

        self.map_params["map_source"] = "osm"
        mock_plot_route.side_effect = MapTileRenderingDegradedError("48/48 map tiles (100%) came back blank")

        result = self._run()

        mock_plot_route.assert_called_once()
        self.assertEqual(mock_plot_route.call_args.kwargs["map_source"], "osm")
        self.assertEqual(result["status"], "error")
