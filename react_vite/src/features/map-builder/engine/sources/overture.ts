/**
 * OpenStreetMap, worldwide, read from the Overture Maps Foundation's open data release.
 *
 * Overture republishes OpenStreetMap as GeoParquet files in a public Amazon S3 bucket (AWS Open
 * Data programme: no account, no key, no request quota). The files are spatially sorted and carry
 * per-block bounding boxes, so the browser only downloads the blocks that touch the selected area
 * using HTTP range requests - there is no tile server or API in between.
 */
import type { AsyncBuffer, FileMetaData } from 'hyparquet';
import type { Geometry, Position } from 'geojson';

import { LAYERS_BY_ID } from '../layers';
import type { Frame } from '../tiles';
import { latitudeToPixel, longitudeToPixel } from '../tiles';
import type { Feature, FeaturesByLayer, PixelBox, TaskContext } from '../types';
import { boxesIntersect, ringArea, sleep, throwIfCancelled } from '../types';
import type { VectorSource } from './types';

const STAC_ROOT = 'https://stac.overturemaps.org';

type OvertureType = 'segment' | 'water' | 'land' | 'land_use' | 'infrastructure';

const THEME_OF_TYPE: Record<OvertureType, string> = {
    segment: 'transportation',
    water: 'base',
    land: 'base',
    land_use: 'base',
    infrastructure: 'base',
};

const TYPE_DESCRIPTION: Record<OvertureType, string> = {
    segment: 'roads and railways',
    water: 'water',
    land: 'forests and peaks',
    land_use: 'land use',
    infrastructure: 'infrastructure',
};

interface OvertureRow {
    subtype?: string | null;
    class?: string | null;
    geometry?: Geometry | null;
    source_tags?: unknown;
}

interface LayerRule {
    type: OvertureType;
    /** The rule reads the original OpenStreetMap tags, which is an extra column to download. */
    needsTags?: boolean;
    match(row: OvertureRow): boolean;
}

const oneOf = (value: string | null | undefined, ...options: string[]): boolean => options.includes(value ?? '');

/** Reads an original OpenStreetMap tag; the column arrives in different shapes depending on the release. */
export function sourceTag(row: OvertureRow, key: string): string | undefined {
    const tags = row.source_tags;
    if (!tags) return undefined;
    if (tags instanceof Map) return tags.get(key);
    if (Array.isArray(tags)) {
        const entry = tags.find(item => item && (item.key === key || item[0] === key));
        return entry ? (entry.value ?? entry[1]) : undefined;
    }
    return (tags as Record<string, string>)[key];
}

const road = (...classes: string[]) => (row: OvertureRow) => row.subtype === 'road' && oneOf(row.class, ...classes);

export const OVERTURE_RULES: Record<string, LayerRule> = {
    sea: { type: 'water', match: row => row.subtype === 'ocean' || oneOf(row.class, 'ocean', 'sea') },
    forest: { type: 'land', match: row => row.subtype === 'forest' },
    built_up: {
        type: 'land_use',
        match: row => row.subtype === 'residential' || (row.subtype === 'developed' && oneOf(row.class, 'commercial', 'retail')),
    },
    industrial: { type: 'land_use', match: row => row.class === 'industrial' },
    quarry: { type: 'land_use', match: row => row.class === 'quarry' },
    solar_farm: {
        type: 'infrastructure',
        needsTags: true,
        match: row =>
            (row.class === 'generator' && sourceTag(row, 'generator:source') === 'solar') ||
            (row.class === 'plant' && sourceTag(row, 'plant:source') === 'solar'),
    },
    lake: {
        type: 'water',
        match: row =>
            oneOf(row.subtype, 'reservoir', 'lake', 'water', 'river', 'pond') &&
            !oneOf(row.class, 'swimming_pool', 'reflecting_pool', 'fish_pass'),
    },
    stream: { type: 'water', match: row => row.subtype === 'stream' },
    canal: { type: 'water', match: row => row.subtype === 'canal' && row.class === 'canal' },
    river: { type: 'water', match: row => row.subtype === 'river' },
    dam: { type: 'infrastructure', match: row => row.class === 'dam' },
    track: { type: 'segment', match: road('track') },
    local_road: { type: 'segment', match: road('unclassified', 'residential', 'living_street') },
    tertiary_road: { type: 'segment', match: road('tertiary') },
    secondary_road: { type: 'segment', match: road('secondary') },
    primary_road: { type: 'segment', match: road('primary') },
    motorway: { type: 'segment', match: road('motorway', 'trunk') },
    railway: {
        type: 'segment',
        match: row => row.subtype === 'rail' && oneOf(row.class, 'standard_gauge', 'narrow_gauge', 'unknown'),
    },
    power_line: { type: 'infrastructure', match: row => row.class === 'power_line' },
    minor_power_line: { type: 'infrastructure', match: row => row.class === 'minor_line' },
    runway: { type: 'infrastructure', match: row => row.class === 'runway' },
    aerodrome: {
        type: 'infrastructure',
        match: row => row.subtype === 'airport' && /airport$|^airstrip$|^aerodrome$/.test(row.class ?? ''),
    },
    peak: { type: 'land', match: row => row.class === 'peak' },
    mast: { type: 'infrastructure', match: row => oneOf(row.class, 'communication_tower', 'mobile_phone_tower') },
    castle: { type: 'infrastructure', match: row => row.class === 'defensive' },
    wind_turbine: {
        type: 'infrastructure',
        needsTags: true,
        match: row => row.class === 'generator' && sourceTag(row, 'generator:source') === 'wind',
    },
};

/** Fetches JSON with a few retries: the catalogue is a set of small static files, failures are transient. */
async function fetchJson(url: string, signal: AbortSignal): Promise<any> {
    for (let attempt = 0; attempt < 3; attempt++) {
        throwIfCancelled(signal);
        try {
            const response = await fetch(url, { signal });
            if (response.ok) return await response.json();
        } catch {
            throwIfCancelled(signal);
        }
        await sleep(1000 * (attempt + 1));
    }
    throw new Error(`Could not read ${url}`);
}

/** The GeoParquet files of one Overture type whose extent touches the box (west, south, east, north). */
async function filesForType(release: string, type: OvertureType, box: number[], signal: AbortSignal): Promise<string[]> {
    const base = `${STAC_ROOT}/${release}/${THEME_OF_TYPE[type]}/${type}/`;
    const collection = await fetchJson(`${base}collection.json`, signal);
    const items: { href: string }[] = collection.links.filter((link: { rel: string }) => link.rel === 'item');
    // The collection lists the overall extent first and then one box per item, which lets most
    // items be ruled out without fetching them.
    const extents: number[][] = collection.extent?.spatial?.bbox ?? [];
    const candidates =
        extents.length === items.length + 1 ? items.filter((_, index) => boxesIntersect(extents[index + 1], box)) : items;
    const urls: string[] = [];
    for (const item of candidates) {
        const description = await fetchJson(new URL(item.href, base).href, signal);
        if (boxesIntersect(description.bbox, box)) urls.push(description.assets.aws.href);
    }
    return urls;
}

interface ReadTask {
    type: OvertureType;
    file: AsyncBuffer;
    metadata: FileMetaData;
    rowStart: number;
    rowEnd: number;
    megabytes: number;
}

const linesOf = (geometry: Geometry): Position[][] => {
    switch (geometry.type) {
        case 'LineString':
            return [geometry.coordinates];
        case 'MultiLineString':
            return geometry.coordinates;
        case 'Polygon':
            return [geometry.coordinates[0]];
        case 'MultiPolygon':
            return geometry.coordinates.map(polygon => polygon[0]);
        default:
            return [];
    }
};

const polygonsOf = (geometry: Geometry): Position[][][] =>
    geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.type === 'MultiPolygon' ? geometry.coordinates : [];

async function fetchOverture(frame: Frame, requestedLayerIds: string[], context: TaskContext) {
    const { signal, reporter } = context;
    const { asyncBufferFromUrl, parquetMetadataAsync, parquetReadObjects } = await import('hyparquet');
    const { compressors } = await import('hyparquet-compressors');

    // Every layer that lives in the same Overture files comes along for free, switched on or not.
    const types = new Set(requestedLayerIds.map(id => OVERTURE_RULES[id].type));
    const layerIds = Object.keys(OVERTURE_RULES).filter(id => types.has(OVERTURE_RULES[id].type));
    const layersOfType = new Map<OvertureType, string[]>();
    for (const id of layerIds) {
        const type = OVERTURE_RULES[id].type;
        layersOfType.set(type, [...(layersOfType.get(type) ?? []), id]);
    }

    const release: string = (await fetchJson(`${STAC_ROOT}/catalog.json`, signal)).latest;
    reporter.log(`OpenStreetMap data: Overture Maps release ${release}`);

    const { bounds, zoom } = frame;
    const box = [bounds.west, bounds.south, bounds.east, bounds.north];

    // 1) Find the files, and the blocks (row groups) inside them, that touch the area.
    const tasks: ReadTask[] = [];
    let totalMegabytes = 0;
    for (const type of layersOfType.keys()) {
        throwIfCancelled(signal);
        for (const url of await filesForType(release, type, box, signal)) {
            const file = await asyncBufferFromUrl({ url, requestInit: { signal } });
            const metadata = await parquetMetadataAsync(file);
            let rowStart = 0;
            for (const rowGroup of metadata.row_groups) {
                const columns: Record<string, any> = {};
                for (const column of rowGroup.columns) {
                    if (column.meta_data) columns[column.meta_data.path_in_schema.join('.')] = column.meta_data;
                }
                const statistic = (name: string, bound: 'min_value' | 'max_value'): number => {
                    const value = columns[name]?.statistics?.[bound];
                    return value === undefined || value === null ? NaN : Number(value);
                };
                const groupBox = [
                    statistic('bbox.xmin', 'min_value'),
                    statistic('bbox.ymin', 'min_value'),
                    statistic('bbox.xmax', 'max_value'),
                    statistic('bbox.ymax', 'max_value'),
                ];
                const rows = Number(rowGroup.num_rows);
                // A block without usable statistics has to be read to find out.
                if (groupBox.some(Number.isNaN) || boxesIntersect(groupBox, box)) {
                    const megabytes =
                        ['geometry', 'subtype', 'class'].reduce(
                            (sum, name) => sum + Number(columns[name]?.total_compressed_size ?? 0),
                            0,
                        ) / 1048576;
                    tasks.push({ type, file, metadata, rowStart, rowEnd: rowStart + rows, megabytes });
                    totalMegabytes += megabytes;
                }
                rowStart += rows;
            }
        }
    }
    reporter.log(`  ${tasks.length} data blocks, about ${totalMegabytes.toFixed(0)} MB to download`);

    // 2) Read each block and turn the matching rows into drawable features.
    const margin = 40;
    const inside = (b: PixelBox) =>
        !(b[2] < -margin || b[0] > frame.width + margin || b[3] < -margin || b[1] > frame.height + margin);
    const project = (coordinates: Position[]): { flat: Float32Array; box: PixelBox } => {
        const flat = new Float32Array(coordinates.length * 2);
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        for (let i = 0; i < coordinates.length; i++) {
            const x = longitudeToPixel(coordinates[i][0], zoom) - frame.originX;
            const y = latitudeToPixel(coordinates[i][1], zoom) - frame.originY;
            flat[2 * i] = x;
            flat[2 * i + 1] = y;
            if (x < minX) minX = x;
            if (x > maxX) maxX = x;
            if (y < minY) minY = y;
            if (y > maxY) maxY = y;
        }
        return { flat, box: [minX, minY, maxX, maxY] };
    };

    const features: FeaturesByLayer = Object.fromEntries(layerIds.map(id => [id, [] as Feature[]]));
    let doneMegabytes = 0;
    let featureCount = 0;
    let previousType: OvertureType | null = null;
    for (const task of tasks) {
        throwIfCancelled(signal);
        if (task.type !== previousType) {
            previousType = task.type;
            reporter.log(`Downloading ${TYPE_DESCRIPTION[task.type]}…`);
        }
        const layers = layersOfType.get(task.type) ?? [];
        const columns = ['subtype', 'class', 'geometry'];
        if (layers.some(id => OVERTURE_RULES[id].needsTags)) columns.push('source_tags');

        let rows: OvertureRow[] = [];
        for (let attempt = 0; ; attempt++) {
            try {
                rows = (await parquetReadObjects({
                    file: task.file,
                    metadata: task.metadata,
                    columns,
                    rowStart: task.rowStart,
                    rowEnd: task.rowEnd,
                    compressors,
                })) as OvertureRow[];
                break;
            } catch (error) {
                throwIfCancelled(signal);
                if (attempt === 2) {
                    throw new Error(`Could not download the OpenStreetMap data (${(error as Error).message})`);
                }
                await sleep(2000 * (attempt + 1));
            }
        }

        for (const row of rows) {
            const geometry = row.geometry;
            if (!geometry) continue;
            for (const id of layers) {
                if (!OVERTURE_RULES[id].match(row)) continue;
                const layer = LAYERS_BY_ID[id];
                if (layer.kind === 'point') {
                    let longitude: number, latitude: number;
                    if (geometry.type === 'Point') {
                        [longitude, latitude] = geometry.coordinates;
                    } else {
                        const coordinates = linesOf(geometry).flat();
                        if (!coordinates.length) continue;
                        longitude = coordinates.reduce((sum, c) => sum + c[0], 0) / coordinates.length;
                        latitude = coordinates.reduce((sum, c) => sum + c[1], 0) / coordinates.length;
                    }
                    const x = longitudeToPixel(longitude, zoom) - frame.originX;
                    const y = latitudeToPixel(latitude, zoom) - frame.originY;
                    const pointBox: PixelBox = [x, y, x, y];
                    if (!inside(pointBox)) continue;
                    features[id].push({ kind: 'point', point: [x, y], box: pointBox });
                    featureCount++;
                } else if (layer.kind === 'line') {
                    for (const coordinates of linesOf(geometry)) {
                        if (coordinates.length < 2) continue;
                        const { flat, box: lineBox } = project(coordinates);
                        if (!inside(lineBox)) continue;
                        features[id].push({ kind: 'line', line: flat, box: lineBox });
                        featureCount++;
                    }
                } else {
                    for (const polygon of polygonsOf(geometry)) {
                        const rings = polygon.map(project);
                        if (!rings.length) continue;
                        if (layer.minimumArea && Math.abs(ringArea(rings[0].flat)) < layer.minimumArea) continue;
                        const polygonBox: PixelBox = [
                            Math.min(...rings.map(ring => ring.box[0])),
                            Math.min(...rings.map(ring => ring.box[1])),
                            Math.max(...rings.map(ring => ring.box[2])),
                            Math.max(...rings.map(ring => ring.box[3])),
                        ];
                        if (!inside(polygonBox)) continue;
                        features[id].push({ kind: 'polygon', rings: rings.map(ring => ring.flat), box: polygonBox });
                        featureCount++;
                    }
                }
            }
        }

        doneMegabytes += task.megabytes;
        reporter.progress(doneMegabytes / Math.max(totalMegabytes, 1e-6));
        reporter.status(`${doneMegabytes.toFixed(0)} of ${totalMegabytes.toFixed(0)} MB processed`);
        // Let the page repaint between blocks.
        await sleep(0);
    }
    reporter.status('');
    reporter.log(`  ${featureCount.toLocaleString('en')} map features`, 'success');
    return { features, complete: true };
}

export const overtureSource: VectorSource = {
    id: 'osm',
    name: 'OpenStreetMap (worldwide)',
    shortName: 'OSM',
    description: 'Community-maintained map of the whole world, read from the Overture Maps open data release.',
    attribution: '© OpenStreetMap contributors (ODbL)',
    covers: () => true,
    layerIds: new Set(Object.keys(OVERTURE_RULES)),
    fetch: fetchOverture,
};
