import logging
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
        self.tiles = [
            tile for tile in self.mbtiles.list_tiles() if tile.z == largest_zoom
        ]
        self.tile_width, self.tile_height = self.get_image_size(
            self.mbtiles.read_tile(*self.tiles[0])
        )
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
            position_y = self.num_y - tile_coordinate.y + self.min_y if self.tms else tile_coordinate.y - self.min_y
            result_image.paste(
                image,
                (
                    int((tile_coordinate.x - self.min_x) * scaled_tile_width),
                    int(position_y * scaled_tile_height),
                ),
            )
