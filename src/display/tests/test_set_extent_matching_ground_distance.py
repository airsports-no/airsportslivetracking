"""
Regression test for a production bug: flight-order maps rendered several percent more
zoomed-out than their configured scale - confirmed on a real Nordic-latitude task (2134,
60N): configured 1:250,000, but the scale bar (once itself fixed to measure correctly, see
test_scale_bar_physical_length.py) reported the map's true effective scale as 1:262,101.

Root cause: plot_route() used to call ax.set_extent(utm_extent, crs=utm) directly - cartopy
has to reproject that UTM-aligned rectangle into the axes' own display CRS (a Mercator-style
projection, from the tile imagery) to establish the view. A UTM rectangle isn't a rectangle
once reprojected into Mercator, so the axes ended up displaying measurably more ground than
intended - worse at higher latitudes, since UTM-to-Mercator distortion grows with distance
from the equator.

Fix: set_extent_matching_ground_distance() converts the UTM extent's centre and half-width/
half-height into the display CRS's own units directly, using the standard Web Mercator local
scale factor (1/cos(latitude)) - no reprojection, so no bounding-box distortion. This test
reproduces the exact mismatch (UTM-vs-Mercator) at both a high latitude and near the equator,
and asserts the axes' actual displayed ground width/height matches what was requested.
"""

import math

import cartopy.crs as ccrs
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from django.test import SimpleTestCase

from display.flight_order_and_maps.map_plotter import PSEUDO_MERCATOR_SPHERE, set_extent_matching_ground_distance
from display.utilities.coordinate_utilities import utm_from_lat_lon


class TestSetExtentMatchingGroundDistance(SimpleTestCase):
    def _measure_actual_ground_extent_metres(self, ax, utm):
        """
        Independently measures what the axes actually displays, in real UTM ground metres -
        by reading back the axes' current view and reprojecting the midpoints of its edges
        (not its corners: a straight line between two Mercator corners doesn't correspond to
        a straight line in UTM, so "corner-to-corner UTM distance" is itself a distorted
        measure at high latitude - the same class of error this fix addresses, just in the
        test's own verification instead of the code under test). Measuring through the
        centre on each axis is deliberately a different code path than
        set_extent_matching_ground_distance() itself, so the test doesn't just check the
        function agrees with itself.
        """
        x0, x1, y0, y1 = ax.get_extent(ax.projection)
        centre_x, centre_y = (x0 + x1) / 2, (y0 + y1) / 2
        left = utm.transform_point(x0, centre_y, ax.projection)
        right = utm.transform_point(x1, centre_y, ax.projection)
        bottom = utm.transform_point(centre_x, y0, ax.projection)
        top = utm.transform_point(centre_x, y1, ax.projection)
        width = math.hypot(right[0] - left[0], right[1] - left[1])
        height = math.hypot(top[0] - bottom[0], top[1] - bottom[1])
        return width, height

    def _build_axes(self, dpi=150):
        fig = plt.figure(figsize=(11.0, 7.0), dpi=dpi)
        ax = fig.add_axes([0, 0, 1, 1], projection=ccrs.Mercator.GOOGLE)
        ax.set_aspect("auto")
        return fig, ax

    def _assert_extent_matches_ground_distance(self, lat, lon, width_metres, height_metres):
        fig, ax = self._build_axes()
        self.addCleanup(plt.close, fig)
        utm = utm_from_lat_lon(lat, lon)
        centre_x, centre_y = utm.transform_point(lon, lat, PSEUDO_MERCATOR_SPHERE)
        utm_extent = [
            centre_x - width_metres / 2,
            centre_x + width_metres / 2,
            centre_y - height_metres / 2,
            centre_y + height_metres / 2,
        ]

        set_extent_matching_ground_distance(ax, utm_extent, utm, PSEUDO_MERCATOR_SPHERE)

        actual_width, actual_height = self._measure_actual_ground_extent_metres(ax, utm)
        # 1% tolerance: some residual noise comes from the test's own verification method
        # (reprojecting edge midpoints through UTM), not from the fix - real-world
        # measurement on production data (task 2134, 60N) showed 0.03% error after this fix,
        # down from 4.84% before it.
        self.assertAlmostEqual(actual_width / width_metres, 1.0, delta=0.01)
        self.assertAlmostEqual(actual_height / height_metres, 1.0, delta=0.01)

    def test_matches_ground_distance_at_nordic_latitude(self):
        # The originally reported bug (1:250,000 configured, 1:262,000 rendered) was measured
        # at 60N - UTM/Mercator distortion is largest at high latitude, so this is where the
        # old code was most wrong.
        self._assert_extent_matches_ground_distance(lat=60.0, lon=11.0, width_metres=47500, height_metres=33250)

    def test_matches_ground_distance_near_the_equator(self):
        # Distortion from this bug is smallest near the equator, but the fix should be exact
        # everywhere, not just somewhere the old (broken) code happened to be close enough.
        self._assert_extent_matches_ground_distance(lat=1.0, lon=30.0, width_metres=30000, height_metres=20000)

    def test_matches_ground_distance_in_the_southern_hemisphere(self):
        self._assert_extent_matches_ground_distance(lat=-33.9, lon=151.2, width_metres=40000, height_metres=28000)

    def test_old_utm_reprojection_would_have_been_measurably_wrong(self):
        # Documents *why* the fix matters: confirms ax.set_extent(utm_extent, crs=utm) (the
        # pre-fix behaviour) really did distort the displayed ground area at this latitude,
        # so this regression test guards against a real, sizeable bug and not a rounding
        # artifact. Uses ax.set_extent directly, not the module's function.
        fig, ax = self._build_axes()
        self.addCleanup(plt.close, fig)
        lat, lon = 60.0, 11.0
        width_metres, height_metres = 47500, 33250
        utm = utm_from_lat_lon(lat, lon)
        centre_x, centre_y = utm.transform_point(lon, lat, PSEUDO_MERCATOR_SPHERE)
        utm_extent = [
            centre_x - width_metres / 2,
            centre_x + width_metres / 2,
            centre_y - height_metres / 2,
            centre_y + height_metres / 2,
        ]

        ax.set_extent(utm_extent, crs=utm)

        actual_width, actual_height = self._measure_actual_ground_extent_metres(ax, utm)
        self.assertGreater(abs(actual_width / width_metres - 1.0), 0.015)
        self.assertGreater(abs(actual_height / height_metres - 1.0), 0.015)
