"""
Regression test for a production bug: the printed flight-order map's scale bar measured
consistently short - confirmed on a real Nordic-latitude 1:150,000 map (measured in Inkscape:
96mm instead of the intended 10cm) and on a "fit to page" map (~3-6% short).

Root cause: scale_bar_y() sized the bar purely from the nominal `scale` value (assuming a
fixed metres-per-cm ratio), but plot_route() sets the axes' view via
`ax.set_extent(extent, crs=utm)` - cartopy has to reproject that UTM-aligned rectangle into
the axes' own display CRS (a Mercator-style projection, from the tile imagery) to set the
view. A UTM rectangle isn't a rectangle once reprojected into Mercator, so the axes ends up
displaying several percent more ground than the nominal scale assumed - worse at higher
latitudes, since UTM-to-Mercator distortion grows with distance from the equator.

Fix: scale_bar_y() now calibrates the bar directly against the axes' actual rendering
transform (ax.transData) - measuring a known real geodesic distance's true rendered pixel
size - instead of trusting the nominal scale. This test reproduces the exact mismatch
(UTM-vs-Mercator, Nordic latitude) that exposed the bug and asserts the bar is still exactly
10cm.
"""

import math

import cartopy.crs as ccrs
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from django.test import SimpleTestCase

from display.flight_order_and_maps.map_plotter import PSEUDO_MERCATOR_SPHERE, scale_bar_y
from display.utilities.coordinate_utilities import utm_from_lat_lon


class TestScaleBarPhysicalLength(SimpleTestCase):
    def _measure_last_plotted_line_cm(self, ax):
        line = ax.lines[-1]
        transform = line.get_transform()
        xs, ys = line.get_xdata(), line.get_ydata()
        p0 = transform.transform((xs[0], ys[0]))
        p1 = transform.transform((xs[1], ys[1]))
        pixels = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        return (pixels / ax.figure.dpi) * 2.54

    def _build_axes_with_utm_mercator_mismatch(self, lat, lon, dpi):
        # Same setup plot_route() uses: a Mercator-style display CRS, with the actual view
        # set from a UTM-computed rectangle - the exact scenario that exposed the bug.
        fig = plt.figure(figsize=(11.0, 7.0), dpi=dpi)
        ax = fig.add_axes([0, 0, 1, 1], projection=ccrs.Mercator.GOOGLE)
        ax.set_aspect("auto")
        utm = utm_from_lat_lon(lat, lon)
        centre_x, centre_y = utm.transform_point(lon, lat, PSEUDO_MERCATOR_SPHERE)
        half_width, half_height = 30000, 20000  # metres - an arbitrary "fixed scale" extent
        extent = [centre_x - half_width, centre_x + half_width, centre_y - half_height, centre_y + half_height]
        ax.set_extent(extent, crs=utm)
        return fig, ax

    def test_bar_measures_exactly_10cm_at_nordic_latitude(self):
        # A high-latitude (Nordic) point: the UTM/Mercator distortion this guards against
        # grows with latitude, and this is what the originally reported bug was measured on.
        fig, ax = self._build_axes_with_utm_mercator_mismatch(lat=60.0, lon=10.7, dpi=150)
        self.addCleanup(plt.close, fig)

        scale_bar_y(ax, PSEUDO_MERCATOR_SPHERE, units="NM", m_per_unit=1852)

        self.assertAlmostEqual(self._measure_last_plotted_line_cm(ax), 10.0, delta=0.05)

    def test_bar_measures_exactly_10cm_near_the_equator(self):
        # Distortion from this bug is smallest near the equator, but the fix should be exact
        # everywhere, not just somewhere the old (broken) code happened to be close enough.
        fig, ax = self._build_axes_with_utm_mercator_mismatch(lat=1.0, lon=30.0, dpi=300)
        self.addCleanup(plt.close, fig)

        scale_bar_y(ax, PSEUDO_MERCATOR_SPHERE, units="NM", m_per_unit=1852)

        self.assertAlmostEqual(self._measure_last_plotted_line_cm(ax), 10.0, delta=0.05)

    def test_bar_measures_exactly_10cm_at_a_different_dpi(self):
        # The calibration explicitly divides by ax.figure.dpi - verify it isn't accidentally
        # hardcoded to one DPI value (flight orders support both 150 and 300 dpi).
        fig, ax = self._build_axes_with_utm_mercator_mismatch(lat=60.0, lon=10.7, dpi=300)
        self.addCleanup(plt.close, fig)

        scale_bar_y(ax, PSEUDO_MERCATOR_SPHERE, units="NM", m_per_unit=1852)

        self.assertAlmostEqual(self._measure_last_plotted_line_cm(ax), 10.0, delta=0.05)
