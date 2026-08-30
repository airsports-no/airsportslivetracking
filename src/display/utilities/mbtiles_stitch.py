import logging
import math
from io import BytesIO
from typing import Tuple

from PIL import Image
from pymbtiles import MBtiles, Tile

logger = logging.getLogger(__name__)


class MBTilesHelper:
    def __init__(self, mbtiles: MBtiles):
        self.mbtiles = mbtiles
        self.tms = self.mbtiles.meta.get("scheme", "tms") == "tms"
        smallest_zoom, largest_zoom = self.mbtiles.zoom_range()
        logger.info(f"Selecting zoom level {smallest_zoom}")
        self.tiles = [tile for tile in self.mbtiles.list_tiles() if tile.z == largest_zoom]
        self.tile_width, self.tile_height = self.get_image_size(self.mbtiles.read_tile(*self.tiles[0]))
        self.min_x = min([tile.x for tile in self.tiles])
        self.max_x = max([tile.x for tile in self.tiles])
        self.min_y = min([tile.y for tile in self.tiles])
        self.max_y = max([tile.y for tile in self.tiles])
        self.num_x = self.max_x - self.min_x + 1
        self.num_y = self.max_y - self.min_y + 1
        self.map_width = self.num_x * self.tile_width
        self.map_height = self.num_y * self.tile_height

    def get_image_size(self, tile: bytes) -> Tuple[float, float]:
        img = Image.open(BytesIO(tile))
        return img.size

    def stitch(self, requested_width: int):
        if requested_width < self.map_width:
            width = self.num_x * int(requested_width / self.num_x)
            height = int(width * self.map_height / self.map_width)
        else:
            width = self.map_width
            height = self.map_height
        result_image = Image.new(
            "RGBA",
            (width, height),
            (0, 0, 0, 0),
        )
        self.do_stitching(result_image)
        return result_image

    def do_stitching(self, result_image: Image):
        width, height = result_image.size
        scaled_tile_width = int(width / self.num_x)
        scaled_tile_height = int(height / self.num_y)
        for tile_coordinate in self.tiles:
            tile = self.mbtiles.read_tile(*tile_coordinate)
            image = Image.open(BytesIO(tile))
            image = image.resize((scaled_tile_width, scaled_tile_height), Image.LANCZOS)
            # TMS y increases northward (0 = south); ranging position_y over [0, num_y-1]
            # requires max_y - y, not num_y - y + min_y, which ranges over [1, num_y] instead -
            # the southernmost tile pastes at y == height, a silent PIL no-op.
            position_y = self.max_y - tile_coordinate.y if self.tms else tile_coordinate.y - self.min_y
            result_image.paste(
                image,
                (
                    int((tile_coordinate.x - self.min_x) * scaled_tile_width),
                    int(position_y * scaled_tile_height),
                ),
            )

    def bounds(self):
        bounds_metadata = self.mbtiles.meta.get("bounds")
        if bounds_metadata:
            west, south, east, north = [float(value) for value in str(bounds_metadata).split(",")]
            return west, south, east, north

        def tile_to_lon_lat(x: int, y: int, z: int):
            n = 2.0**z
            lon_deg = x / n * 360.0 - 180.0
            lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
            lat_deg = math.degrees(lat_rad)
            return lon_deg, lat_deg

        zoom = self.tiles[0].z
        if self.tms:
            # tile_to_lon_lat assumes XYZ addressing (y=0 at the north edge, increasing
            # southward). TMS y increases northward instead, so the tile y-range itself
            # must be converted (y_xyz = 2**z - 1 - y_tms) before calling it - swapping the
            # resulting min/max lat labels (the previous fix attempt) doesn't correct for
            # tile_to_lon_lat having been fed raw TMS y values as though they were XYZ
            # ones, and produces bounds that are both inverted and mirrored about the
            # equator.
            n_tiles = int(2**zoom)
            top_y = n_tiles - 1 - self.max_y
            bottom_y = n_tiles - self.min_y
        else:
            top_y = self.min_y
            bottom_y = self.max_y + 1
        min_lon, max_lat = tile_to_lon_lat(self.min_x, top_y, zoom)
        max_lon, min_lat = tile_to_lon_lat(self.max_x + 1, bottom_y, zoom)
        return min_lon, min_lat, max_lon, max_lat
