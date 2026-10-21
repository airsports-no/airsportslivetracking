"""Regression test for plot_route()'s pre-render memory safety check drastically underestimating
real peak memory usage, letting dangerous configurations through to OOM-kill tracker-celery pods
(3Gi memory limit) instead of being rejected up front.

Empirically measured against a real production task (task pk=3222, "Entrenament ANR Mar2026":
A3 page, 300 DPI, zoom level 14, scale=0 "zoom to fit", custom single-fixed-zoom uploaded MBTiles
chart, ~792 tiles at zoom 14): the pre-fix estimate was 264MB (66MB final image + 198MB naive
per-tile estimate) - safely under the 750MB MEMORY_THRESHOLD_MB in plot_route() - while the actual
measured peak RSS delta for rendering it was ~3320MB, which OOM-crashed the pod.

Two fixes since address most of the real underlying cost (see map_plotter.py for detail):
- TileDownsamplingMixin shrinks the fetched tile mosaic to the output page's own resolution before
  matplotlib composites it.
- requirements.txt pins matplotlib below 3.10 to avoid an upstream Figure.savefig() memory
  regression for large imshow() images (matplotlib#29434), which turned out to be the dominant
  cost - not our own code.

For this same task, that took the actual measured peak from ~3320MB down to ~1092MB.
TILE_MEMORY_OVERHEAD_MULTIPLIER is calibrated against that post-fix number, since it's what
plot_route() now actually does.

MEMORY_THRESHOLD_MB was later raised from 750 to 1500 after a separate production investigation:
one user was hitting the 750MB threshold 38 times in 26h, always at zoom_level=14 (the form's
max), across routes whose tiles_mb alone ranged ~770-1134MB regardless of DPI or page size - i.e.
the threshold was blocking routine zoom-14 use for any but a small-area task, not just the
originally-profiled worst case. 1500 covers that range (and the original 792-tile/~1092MB
calibration case below, which is now allowed) while keeping ~1.5GB of headroom under
tracker-celery's 3Gi pod memory limit.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from display.flight_order_and_maps.map_plotter import (
    MEMORY_THRESHOLD_MB,
    MINIMUM_FALLBACK_ZOOM_LEVEL,
    MemoryEstimationExceededError,
    plot_route_within_memory_limit,
    estimate_memory_usage,
    highest_zoom_level_within_memory_limit,
    estimate_tile_memory_mb,
    memory_estimation_exceeded_message,
    total_tile_count,
)

# The real production configuration that OOM-crashed a tracker-celery pod.
REAL_WORLD_TOTAL_TILES = 792
REAL_WORLD_FIGURE_WIDTH_CM = 42  # A3 landscape height-as-width
REAL_WORLD_FIGURE_HEIGHT_CM = 29.7
REAL_WORLD_DPI = 300
# Measured peak RSS delta with both the downsampling fix and the matplotlib<3.10 pin applied
# (down from ~3320MB with neither).
REAL_WORLD_MEASURED_PEAK_MB = 1092


class TestTileMemoryEstimation:
    def test_naive_per_tile_estimate_alone_would_not_have_caught_the_real_oom(self):
        # Pins down the original bug: the old "0.25MB per tile" formula (no overhead multiplier)
        # combined with the final image estimate stayed comfortably under the threshold for the
        # exact configuration that went on to OOM-crash the pod in production.
        final_image_mb = estimate_memory_usage(REAL_WORLD_FIGURE_WIDTH_CM, REAL_WORLD_FIGURE_HEIGHT_CM, REAL_WORLD_DPI)
        naive_tiles_mb = REAL_WORLD_TOTAL_TILES * 0.25
        naive_estimated_mb = final_image_mb + naive_tiles_mb

        assert naive_estimated_mb < MEMORY_THRESHOLD_MB
        assert round(naive_estimated_mb) == 264

    def test_calibrated_estimate_is_close_to_the_real_post_fix_measurement(self):
        # With both fixes applied, this configuration's actual peak (~1092MB) is now comfortably
        # under the (later-raised) 1500MB threshold - this specific "zoom to fit" A3/300dpi
        # configuration is allowed today, since it's been measured safe with real headroom to
        # spare under tracker-celery's 3Gi pod limit.
        final_image_mb = estimate_memory_usage(REAL_WORLD_FIGURE_WIDTH_CM, REAL_WORLD_FIGURE_HEIGHT_CM, REAL_WORLD_DPI)
        tiles_mb = estimate_tile_memory_mb(REAL_WORLD_TOTAL_TILES)
        estimated_mb = final_image_mb + tiles_mb

        assert estimated_mb < MEMORY_THRESHOLD_MB
        # Within 10% of the real post-fix measured peak - calibrated, not wildly over- or
        # under-shooting.
        assert abs(estimated_mb - REAL_WORLD_MEASURED_PEAK_MB) / REAL_WORLD_MEASURED_PEAK_MB < 0.10

    def test_tile_memory_estimate_scales_linearly_with_tile_count(self):
        assert estimate_tile_memory_mb(100) * 2 == estimate_tile_memory_mb(200)
        assert estimate_tile_memory_mb(0) == 0

    def test_small_maps_stay_well_under_the_threshold(self):
        # A modest single-zoom-level map (e.g. a normal-sized A4 task) shouldn't be penalised by
        # the overhead multiplier into false-positive rejections.
        final_image_mb = estimate_memory_usage(29.7, 21, 150)
        tiles_mb = estimate_tile_memory_mb(20)
        assert final_image_mb + tiles_mb < MEMORY_THRESHOLD_MB

    def test_zoom_14_at_200_dpi_fits_under_the_raised_threshold_for_the_worst_observed_route(self):
        # Direct regression test for the production complaint that prompted raising the
        # threshold: zoom_level=14 at a normal page size/DPI, for the largest route extent
        # actually observed (1134MB tiles - the worst of the 38 real failures) must now pass.
        final_image_mb = estimate_memory_usage(REAL_WORLD_FIGURE_WIDTH_CM, REAL_WORLD_FIGURE_HEIGHT_CM, dpi=200)
        worst_observed_tiles_mb = 1134
        assert final_image_mb + worst_observed_tiles_mb < MEMORY_THRESHOLD_MB


class TestMemoryEstimationExceededMessage:
    def test_message_names_the_actual_zoom_level(self):
        # Regression test: the pre-fix message said only "reduce the map size, choose a smaller
        # scale, or lower the DPI" - it never mentioned zoom, even though tiles_mb (usually the
        # dominant term) depends only on zoom level and the route's geographic extent, not DPI or
        # page size. Confirmed against real production Sentry data: the same user hit this 38
        # times in 26h, always at zoom_level=14, with DPI/page size varying every time - changing
        # those never would have helped.
        message = memory_estimation_exceeded_message(
            estimated_mb=1084, final_image_mb=28, tiles_mb=1056, threshold_mb=750, zoom_level=14
        )

        assert "zoom level (currently 14)" in message
        assert "1084MB" in message
        assert "750MB" in message


class TestTotalTileCount:
    def test_doubles_for_an_openaip_overlay_on_a_non_openaip_base(self):
        # The overlay is a second GoogleWTS mosaic fetched for the same domain/zoom - the
        # estimate must account for its cost too, not just the base imagery's.
        assert total_tile_count(792, include_openaip_overlay=True, provider="osm") == 1584

    def test_no_overlay_leaves_the_count_unchanged(self):
        assert total_tile_count(792, include_openaip_overlay=False, provider="osm") == 792

    def test_openaip_base_is_not_doubled(self):
        # provider="openaip" means the base imagery already IS the OpenAIP layer - plot_route
        # skips adding a separate overlay image in that case, so there's no second fetch.
        assert total_tile_count(792, include_openaip_overlay=True, provider="openaip") == 792


def _plot_route_needing(memory_by_zoom: dict):
    """A plot_route stand-in: estimates from [memory_by_zoom], and refuses like the real one above the threshold."""

    def fake_plot_route(task, map_size, zoom_level=None, estimate_only=False, **kwargs):
        estimated_mb = memory_by_zoom[zoom_level]
        if estimate_only:
            return estimated_mb
        if estimated_mb > MEMORY_THRESHOLD_MB:
            raise MemoryEstimationExceededError(f"too much at {zoom_level}")
        return f"image at {zoom_level}"

    return fake_plot_route


class TestPlotRouteWithinMemoryLimit:
    # Sentry PYTHON-DJANGO-Z: a flight order configured at zoom 14 and 1:200,000 needed ~2140MB, so the pilots of that
    # task got no flight order at all.
    def test_lowers_the_zoom_level_until_the_map_fits(self):
        task = SimpleNamespace(pk=1)
        with patch(
            "display.flight_order_and_maps.map_plotter.plot_route",
            side_effect=_plot_route_needing({14: 2140, 13: 1600, 12: 600}),
        ):
            assert plot_route_within_memory_limit(task, "A4", 14) == ("image at 12", 12)

    def test_gives_up_below_the_minimum_zoom_level(self):
        task = SimpleNamespace(pk=1)
        too_much = {zoom: 5000 for zoom in range(MINIMUM_FALLBACK_ZOOM_LEVEL, 15)}
        with patch("display.flight_order_and_maps.map_plotter.plot_route", side_effect=_plot_route_needing(too_much)):
            with pytest.raises(MemoryEstimationExceededError):
                plot_route_within_memory_limit(task, "A4", 14)

    def test_does_not_go_below_the_lowest_zoom_level_of_an_uploaded_map(self):
        # Below its lowest zoom level an uploaded map has no tiles: the map would come out blank
        task = SimpleNamespace(pk=1)
        uploaded_map = SimpleNamespace(pk=1)
        with patch(
            "display.flight_order_and_maps.map_plotter.resolve_map_source_definition", return_value={"min_zoom": 12}
        ), patch(
            "display.flight_order_and_maps.map_plotter.plot_route",
            side_effect=_plot_route_needing({14: 2140, 13: 1600, 12: 1550, 11: 600}),
        ):
            with pytest.raises(MemoryEstimationExceededError):
                plot_route_within_memory_limit(task, "A4", 14, user_map_source=uploaded_map)
            assert highest_zoom_level_within_memory_limit(task, "A4", 14, user_map_source=uploaded_map) is None


class TestFlightOrderMapMemoryError:
    def _configuration(self, zoom_level):
        return SimpleNamespace(
            map_zoom_level=zoom_level,
            map_orientation="landscape",
            map_include_contestant_declarations=True,
            map_include_annotations=True,
            map_plot_track_between_waypoints=True,
            map_dpi=300,
            map_scale=200,
            map_source="osm",
            map_include_openaip_overlay=False,
            map_line_width=0.5,
            map_minute_mark_line_width=0.5,
            map_line_colour="#0000ff",
            map_include_meridians_and_parallels_lines=True,
            document_size="A4",
        )

    def _error(self, zoom_level, memory_by_zoom):
        from display.flight_order_and_maps.generate_flight_orders import flight_order_map_memory_error

        with patch(
            "display.flight_order_and_maps.generate_flight_orders.plot_route", side_effect=_plot_route_needing(memory_by_zoom)
        ), patch("display.flight_order_and_maps.map_plotter.plot_route", side_effect=_plot_route_needing(memory_by_zoom)):
            return flight_order_map_memory_error(SimpleNamespace(pk=1), self._configuration(zoom_level))

    def test_a_configuration_that_fits_is_accepted(self):
        assert self._error(12, {12: 900}) is None

    def test_names_the_highest_zoom_level_that_fits(self):
        error = self._error(14, {14: 2140, 13: 1600, 12: 600})
        assert "zoom level 14 needs about 2140 MB" in error
        assert "The highest zoom level that fits is 12." in error

    def test_says_when_no_zoom_level_fits(self):
        error = self._error(14, {zoom: 5000 for zoom in range(MINIMUM_FALLBACK_ZOOM_LEVEL, 15)})
        assert "choose a smaller scale or page size" in error
