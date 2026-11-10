/**
 * The whole job: download the data for the area, draw every zoom level and pack the tiles into an
 * MBTiles file. Everything runs in the browser; the only network traffic is between the browser
 * and the public map data providers.
 */
import type { SqlJsStatic } from 'sql.js';

import type { LayerDefinition } from './layers';
import { LAYERS } from './layers';
import { MbtilesWriter } from './mbtiles';
import { drawFeatures, levelTransform } from './render';
import { sourcesForLayer } from './sources';
import type { VectorSource } from './sources';
import type { HillshadeOptions } from './terrain';
import { drawContours, fetchElevation, hillshade } from './terrain';
import type { Frame, MapArea, TileGrid } from './tiles';
import { MAX_DETAIL_TILES, TILE_SIZE, frameForArea, frameKey, gridBounds, tileGridsForArea } from './tiles';
import type { Feature, FeaturesByLayer, Reporter, TaskContext } from './types';
import { sleep, throwIfCancelled } from './types';

export const TERRAIN_ATTRIBUTION = 'Mapterhorn / Copernicus DEM';

/** The server's limit on an uploaded map file (see `validate_file_size` in user_uploaded_map.py). */
export const MAX_FILE_BYTES = 100 * 1024 * 1024;

export interface TerrainOptions {
    hillshade: boolean;
    exaggeration: number;
    intensity: number;
    contours: boolean;
    /** Metres between contour lines. */
    contourInterval: number;
}

export interface GenerationRequest {
    name: string;
    area: MapArea;
    sourceId: string;
    /** Layer id -> switched on. */
    layers: Record<string, boolean>;
    terrain: TerrainOptions;
    /**
     * How levels below the detail zoom are drawn: 'scaled' shrinks the detail level's look (fine
     * lines, uncrowded), 'redrawn' uses the same line weights at every level (bolder, busier).
     */
    lowerLevels: 'scaled' | 'redrawn';
}

export interface GeneratedMap {
    name: string;
    file: Uint8Array;
    area: MapArea;
    tileCount: number;
    attribution: string;
    /** How long the generation took. */
    seconds: number;
}

/**
 * Downloaded data for one area, kept between runs so that changing the styling or the layer
 * selection does not download everything again.
 */
export interface DataCache {
    key: string;
    features: Map<string, FeaturesByLayer>;
    /** Keyed by `gridKey(grid)`: the array layout depends on the grid's origin and size. */
    elevation: Map<string, Float32Array>;
}

export const gridKey = (grid: TileGrid): string =>
    [grid.zoom, grid.tileX0, grid.tileY0, grid.columns, grid.rows].join(',');

export const createDataCache = (): DataCache => ({ key: '', features: new Map(), elevation: new Map() });

/** Reports a sub-task's 0..1 progress as a slice of the overall progress. */
const slice = (reporter: Reporter, from: number, to: number): Reporter => ({
    log: (message, level) => reporter.log(message, level),
    status: message => reporter.status(message),
    progress: fraction => reporter.progress(from + (to - from) * Math.max(0, Math.min(1, fraction))),
});

/** The layers that will be drawn, in drawing order, each with the sources it comes from. */
export function planLayers(
    selection: Record<string, boolean>,
    sourceId: string,
): { layer: LayerDefinition; sources: VectorSource[] }[] {
    return LAYERS.filter(layer => selection[layer.id])
        .map(layer => ({ layer, sources: sourcesForLayer(layer, sourceId) }))
        .filter(entry => entry.sources.length > 0);
}

export function composeAttribution(sources: VectorSource[], usesTerrain: boolean): string {
    return [...sources.map(source => source.attribution), ...(usesTerrain ? [TERRAIN_ATTRIBUTION] : [])].join('; ');
}

async function loadFeatures(
    plan: ReturnType<typeof planLayers>,
    frame: Frame,
    cache: DataCache,
    context: TaskContext,
    progressFrom: number,
    progressTo: number,
): Promise<FeaturesByLayer> {
    const wanted = new Map<VectorSource, string[]>();
    for (const { layer, sources } of plan) {
        for (const source of sources) wanted.set(source, [...(wanted.get(source) ?? []), layer.id]);
    }
    const bySource = new Map<string, FeaturesByLayer>();
    const share = (progressTo - progressFrom) / Math.max(1, wanted.size);
    let index = 0;
    for (const [source, layerIds] of wanted) {
        throwIfCancelled(context.signal);
        const from = progressFrom + share * index++;
        const cached = cache.features.get(source.id) ?? {};
        const missing = layerIds.filter(id => !(id in cached));
        if (!missing.length) {
            context.reporter.log(`${source.name}: reusing the data already downloaded`, 'success');
            bySource.set(source.id, cached);
        } else {
            const result = await source.fetch(frame, missing, { ...context, reporter: slice(context.reporter, from, from + share) });
            const merged = { ...cached, ...result.features };
            if (result.complete) cache.features.set(source.id, merged);
            bySource.set(source.id, merged);
        }
        context.reporter.progress(from + share);
    }
    const features: FeaturesByLayer = {};
    for (const { layer, sources } of plan) {
        features[layer.id] = sources.flatMap((source): Feature[] => bySource.get(source.id)?.[layer.id] ?? []);
    }
    return features;
}

const canvasToPng = (canvas: HTMLCanvasElement): Promise<Uint8Array> =>
    new Promise((resolve, reject) => {
        canvas.toBlob(blob => {
            if (!blob) reject(new Error('The browser could not encode a map tile'));
            else blob.arrayBuffer().then(buffer => resolve(new Uint8Array(buffer)), reject);
        }, 'image/png');
    });

/** Tiles are drawn in blocks of this many tiles a side, then cut up. */
const BLOCK_TILES = 4;

async function renderLevel(
    grid: TileGrid,
    frame: Frame,
    layers: LayerDefinition[],
    features: FeaturesByLayer,
    elevation: Float32Array | null,
    terrain: TerrainOptions,
    writer: MbtilesWriter,
    preview: HTMLCanvasElement | null,
    styleScale: number,
    context: TaskContext,
): Promise<void> {
    const transform = levelTransform(frame, grid);
    const shading: HillshadeOptions = {
        enabled: terrain.hillshade && elevation !== null,
        exaggeration: terrain.exaggeration,
        intensity: terrain.intensity,
    };
    const blockCanvas = document.createElement('canvas');
    const blockContext = blockCanvas.getContext('2d')!;
    const tileCanvas = document.createElement('canvas');
    tileCanvas.width = tileCanvas.height = TILE_SIZE;
    const tileContext = tileCanvas.getContext('2d')!;

    let previewContext: CanvasRenderingContext2D | null = null;
    let previewScale = 1;
    if (preview) {
        previewScale = Math.min(1, 2400 / grid.width);
        preview.width = Math.round(grid.width * previewScale);
        preview.height = Math.round(grid.height * previewScale);
        previewContext = preview.getContext('2d');
    }

    let done = 0;
    for (let blockY = 0; blockY < grid.rows; blockY += BLOCK_TILES) {
        for (let blockX = 0; blockX < grid.columns; blockX += BLOCK_TILES) {
            throwIfCancelled(context.signal);
            const columns = Math.min(BLOCK_TILES, grid.columns - blockX);
            const rows = Math.min(BLOCK_TILES, grid.rows - blockY);
            const x0 = blockX * TILE_SIZE;
            const y0 = blockY * TILE_SIZE;
            const width = columns * TILE_SIZE;
            const height = rows * TILE_SIZE;
            blockCanvas.width = width;
            blockCanvas.height = height;
            blockContext.putImageData(hillshade(elevation ?? new Float32Array(0), grid, x0, y0, width, height, shading), 0, 0);
            if (terrain.contours && elevation) {
                drawContours(blockContext, elevation, grid, x0, y0, width, height, terrain.contourInterval);
            }
            drawFeatures(blockContext, x0, y0, width, height, layers, features, transform, styleScale);
            previewContext?.drawImage(blockCanvas, x0 * previewScale, y0 * previewScale, width * previewScale, height * previewScale);
            for (let row = 0; row < rows; row++) {
                for (let column = 0; column < columns; column++) {
                    tileContext.clearRect(0, 0, TILE_SIZE, TILE_SIZE);
                    tileContext.drawImage(blockCanvas, column * TILE_SIZE, row * TILE_SIZE, TILE_SIZE, TILE_SIZE, 0, 0, TILE_SIZE, TILE_SIZE);
                    writer.addTile(grid.zoom, grid.tileX0 + blockX + column, grid.tileY0 + blockY + row, await canvasToPng(tileCanvas));
                    done++;
                }
            }
            context.reporter.progress(done / grid.tileCount);
            // Let the page repaint between blocks.
            await sleep(0);
        }
    }
}

export async function generateMap(
    request: GenerationRequest,
    SQL: SqlJsStatic,
    cache: DataCache,
    context: TaskContext,
    preview: HTMLCanvasElement | null = null,
): Promise<GeneratedMap> {
    const started = performance.now();
    const { reporter } = context;
    const { area, terrain } = request;
    const grids = tileGridsForArea(area);
    if (grids[0].tileCount > MAX_DETAIL_TILES) {
        throw new Error(`The area is too large for zoom ${area.maxZoom} (at most ${MAX_DETAIL_TILES} tiles)`);
    }
    const frame = frameForArea(area);
    if (cache.key !== frameKey(frame)) {
        cache.key = frameKey(frame);
        cache.features.clear();
        cache.elevation.clear();
    }
    const totalTiles = grids.reduce((sum, grid) => sum + grid.tileCount, 0);
    reporter.log(
        `Area: ${grids[0].columns}×${grids[0].rows} tiles at zoom ${area.maxZoom}` +
            (grids.length > 1 ? `, ${totalTiles} tiles over zoom ${area.minZoom}–${area.maxZoom}` : ''),
    );
    reporter.progress(0.02);

    const plan = planLayers(request.layers, request.sourceId);
    const features = await loadFeatures(plan, frame, cache, context, 0.02, 0.4);
    throwIfCancelled(context.signal);

    const usesTerrain = terrain.hillshade || terrain.contours;
    const usedSources = [...new Set(plan.flatMap(entry => entry.sources))];
    const attribution = composeAttribution(usedSources, usesTerrain);
    const layers = plan.map(entry => entry.layer);

    const writer = new MbtilesWriter(SQL, {
        name: request.name,
        description: request.name,
        attribution,
        // The detail level's tiles; lower levels reach a little further out.
        bounds: gridBounds(grids[0]),
        minZoom: area.minZoom,
        maxZoom: area.maxZoom,
    });
    try {
        let progress = 0.4;
        for (const grid of grids) {
            throwIfCancelled(context.signal);
            const share = (0.6 * grid.tileCount) / totalTiles;
            let elevation: Float32Array | null = null;
            if (usesTerrain) {
                elevation = cache.elevation.get(gridKey(grid)) ?? null;
                if (elevation) {
                    reporter.log(`Terrain for zoom ${grid.zoom}: reusing the data already downloaded`, 'success');
                } else {
                    const result = await fetchElevation(grid, {
                        ...context,
                        reporter: slice(reporter, progress, progress + share * 0.3),
                    });
                    elevation = result.values;
                    if (result.complete) cache.elevation.set(gridKey(grid), elevation);
                }
            }
            throwIfCancelled(context.signal);
            reporter.log(`Drawing zoom ${grid.zoom}: ${grid.tileCount} tiles…`);
            await renderLevel(
                grid,
                frame,
                layers,
                features,
                elevation,
                terrain,
                writer,
                grid === grids[0] ? preview : null,
                request.lowerLevels === 'scaled' ? 2 ** (grid.zoom - area.maxZoom) : 1,
                { ...context, reporter: slice(reporter, progress + share * 0.3, progress + share) },
            );
            progress += share;
        }
        const tileCount = writer.tileCount;
        const file = writer.finish();
        reporter.progress(1);
        return { name: request.name, file, area, tileCount, attribution, seconds: (performance.now() - started) / 1000 };
    } catch (error) {
        writer.discard();
        throw error;
    }
}
