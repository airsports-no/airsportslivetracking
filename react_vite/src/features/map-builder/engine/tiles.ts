/**
 * Web Mercator tile maths for the map builder.
 *
 * Everything is expressed in "global pixels" at a zoom level: the world is `256 * 2^zoom` pixels
 * wide, x grows eastwards and y grows southwards (XYZ / slippy-map convention). MBTiles stores rows
 * the other way round (TMS); that flip only happens in `mbtiles.ts`.
 */

export const TILE_SIZE = 256;

/** The largest number of tiles at the detail (maximum) zoom level a single map may have. */
export const MAX_DETAIL_TILES = 1000;

/** Default width and height (in detail-zoom tiles) of a small test patch for previewing settings quickly. */
export const SAMPLE_SIDE_TILES = 3;

export interface Bounds {
    west: number;
    south: number;
    east: number;
    north: number;
}

/** The tiles of one zoom level that cover an area. */
export interface TileGrid {
    zoom: number;
    /** First and last tile column and row (inclusive, XYZ numbering). */
    tileX0: number;
    tileY0: number;
    tileX1: number;
    tileY1: number;
    columns: number;
    rows: number;
    tileCount: number;
    /** Size of the whole grid in pixels. */
    width: number;
    height: number;
}

/** A pixel rectangle at `zoom`, positioned in global pixels. Vector features are stored relative to its origin. */
export interface Frame {
    zoom: number;
    originX: number;
    originY: number;
    width: number;
    height: number;
    /** The geographic extent of the rectangle. */
    bounds: Bounds;
}

/** What the user asked for: an area and the zoom levels to render it at. */
export interface MapArea {
    bounds: Bounds;
    minZoom: number;
    maxZoom: number;
}

export const longitudeToPixel = (longitude: number, zoom: number): number =>
    ((longitude + 180) / 360) * TILE_SIZE * 2 ** zoom;

export const latitudeToPixel = (latitude: number, zoom: number): number => {
    const sine = Math.sin((latitude * Math.PI) / 180);
    return (0.5 - Math.log((1 + sine) / (1 - sine)) / (4 * Math.PI)) * TILE_SIZE * 2 ** zoom;
};

export const pixelToLongitude = (x: number, zoom: number): number => (x / (TILE_SIZE * 2 ** zoom)) * 360 - 180;

export const pixelToLatitude = (y: number, zoom: number): number => {
    const n = Math.PI - (2 * Math.PI * y) / (TILE_SIZE * 2 ** zoom);
    return (180 / Math.PI) * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));
};

export function isValidBounds(bounds: Bounds): boolean {
    const values = [bounds.west, bounds.south, bounds.east, bounds.north];
    return (
        values.every(Number.isFinite) &&
        bounds.west < bounds.east &&
        bounds.south < bounds.north &&
        bounds.west >= -180 &&
        bounds.east <= 180 &&
        // Web Mercator stops at about 85.05 degrees
        bounds.south >= -85 &&
        bounds.north <= 85
    );
}

/** The tiles at `zoom` needed to cover `bounds`. */
export function tileGridForBounds(bounds: Bounds, zoom: number): TileGrid {
    const epsilon = 1e-6;
    const tileX0 = Math.floor(longitudeToPixel(bounds.west, zoom) / TILE_SIZE);
    const tileX1 = Math.floor((longitudeToPixel(bounds.east, zoom) - epsilon) / TILE_SIZE);
    const tileY0 = Math.floor(latitudeToPixel(bounds.north, zoom) / TILE_SIZE);
    const tileY1 = Math.floor((latitudeToPixel(bounds.south, zoom) - epsilon) / TILE_SIZE);
    const columns = tileX1 - tileX0 + 1;
    const rows = tileY1 - tileY0 + 1;
    return {
        zoom,
        tileX0,
        tileY0,
        tileX1,
        tileY1,
        columns,
        rows,
        tileCount: columns * rows,
        width: columns * TILE_SIZE,
        height: rows * TILE_SIZE,
    };
}

/** The geographic extent actually covered by a grid's tiles (always at least the requested bounds). */
export function gridBounds(grid: TileGrid): Bounds {
    return {
        west: pixelToLongitude(grid.tileX0 * TILE_SIZE, grid.zoom),
        east: pixelToLongitude((grid.tileX1 + 1) * TILE_SIZE, grid.zoom),
        north: pixelToLatitude(grid.tileY0 * TILE_SIZE, grid.zoom),
        south: pixelToLatitude((grid.tileY1 + 1) * TILE_SIZE, grid.zoom),
    };
}

/** One grid per zoom level, from the detail (maximum) level down to the minimum. */
export function tileGridsForArea(area: MapArea): TileGrid[] {
    const grids: TileGrid[] = [];
    for (let zoom = area.maxZoom; zoom >= area.minZoom; zoom--) grids.push(tileGridForBounds(area.bounds, zoom));
    return grids;
}

/**
 * The frame the vector data is fetched and stored in: detail-zoom pixels, covering the tiles of the
 * *lowest* zoom level. Lower levels have larger tiles, so their grid reaches furthest beyond the
 * requested bounds; covering it means every tile of every level is fully drawn.
 */
export function frameForArea(area: MapArea): Frame {
    const coarsest = tileGridForBounds(area.bounds, area.minZoom);
    const scale = 2 ** (area.maxZoom - area.minZoom);
    return {
        zoom: area.maxZoom,
        originX: coarsest.tileX0 * TILE_SIZE * scale,
        originY: coarsest.tileY0 * TILE_SIZE * scale,
        width: coarsest.width * scale,
        height: coarsest.height * scale,
        bounds: gridBounds(coarsest),
    };
}

/** A stable identifier for "the same downloaded data can be reused". */
export const frameKey = (frame: Frame): string =>
    [frame.zoom, frame.originX, frame.originY, frame.width, frame.height].join(",");

export function distanceKm(latitude1: number, longitude1: number, latitude2: number, longitude2: number): number {
    const radians = Math.PI / 180;
    const a =
        Math.sin(((latitude2 - latitude1) * radians) / 2) ** 2 +
        Math.cos(latitude1 * radians) *
            Math.cos(latitude2 * radians) *
            Math.sin(((longitude2 - longitude1) * radians) / 2) ** 2;
    return 2 * 6371 * Math.asin(Math.sqrt(a));
}

/** Ground size of one pixel, in metres, at the given latitude and zoom. */
export const metresPerPixel = (latitude: number, zoom: number): number =>
    ((2 * Math.PI * 6378137) / (TILE_SIZE * 2 ** zoom)) * Math.cos((latitude * Math.PI) / 180);

export interface AreaSummary {
    widthKm: number;
    heightKm: number;
    metresPerPixel: number;
    detailGrid: TileGrid;
    totalTiles: number;
    tooLarge: boolean;
}

export function summariseArea(area: MapArea): AreaSummary {
    const { bounds } = area;
    const middle = (bounds.south + bounds.north) / 2;
    const grids = tileGridsForArea(area);
    return {
        widthKm: distanceKm(middle, bounds.west, middle, bounds.east),
        heightKm: distanceKm(bounds.south, bounds.west, bounds.north, bounds.west),
        metresPerPixel: metresPerPixel(middle, area.maxZoom),
        detailGrid: grids[0],
        totalTiles: grids.reduce((sum, grid) => sum + grid.tileCount, 0),
        tooLarge: grids[0].tileCount > MAX_DETAIL_TILES,
    };
}

/**
 * Picks a small rectangle in the middle of `bounds` covering at most `sideTiles × sideTiles` tiles
 * at `zoom`, so the user can generate and inspect a representative sample in a few seconds before
 * generating the full extent.
 */
export function sampleBounds(bounds: Bounds, zoom: number, sideTiles = SAMPLE_SIDE_TILES): Bounds {
    const round = (value: number) => Math.round(value * 100000) / 100000;
    const grid = tileGridForBounds(bounds, zoom);
    if (grid.columns <= sideTiles && grid.rows <= sideTiles) return bounds;
    const cols = Math.min(grid.columns, sideTiles);
    const rows = Math.min(grid.rows, sideTiles);
    const startCol = grid.tileX0 + Math.floor((grid.columns - cols) / 2);
    const endCol = startCol + cols - 1;
    const startRow = grid.tileY0 + Math.floor((grid.rows - rows) / 2);
    const endRow = startRow + rows - 1;
    // Inset by 1 pixel from the tile edges so tileGridForBounds stays within the chosen columns/rows.
    const west = Math.max(bounds.west, pixelToLongitude(startCol * TILE_SIZE + 1, zoom));
    const east = Math.min(bounds.east, pixelToLongitude((endCol + 1) * TILE_SIZE - 1, zoom));
    const north = Math.min(bounds.north, pixelToLatitude(startRow * TILE_SIZE + 1, zoom));
    const south = Math.max(bounds.south, pixelToLatitude((endRow + 1) * TILE_SIZE - 1, zoom));
    return { west: round(west), south: round(south), east: round(east), north: round(north) };
}
