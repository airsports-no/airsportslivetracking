/**
 * Terrain: elevation download, hillshading and contour lines.
 *
 * Elevation comes from Mapterhorn (Copernicus GLO-30 plus national LiDAR models), as 512 pixel
 * tiles in "terrarium" encoding. A 512 pixel tile at zoom z-1 lines up pixel for pixel with the
 * 2x2 block of 256 pixel tiles at zoom z, so no resampling is needed.
 */
import type { TileGrid } from './tiles';
import { TILE_SIZE, pixelToLatitude } from './tiles';
import type { TaskContext } from './types';
import { sleep, throwIfCancelled } from './types';

const terrainTileUrl = (zoom: number, x: number, y: number) => `https://tiles.mapterhorn.com/${zoom}/${x}/${y}.webp`;
const TERRAIN_TILE_SIZE = 512;

export interface Elevation {
    /** Metres above sea level, one value per pixel of the grid, row by row. */
    values: Float32Array;
    /** False when some tiles could not be downloaded (those areas are flat). */
    complete: boolean;
}

interface TerrainTile {
    values: Float32Array;
    size: number;
}

async function downloadTerrainTile(url: string, signal: AbortSignal): Promise<TerrainTile | null> {
    for (let attempt = 0; attempt < 3; attempt++) {
        throwIfCancelled(signal);
        try {
            const response = await fetch(url, { signal });
            if (response.status === 404) return null;
            if (!response.ok) throw new Error(String(response.status));
            const bitmap = await createImageBitmap(await response.blob());
            const canvas = document.createElement('canvas');
            canvas.width = bitmap.width;
            canvas.height = bitmap.height;
            const context = canvas.getContext('2d', { willReadFrequently: true })!;
            context.drawImage(bitmap, 0, 0);
            const pixels = context.getImageData(0, 0, bitmap.width, bitmap.height).data;
            const values = new Float32Array(bitmap.width * bitmap.height);
            for (let i = 0, j = 0; i < values.length; i++, j += 4) {
                values[i] = pixels[j] * 256 + pixels[j + 1] + pixels[j + 2] / 256 - 32768;
            }
            const size = bitmap.width;
            bitmap.close();
            return { values, size };
        } catch {
            throwIfCancelled(signal);
            await sleep(800);
        }
    }
    return null;
}

export async function fetchElevation(grid: TileGrid, context: TaskContext): Promise<Elevation> {
    const { signal, reporter } = context;
    const { width, height } = grid;
    const values = new Float32Array(width * height);
    const terrainZoom = grid.zoom - 1;
    const tiles: [number, number][] = [];
    for (let y = grid.tileY0 >> 1; y <= grid.tileY1 >> 1; y++) {
        for (let x = grid.tileX0 >> 1; x <= grid.tileX1 >> 1; x++) tiles.push([x, y]);
    }
    const originX = grid.tileX0 * TILE_SIZE;
    const originY = grid.tileY0 * TILE_SIZE;
    let done = 0, approximated = 0, failed = 0;
    reporter.log(`Downloading terrain for zoom ${grid.zoom}: ${tiles.length} tiles…`);

    async function readTile([tileX, tileY]: [number, number]): Promise<void> {
        let tile = await downloadTerrainTile(terrainTileUrl(terrainZoom, tileX, tileY), signal);
        let scale = 1, sourceX = 0, sourceY = 0;
        // No data at this zoom: enlarge the matching part of a parent tile instead.
        for (let levels = 1; levels <= 3 && !tile && terrainZoom - levels >= 0; levels++) {
            tile = await downloadTerrainTile(terrainTileUrl(terrainZoom - levels, tileX >> levels, tileY >> levels), signal);
            if (tile) {
                scale = 2 ** levels;
                sourceX = ((tileX - ((tileX >> levels) << levels)) * TERRAIN_TILE_SIZE) / scale;
                sourceY = ((tileY - ((tileY >> levels) << levels)) * TERRAIN_TILE_SIZE) / scale;
                approximated++;
            }
        }
        if (!tile) {
            failed++;
            return;
        }
        const size = tile.size;
        const source = tile.values;
        for (let y = 0; y < TERRAIN_TILE_SIZE; y++) {
            const targetY = tileY * TERRAIN_TILE_SIZE + y - originY;
            if (targetY < 0 || targetY >= height) continue;
            for (let x = 0; x < TERRAIN_TILE_SIZE; x++) {
                const targetX = tileX * TERRAIN_TILE_SIZE + x - originX;
                if (targetX < 0 || targetX >= width) continue;
                if (scale === 1) {
                    values[targetY * width + targetX] = source[y * size + x];
                    continue;
                }
                // Bilinear interpolation in the parent tile.
                const fx = sourceX + (x + 0.5) / scale - 0.5;
                const fy = sourceY + (y + 0.5) / scale - 0.5;
                const x0 = Math.max(0, Math.floor(fx));
                const y0 = Math.max(0, Math.floor(fy));
                const x1 = Math.min(size - 1, x0 + 1);
                const y1 = Math.min(size - 1, y0 + 1);
                const ax = fx - x0;
                const ay = fy - y0;
                values[targetY * width + targetX] =
                    (source[y0 * size + x0] * (1 - ax) + source[y0 * size + x1] * ax) * (1 - ay) +
                    (source[y1 * size + x0] * (1 - ax) + source[y1 * size + x1] * ax) * ay;
            }
        }
    }

    const queue = [...tiles];
    const workers = Array.from({ length: 6 }, async () => {
        for (let tile = queue.shift(); tile; tile = queue.shift()) {
            await readTile(tile);
            done++;
            if (done % 5 === 0) reporter.progress(done / tiles.length);
        }
    });
    await Promise.all(workers);
    if (failed) {
        reporter.log(`  ${failed} terrain tiles could not be downloaded (those areas will be flat)`, 'error');
    } else {
        reporter.log(`  terrain complete${approximated ? ` (${approximated} tiles at reduced resolution)` : ''}`, 'success');
    }
    return { values, complete: failed === 0 };
}

export interface HillshadeOptions {
    enabled: boolean;
    /** Vertical exaggeration; makes gentle terrain readable. */
    exaggeration: number;
    /** 0..1, how dark the darkest slopes get. */
    intensity: number;
}

/**
 * Greyscale shading for a block of the grid, lit from four directions around the north-west so
 * that ridges running towards the light do not disappear. With shading off the block is white.
 */
export function hillshade(
    elevation: Float32Array,
    grid: TileGrid,
    x0: number,
    y0: number,
    width: number,
    height: number,
    options: HillshadeOptions,
): ImageData {
    const output = new Uint8ClampedArray(width * height * 4);
    if (!options.enabled) {
        output.fill(255);
        return new ImageData(output, width, height);
    }
    const gridWidth = grid.width;
    const gridHeight = grid.height;
    const circumference = 2 * Math.PI * 6378137;
    const worldPixels = TILE_SIZE * 2 ** grid.zoom;
    const altitude = (45 * Math.PI) / 180;
    const flat = Math.sin(altitude);
    const lights = [[225, 0.5], [270, 1], [315, 1], [360, 0.5]].map(
        ([azimuth, weight]) => [((360 - azimuth + 90) * Math.PI) / 180, weight] as const,
    );
    const totalWeight = 3;
    for (let y = 0; y < height; y++) {
        const gridY = y0 + y;
        const latitude = pixelToLatitude(grid.tileY0 * TILE_SIZE + gridY + 0.5, grid.zoom);
        const metres = (circumference / worldPixels) * Math.cos((latitude * Math.PI) / 180);
        const up = Math.max(0, gridY - 1);
        const down = Math.min(gridHeight - 1, gridY + 1);
        const dy = (down - up) * metres;
        for (let x = 0; x < width; x++) {
            const gridX = x0 + x;
            const left = Math.max(0, gridX - 1);
            const right = Math.min(gridWidth - 1, gridX + 1);
            const dzdx =
                ((elevation[gridY * gridWidth + right] - elevation[gridY * gridWidth + left]) * options.exaggeration) /
                ((right - left) * metres);
            const dzdy =
                ((elevation[down * gridWidth + gridX] - elevation[up * gridWidth + gridX]) * options.exaggeration) / dy;
            const slope = Math.atan(Math.hypot(dzdx, dzdy));
            const aspect = Math.atan2(-dzdx, dzdy);
            let light = 0;
            for (const [direction, weight] of lights) {
                light +=
                    weight *
                    (Math.sin(altitude) * Math.cos(slope) + Math.cos(altitude) * Math.sin(slope) * Math.cos(direction - aspect));
            }
            let dark = 1 - light / totalWeight / flat;
            dark = Math.sqrt(dark < 0 ? 0 : dark > 1 ? 1 : dark);
            const value = 255 * (1 - options.intensity * dark);
            const i = (y * width + x) * 4;
            output[i] = output[i + 1] = output[i + 2] = value;
            output[i + 3] = 255;
        }
    }
    return new ImageData(output, width, height);
}

const CONTOUR_COLOR = '#b8925a';
const INDEX_CONTOUR_INTERVAL = 50;

/**
 * Contour lines for a block of the grid: marching squares over a smoothed copy of the elevation
 * (smoothing removes the noise of trees and buildings in LiDAR-derived models).
 */
export function drawContours(
    context: CanvasRenderingContext2D,
    elevation: Float32Array,
    grid: TileGrid,
    x0: number,
    y0: number,
    width: number,
    height: number,
    interval: number,
): void {
    const gridWidth = grid.width;
    const gridHeight = grid.height;
    const margin = 4;
    const regionX0 = Math.max(0, x0 - margin);
    const regionY0 = Math.max(0, y0 - margin);
    const regionX1 = Math.min(gridWidth, x0 + width + margin);
    const regionY1 = Math.min(gridHeight, y0 + height + margin);
    const regionWidth = regionX1 - regionX0;
    const regionHeight = regionY1 - regionY0;
    const smooth = new Float32Array(regionWidth * regionHeight);
    for (let y = 0; y < regionHeight; y++) {
        smooth.set(elevation.subarray((regionY0 + y) * gridWidth + regionX0, (regionY0 + y) * gridWidth + regionX1), y * regionWidth);
    }
    // Separable box blur; two passes approximate a Gaussian.
    const scratch = new Float32Array(regionWidth * regionHeight);
    const radius = 2;
    for (let pass = 0; pass < 2; pass++) {
        for (let y = 0; y < regionHeight; y++) {
            let sum = 0, count = 0;
            const row = y * regionWidth;
            for (let x = -radius; x < regionWidth + radius; x++) {
                const entering = x + radius;
                if (entering < regionWidth) {
                    sum += smooth[row + entering];
                    count++;
                }
                const leaving = x - radius - 1;
                if (leaving >= 0) {
                    sum -= smooth[row + leaving];
                    count--;
                }
                if (x >= 0 && x < regionWidth) scratch[row + x] = sum / count;
            }
        }
        for (let x = 0; x < regionWidth; x++) {
            let sum = 0, count = 0;
            for (let y = -radius; y < regionHeight + radius; y++) {
                const entering = y + radius;
                if (entering < regionHeight) {
                    sum += scratch[entering * regionWidth + x];
                    count++;
                }
                const leaving = y - radius - 1;
                if (leaving >= 0) {
                    sum -= scratch[leaving * regionWidth + x];
                    count--;
                }
                if (y >= 0 && y < regionHeight) smooth[y * regionWidth + x] = sum / count;
            }
        }
    }

    const indexPath = new Path2D();
    const regularPath = new Path2D();
    const cellX0 = Math.max(regionX0, x0 - 1);
    const cellY0 = Math.max(regionY0, y0 - 1);
    const cellX1 = Math.min(regionX1 - 1, x0 + width);
    const cellY1 = Math.min(regionY1 - 1, y0 + height);
    const crossings: number[] = [];
    for (let cellY = cellY0; cellY < cellY1; cellY++) {
        const j = cellY - regionY0;
        for (let cellX = cellX0; cellX < cellX1; cellX++) {
            const i = cellX - regionX0;
            const a = smooth[j * regionWidth + i];
            const b = smooth[j * regionWidth + i + 1];
            const c = smooth[(j + 1) * regionWidth + i + 1];
            const d = smooth[(j + 1) * regionWidth + i];
            const lowest = Math.min(a, b, c, d);
            const highest = Math.max(a, b, c, d);
            let level = Math.ceil(lowest / interval) * interval;
            // No contour at zero: it would trace the coastline.
            if (level <= 0) level = interval;
            const px = cellX + 0.5 - x0;
            const py = cellY + 0.5 - y0;
            for (; level <= highest; level += interval) {
                if (level === lowest && level === highest) continue;
                crossings.length = 0;
                const cross = (v1: number, v2: number, ax: number, ay: number, bx: number, by: number) => {
                    if (v1 < level !== v2 < level) {
                        const f = (level - v1) / (v2 - v1);
                        crossings.push(ax + (bx - ax) * f, ay + (by - ay) * f);
                    }
                };
                cross(a, b, px, py, px + 1, py);
                cross(b, c, px + 1, py, px + 1, py + 1);
                cross(c, d, px + 1, py + 1, px, py + 1);
                cross(d, a, px, py + 1, px, py);
                const path = level % INDEX_CONTOUR_INTERVAL === 0 ? indexPath : regularPath;
                for (let k = 0; k + 3 < crossings.length; k += 4) {
                    path.moveTo(crossings[k], crossings[k + 1]);
                    path.lineTo(crossings[k + 2], crossings[k + 3]);
                }
            }
        }
    }
    context.save();
    context.strokeStyle = CONTOUR_COLOR;
    context.lineCap = 'round';
    if (interval < INDEX_CONTOUR_INTERVAL) {
        context.globalAlpha = 0.45;
        context.lineWidth = 0.5;
        context.stroke(regularPath);
    }
    context.globalAlpha = 0.8;
    context.lineWidth = 0.9;
    context.stroke(indexPath);
    context.restore();
}
