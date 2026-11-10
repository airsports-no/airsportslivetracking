/**
 * Shared reader for sources published as Mapbox Vector Tiles (MVT), which is how most national
 * mapping agencies publish their vector data. A source built on this only has to say where the
 * tiles are and how the provider's tile layers map onto our layer ids.
 */
import { LAYERS_BY_ID } from '../layers';
import type { Frame } from '../tiles';
import { TILE_SIZE } from '../tiles';
import type { Feature, FeaturesByLayer, TaskContext } from '../types';
import { ringArea, sleep, throwIfCancelled } from '../types';
import type { FetchResult } from './types';

export interface VectorTileRule {
    /** Names of the layers inside the vector tile that hold this element. */
    tileLayers: string[];
    /** Further selection on the feature's attributes. Omit to take everything in those layers. */
    match?(properties: Record<string, unknown>, tileLayer: string): boolean;
}

export interface VectorTileSourceOptions {
    /** Name used in the progress log. */
    label: string;
    tileUrl(zoom: number, x: number, y: number): string;
    /** Which tile zoom to download for a map whose detail zoom is `frameZoom`. */
    tileZoomFor(frameZoom: number): number;
    rules: Record<string, VectorTileRule>;
    /**
     * Some servers answer "no data here" with a 404 that lacks CORS headers, which a browser can
     * only see as a network failure. With this set, a repeated network failure counts as an
     * empty tile instead of an error.
     */
    networkErrorMeansEmpty?: boolean;
    concurrency?: number;
}

type XY = [number, number];

/** Clips a ring to a rectangle (Sutherland-Hodgman). Vector tiles carry a buffer beyond their edge. */
export function clipRing(points: XY[], minX: number, minY: number, maxX: number, maxY: number): XY[] {
    const edges: [(p: XY) => boolean, (a: XY, b: XY) => XY][] = [
        [p => p[0] >= minX, (a, b) => [minX, a[1] + ((b[1] - a[1]) * (minX - a[0])) / (b[0] - a[0])]],
        [p => p[0] <= maxX, (a, b) => [maxX, a[1] + ((b[1] - a[1]) * (maxX - a[0])) / (b[0] - a[0])]],
        [p => p[1] >= minY, (a, b) => [a[0] + ((b[0] - a[0]) * (minY - a[1])) / (b[1] - a[1]), minY]],
        [p => p[1] <= maxY, (a, b) => [a[0] + ((b[0] - a[0]) * (maxY - a[1])) / (b[1] - a[1]), maxY]],
    ];
    let output = points;
    for (const [isInside, intersection] of edges) {
        const input = output;
        output = [];
        if (!input.length) break;
        for (let i = 0; i < input.length; i++) {
            const previous = input[(i + input.length - 1) % input.length];
            const current = input[i];
            if (isInside(current)) {
                if (!isInside(previous)) output.push(intersection(previous, current));
                output.push(current);
            } else if (isInside(previous)) {
                output.push(intersection(previous, current));
            }
        }
    }
    return output;
}

export async function fetchVectorTiles(
    options: VectorTileSourceOptions,
    frame: Frame,
    context: TaskContext,
): Promise<FetchResult> {
    const { signal, reporter } = context;
    const [{ VectorTile }, { default: Pbf }] = await Promise.all([import('@mapbox/vector-tile'), import('pbf')]);

    const tileZoom = options.tileZoomFor(frame.zoom);
    // Size of one source tile in frame pixels.
    const tilePixels = TILE_SIZE * 2 ** (frame.zoom - tileZoom);
    const tileX0 = Math.floor(frame.originX / tilePixels);
    const tileY0 = Math.floor(frame.originY / tilePixels);
    const tileX1 = Math.ceil((frame.originX + frame.width) / tilePixels) - 1;
    const tileY1 = Math.ceil((frame.originY + frame.height) / tilePixels) - 1;
    const tiles: XY[] = [];
    for (let y = tileY0; y <= tileY1; y++) for (let x = tileX0; x <= tileX1; x++) tiles.push([x, y]);
    reporter.log(`Downloading ${options.label}: ${tiles.length} tiles…`);

    const layerIds = Object.keys(options.rules);
    const layersOfTileLayer = new Map<string, string[]>();
    for (const id of layerIds) {
        for (const tileLayer of options.rules[id].tileLayers) {
            layersOfTileLayer.set(tileLayer, [...(layersOfTileLayer.get(tileLayer) ?? []), id]);
        }
    }
    const features: FeaturesByLayer = Object.fromEntries(layerIds.map(id => [id, [] as Feature[]]));

    let done = 0, failed = 0, empty = 0, featureCount = 0, bytes = 0;

    async function download([x, y]: XY): Promise<ArrayBuffer | 'empty' | null> {
        for (let attempt = 0; attempt < 3; attempt++) {
            throwIfCancelled(signal);
            try {
                const response = await fetch(options.tileUrl(tileZoom, x, y), { signal });
                if (response.status === 404 || response.status === 204) return 'empty';
                if (!response.ok) throw new Error(String(response.status));
                return await response.arrayBuffer();
            } catch (error) {
                throwIfCancelled(signal);
                if (options.networkErrorMeansEmpty && error instanceof TypeError && attempt >= 1) return 'empty';
                await sleep(600 * (attempt + 1));
            }
        }
        return null;
    }

    async function readTile(tile: XY): Promise<void> {
        const buffer = await download(tile);
        if (buffer === 'empty') {
            empty++;
            return;
        }
        if (!buffer) {
            failed++;
            return;
        }
        bytes += buffer.byteLength;
        if (!buffer.byteLength) return;
        const vectorTile = new VectorTile(new Pbf(new Uint8Array(buffer)));
        // Where this tile sits in the frame.
        const offsetX = tile[0] * tilePixels - frame.originX;
        const offsetY = tile[1] * tilePixels - frame.originY;
        for (const [tileLayerName, ids] of layersOfTileLayer) {
            const tileLayer = vectorTile.layers[tileLayerName];
            if (!tileLayer) continue;
            const extent = tileLayer.extent;
            const scale = tilePixels / extent;
            for (let index = 0; index < tileLayer.length; index++) {
                const tileFeature = tileLayer.feature(index);
                const matching = ids.filter(id => options.rules[id].match?.(tileFeature.properties, tileLayerName) ?? true);
                if (!matching.length) continue;
                const geometry = tileFeature.loadGeometry();
                for (const id of matching) {
                    const layer = LAYERS_BY_ID[id];
                    if (layer.kind === 'point') {
                        // One symbol per object, at its centre, and only from the tile that
                        // contains the centre: objects reaching into the tile buffer appear in
                        // several tiles.
                        const points = geometry.flat();
                        if (!points.length) continue;
                        let centreX = 0, centreY = 0;
                        for (const point of points) {
                            centreX += point.x;
                            centreY += point.y;
                        }
                        centreX /= points.length;
                        centreY /= points.length;
                        if (centreX < 0 || centreY < 0 || centreX >= extent || centreY >= extent) continue;
                        const x = offsetX + centreX * scale;
                        const y = offsetY + centreY * scale;
                        features[id].push({ kind: 'point', point: [x, y], box: [x, y, x, y] });
                        featureCount++;
                    } else if (tileFeature.type === 3 && (layer.kind === 'fill' || layer.fillPolygons)) {
                        const rings: Float32Array[] = [];
                        for (const ring of geometry) {
                            const clipped = clipRing(ring.map(point => [point.x, point.y] as XY), 0, 0, extent, extent);
                            if (clipped.length < 3) continue;
                            const flat = new Float32Array(clipped.length * 2);
                            clipped.forEach((point, i) => {
                                flat[2 * i] = offsetX + point[0] * scale;
                                flat[2 * i + 1] = offsetY + point[1] * scale;
                            });
                            rings.push(flat);
                        }
                        if (!rings.length) continue;
                        if (layer.kind === 'fill' && layer.minimumArea) {
                            const area = Math.abs(rings.reduce((sum, ring) => sum + ringArea(ring), 0));
                            if (area < layer.minimumArea) continue;
                        }
                        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
                        for (const ring of rings) {
                            for (let i = 0; i < ring.length; i += 2) {
                                minX = Math.min(minX, ring[i]);
                                maxX = Math.max(maxX, ring[i]);
                                minY = Math.min(minY, ring[i + 1]);
                                maxY = Math.max(maxY, ring[i + 1]);
                            }
                        }
                        features[id].push({ kind: 'polygon', rings, box: [minX, minY, maxX, maxY] });
                        featureCount++;
                    } else if (layer.kind === 'line') {
                        for (const line of geometry) {
                            if (line.length < 2) continue;
                            const flat = new Float32Array(line.length * 2);
                            let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
                            line.forEach((point, i) => {
                                const x = offsetX + point.x * scale;
                                const y = offsetY + point.y * scale;
                                flat[2 * i] = x;
                                flat[2 * i + 1] = y;
                                if (x < minX) minX = x;
                                if (x > maxX) maxX = x;
                                if (y < minY) minY = y;
                                if (y > maxY) maxY = y;
                            });
                            features[id].push({ kind: 'line', line: flat, box: [minX, minY, maxX, maxY] });
                            featureCount++;
                        }
                    }
                }
            }
        }
    }

    const queue = [...tiles];
    const workers = Array.from({ length: options.concurrency ?? 6 }, async () => {
        for (let tile = queue.shift(); tile; tile = queue.shift()) {
            await readTile(tile);
            done++;
            if (done % 10 === 0) {
                reporter.progress(done / tiles.length);
                reporter.status(`${options.label}: ${done} of ${tiles.length} tiles (${(bytes / 1048576).toFixed(0)} MB)`);
            }
        }
    });
    await Promise.all(workers);
    reporter.status('');
    if (empty) reporter.log(`  ${empty} tiles have no data (open sea or outside the covered area)`);
    if (failed) {
        reporter.log(`  ${failed} tiles could not be downloaded; features will be missing in those places`, 'error');
    }
    reporter.log(`  ${featureCount.toLocaleString('en')} map features`, 'success');
    return { features, complete: failed === 0 };
}
