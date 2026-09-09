"""
Regression test for a user-reported bug: the generated navigation map (PDF) rendered a
task's route ~10 NM north of where the live map/route editor showed it, shape unchanged.

Root cause: every tile provider in map_plotter.py (MyGoogleWTS/GoogleWTS subclasses) sets
self.crs = ccrs.Mercator.GOOGLE, and GoogleWTS.tile_bbox() positions tiles by pure
fractional interpolation over that CRS's native extent - never through a PlateCarree
transform. That implicitly assumes the "Web/Pseudo-Mercator" convention every real XYZ tile
provider (OSM, CyclOSM, any MBTiles chart) actually uses: WGS84 lon/lat treated as if on a
perfect sphere. But every vector-plotting call (waypoints, corridor polygons, gate lines,
gridlines, the UTM scale-fit extent math) used transform=ccrs.PlateCarree(), which defaults
to the real WGS84 ellipsoid - a genuine ellipsoid-to-sphere conversion the tiles never go
through, producing a latitude-dependent north/south offset between the vector overlay and
the tiles it's drawn on (zero at the equator, growing with latitude - about 9 NM at 42N,
matching the reported task's location and the reported ~10 NM shift).

Fixed by routing every such transform through PSEUDO_MERCATOR_SPHERE (an explicit
sphere-globe PlateCarree) instead, matching the spherical convention the tiles already use.
"""

import math

import cartopy.crs as ccrs
from django.test import SimpleTestCase

from display.flight_order_and_maps.map_plotter import PSEUDO_MERCATOR_SPHERE


class TestMapPlotterVectorTileAlignment(SimpleTestCase):
    def test_pseudo_mercator_sphere_matches_standard_web_mercator_formula(self):
        # A real waypoint from the reported task, at a latitude (~42N) where the
        # ellipsoid-vs-sphere divergence is large enough to be visually obvious (~9 NM).
        lat, lon = 41.74953654214251, 2.124080964886541

        x, y = ccrs.Mercator.GOOGLE.transform_point(lon, lat, PSEUDO_MERCATOR_SPHERE)

        radius = 6378137.0
        expected_x = radius * math.radians(lon)
        expected_y = radius * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))

        self.assertAlmostEqual(x, expected_x, places=3)
        self.assertAlmostEqual(y, expected_y, places=3)

    def test_default_platecarree_would_have_diverged_by_several_nautical_miles(self):
        # Documents *why* the fix matters: confirms the bug this regression test guards
        # against is real and large enough to notice, not a rounding artifact. Uses
        # ccrs.PlateCarree() directly (the pre-fix behavior), not the module's constant.
        lat, lon = 41.74953654214251, 2.124080964886541

        _, y_ellipsoidal = ccrs.Mercator.GOOGLE.transform_point(lon, lat, ccrs.PlateCarree())
        _, y_sphere = ccrs.Mercator.GOOGLE.transform_point(lon, lat, PSEUDO_MERCATOR_SPHERE)

        divergence_nm = abs(y_ellipsoidal - y_sphere) / 1852
        self.assertGreater(divergence_nm, 5)

    def test_no_stray_ellipsoidal_platecarree_left_in_map_plotter(self):
        # Guards against a future edit reintroducing ccrs.PlateCarree() (WGS84-ellipsoidal
        # by default) in map_plotter.py instead of the module's sphere-based constant -
        # every tile in this file is positioned assuming the spherical convention, so any
        # vector-plotting call using the real ellipsoid would reintroduce this bug.
        import inspect

        from display.flight_order_and_maps import map_plotter

        source = inspect.getsource(map_plotter)
        # The constant's own definition line is the sole legitimate use of the bare call.
        stray_uses = [
            line
            for line in source.splitlines()
            if "ccrs.PlateCarree()" in line and "PSEUDO_MERCATOR_SPHERE =" not in line
        ]
        self.assertEqual(stray_uses, [])
