"""
Regression test for a production bug report: the SP/FP satellite-image crops embedded in an
ANR task's flight order (generate_turning_point_image) showed terrain nowhere near the actual
waypoint - a task with start/finish clearly on roundabouts produced photos of mountains.

Same root cause as the map_plotter.py bug fixed in
test_map_plotter_vector_tile_alignment.py (see that file for the full explanation): GoogleTiles
imagery is positioned assuming the spherical "Web Mercator" convention, but
generate_turning_point_image/generate_photo used transform=ccrs.PlateCarree() (real WGS84
ellipsoid) for the waypoint marker, the leg lines, the UTM-derived crop extent, and the
200m accuracy circle - producing a latitude-dependent north/south offset between where the
crop window actually sits and the tile imagery beneath it, large enough at high latitudes to
put the crop entirely off the intended waypoint.

Fixed by routing those same calls through map_plotter.PSEUDO_MERCATOR_SPHERE instead.
"""

import inspect

from django.test import SimpleTestCase

from display.flight_order_and_maps import generate_flight_orders
from display.flight_order_and_maps.map_plotter import PSEUDO_MERCATOR_SPHERE


class TestGenerateFlightOrdersVectorTileAlignment(SimpleTestCase):
    def test_module_uses_the_shared_pseudo_mercator_sphere_constant(self):
        source = inspect.getsource(generate_flight_orders)
        self.assertIn("PSEUDO_MERCATOR_SPHERE", source)

    def test_no_stray_ellipsoidal_platecarree_left_in_generate_flight_orders(self):
        # Guards against a future edit reintroducing ccrs.PlateCarree() (WGS84-ellipsoidal by
        # default) here - every GoogleTiles image in this file is positioned assuming the
        # spherical convention, so any vector-plotting/extent call using the real ellipsoid
        # would reintroduce the SP/FP photo mislocation bug.
        source = inspect.getsource(generate_flight_orders)
        stray_uses = [line for line in source.splitlines() if "ccrs.PlateCarree()" in line]
        self.assertEqual(stray_uses, [])

    def test_ccrs_module_is_no_longer_imported_directly(self):
        # generate_flight_orders.py has no legitimate remaining use of ccrs now that every
        # transform/crs argument goes through the shared PSEUDO_MERCATOR_SPHERE constant - a
        # reintroduced "import cartopy.crs as ccrs" is a strong signal someone is about to
        # reach for the bare (ellipsoidal) ccrs.PlateCarree() again.
        source = inspect.getsource(generate_flight_orders)
        self.assertNotIn("import cartopy.crs as ccrs", source)

    def test_pseudo_mercator_sphere_is_reexported_from_map_plotter(self):
        self.assertIs(generate_flight_orders.PSEUDO_MERCATOR_SPHERE, PSEUDO_MERCATOR_SPHERE)
