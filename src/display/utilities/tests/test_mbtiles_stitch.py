"""
Regression tests for management-commands findings #2 and #3 (2026-08-28 review):

- do_stitching's TMS row-index formula (num_y - y + min_y) ranges over [1, num_y] instead of
  [0, num_y-1] - the southernmost tile pastes at y == height, a silent PIL no-op, dropping the
  bottom tile row of every map thumbnail (self.tms defaults to True, so this is the normal path).
- bounds() computed correct XYZ-formula bounds, then unconditionally swapped the resulting
  min/max lat labels for TMS - but TMS-to-XYZ tile-y conversion requires
  y_xyz = 2**z - 1 - y_tms, not a label swap, so the result was both inverted
  (min_lat > max_lat) and mirrored about the equator.
"""

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase
from PIL import Image
from pymbtiles import Tile

from display.utilities.mbtiles_stitch import MBTilesHelper


def _solid_tile_bytes(color) -> bytes:
    img = Image.new("RGBA", (2, 2), color)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def _make_helper(tms: bool, tiles, mbtiles_meta=None) -> MBTilesHelper:
    helper = object.__new__(MBTilesHelper)
    helper.mbtiles = MagicMock()
    helper.mbtiles.meta = mbtiles_meta or {}
    helper.tms = tms
    helper.tiles = tiles
    helper.tile_width = 2
    helper.tile_height = 2
    helper.min_x = min(tile.x for tile in tiles)
    helper.max_x = max(tile.x for tile in tiles)
    helper.min_y = min(tile.y for tile in tiles)
    helper.max_y = max(tile.y for tile in tiles)
    helper.num_x = helper.max_x - helper.min_x + 1
    helper.num_y = helper.max_y - helper.min_y + 1
    helper.map_width = helper.num_x * helper.tile_width
    helper.map_height = helper.num_y * helper.tile_height
    return helper


class TestDoStitchingTmsRowMapping(SimpleTestCase):
    def test_southernmost_tms_tile_lands_in_the_bottom_row(self):
        # South tile is TMS y=0 (red), north tile is TMS y=1 (blue).
        south_tile = Tile(z=1, x=0, y=0, data=None)
        north_tile = Tile(z=1, x=0, y=1, data=None)
        helper = _make_helper(tms=True, tiles=[south_tile, north_tile])

        tile_bytes = {0: _solid_tile_bytes((255, 0, 0, 255)), 1: _solid_tile_bytes((0, 0, 255, 255))}
        helper.mbtiles.read_tile = MagicMock(side_effect=lambda z, x, y, *rest: tile_bytes[y])

        result_image = Image.new("RGBA", (helper.map_width, helper.map_height), (0, 0, 0, 0))
        helper.do_stitching(result_image)

        # South (TMS y=0, red) must be in the BOTTOM row of the stitched image; north (TMS
        # y=1, blue) in the TOP row - south is never y == image height (a no-op paste).
        top_row_pixel = result_image.getpixel((0, 0))
        bottom_row_pixel = result_image.getpixel((0, helper.map_height - 1))
        self.assertEqual(top_row_pixel, (0, 0, 255, 255))
        self.assertEqual(bottom_row_pixel, (255, 0, 0, 255))


class TestBoundsTmsConversion(SimpleTestCase):
    def test_single_global_tile_bounds_are_not_mirrored_or_inverted(self):
        tile = Tile(z=0, x=0, y=0, data=None)
        helper = _make_helper(tms=True, tiles=[tile])

        min_lon, min_lat, max_lon, max_lat = helper.bounds()

        self.assertLess(min_lat, max_lat)
        self.assertAlmostEqual(min_lon, -180, places=3)
        self.assertAlmostEqual(max_lon, 180, places=3)
        # A single global tile's bounds are the standard Web Mercator extent
        # (~85.0511 degrees), entirely in the northern hemisphere for max_lat.
        self.assertAlmostEqual(max_lat, 85.0511, places=3)
        self.assertAlmostEqual(min_lat, -85.0511, places=3)

    def test_northern_tile_reports_northern_bounds_not_mirrored_south(self):
        # At zoom 1 there are 2x2 tiles; TMS y=1 is the NORTHERN row (y increases
        # northward), spanning from the equator up to ~85.05 degrees N. Mirrored (the
        # pre-fix bug), this would instead report the SOUTHERN hemisphere's counterpart.
        tile = Tile(z=1, x=0, y=1, data=None)
        helper = _make_helper(tms=True, tiles=[tile])

        min_lon, min_lat, max_lon, max_lat = helper.bounds()

        self.assertLess(min_lat, max_lat)
        self.assertAlmostEqual(min_lat, 0, places=3)
        self.assertAlmostEqual(max_lat, 85.0511, places=3)
