"""Regression test for plot_route() fetching far more tile resolution than an output page can
even display, wasting most of its peak memory in matplotlib's own resample/composite step.

Empirically measured (real production task, A3/300dpi/zoom14/scale=0 "zoom to fit", that was
OOM-crashing tracker-celery pods): the fetched tile mosaic (8416x6121px) was ~1.7x finer per axis
than the ~4960x3507px final page, and matplotlib's savefig() resampling that oversized mosaic down
to the page accounted for ~1.8GB of a ~3.3GB peak - entirely wasted, since none of that extra
resolution is visible on the final page.

Fixed by TileDownsamplingMixin.image_for_domain(), which downsamples the merged mosaic to the
output page's own pixel size (plus headroom) before matplotlib ever sees it.
"""

import numpy as np
from django.test import SimpleTestCase

from display.flight_order_and_maps.map_plotter import (
    TileDownsamplingMixin,
    compute_tile_target_pixel_size,
)


class _StubBase:
    """Stands in for cartopy's GoogleWTS.image_for_domain() with a controllable mosaic size."""

    def __init__(self, mosaic):
        self._mosaic = mosaic

    def image_for_domain(self, target_domain, target_z):
        return self._mosaic, [0, 1, 0, 1], "lower"


class _DownsamplingImagery(TileDownsamplingMixin, _StubBase):
    pass


class TestComputeTileTargetPixelSize(SimpleTestCase):
    def test_matches_output_page_pixel_size_with_headroom(self):
        # A3 landscape at 300dpi: page is 4960x3507px; 10% linear headroom on top of that.
        self.assertEqual(compute_tile_target_pixel_size(42, 29.7, 300), (5456, 3858))

    def test_smaller_page_gives_smaller_target(self):
        small = compute_tile_target_pixel_size(29.7, 21, 150)
        large = compute_tile_target_pixel_size(42, 29.7, 300)
        self.assertLess(small[0], large[0])
        self.assertLess(small[1], large[1])


class TestTileDownsamplingMixin(SimpleTestCase):
    def test_downsamples_a_mosaic_larger_than_the_target(self):
        mosaic = np.random.randint(0, 255, size=(6121, 8416, 3), dtype=np.uint8)
        imagery = _DownsamplingImagery(mosaic)
        imagery.target_pixel_size = (5952, 4209)

        img, extent, origin = imagery.image_for_domain(target_domain=None, target_z=14)

        self.assertEqual(img.shape, (4209, 5952, 3))
        self.assertEqual(extent, [0, 1, 0, 1])
        self.assertEqual(origin, "lower")

    def test_does_not_upsample_a_mosaic_smaller_than_the_target(self):
        mosaic = np.random.randint(0, 255, size=(200, 300, 3), dtype=np.uint8)
        imagery = _DownsamplingImagery(mosaic)
        imagery.target_pixel_size = (5952, 4209)

        img, _, _ = imagery.image_for_domain(target_domain=None, target_z=5)

        self.assertEqual(img.shape, (200, 300, 3))

    def test_is_a_no_op_when_target_pixel_size_is_not_set(self):
        # e.g. plot_editable_route()'s add_image() call sites, which don't wire up
        # target_pixel_size - existing behaviour there must be unaffected.
        mosaic = np.random.randint(0, 255, size=(6121, 8416, 3), dtype=np.uint8)
        imagery = _DownsamplingImagery(mosaic)

        img, _, _ = imagery.image_for_domain(target_domain=None, target_z=14)

        self.assertEqual(img.shape, (6121, 8416, 3))
