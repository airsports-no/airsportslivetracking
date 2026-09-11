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
"""

from display.flight_order_and_maps.map_plotter import (
    estimate_memory_usage,
    estimate_tile_memory_mb,
)

# Mirrors plot_route()'s local MEMORY_THRESHOLD_MB safety threshold.
MEMORY_THRESHOLD_MB = 750

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
        # With both fixes applied, this configuration's actual peak (~1092MB) has dropped below
        # the old measured peak but is still well above the 750MB safety threshold - i.e. this
        # specific "zoom to fit" A3/300dpi configuration should still be refused, just by a
        # narrower and more honest margin than before either fix existed.
        final_image_mb = estimate_memory_usage(REAL_WORLD_FIGURE_WIDTH_CM, REAL_WORLD_FIGURE_HEIGHT_CM, REAL_WORLD_DPI)
        tiles_mb = estimate_tile_memory_mb(REAL_WORLD_TOTAL_TILES)
        estimated_mb = final_image_mb + tiles_mb

        assert estimated_mb > MEMORY_THRESHOLD_MB
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
