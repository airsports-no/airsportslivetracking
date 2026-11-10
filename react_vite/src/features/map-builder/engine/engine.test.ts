import initSqlJs from 'sql.js';

import { composeAttribution, gridKey, planLayers, tileKey } from './generate';
import { LAYERS_BY_ID, defaultLayerSelection } from './layers';
import { MbtilesWriter } from './mbtiles';
import { levelTransform } from './render';
import { BASE_SOURCE, preferredSourceId, sourcesCovering, sourcesForLayer } from './sources';
import { isInSpain } from './sources/ignSpain';
import { sourceTag } from './sources/overture';
import { clipRing } from './sources/vectorTiles';
import {
    MAX_DETAIL_TILES,
    SAMPLE_SIDE_TILES,
    TILE_SIZE,
    frameForArea,
    gridBounds,
    latitudeToPixel,
    longitudeToPixel,
    pixelToLatitude,
    pixelToLongitude,
    sampleBounds,
    summariseArea,
    tileGridForBounds,
    tileGridsForArea,
} from './tiles';

const OSLO = { west: 10.5, south: 59.8, east: 11.0, north: 60.0 };
const VALENCIA = { west: -0.6, south: 39.4, east: -0.3, north: 39.6 };

describe('tile maths', () => {
    it('round-trips coordinates through pixels', () => {
        expect(pixelToLongitude(longitudeToPixel(10.75, 13), 13)).toBeCloseTo(10.75, 9);
        expect(pixelToLatitude(latitudeToPixel(59.9, 13), 13)).toBeCloseTo(59.9, 9);
    });

    it('covers the requested bounds with whole tiles', () => {
        const grid = tileGridForBounds(OSLO, 13);
        const covered = gridBounds(grid);
        expect(covered.west).toBeLessThanOrEqual(OSLO.west);
        expect(covered.east).toBeGreaterThanOrEqual(OSLO.east);
        expect(covered.south).toBeLessThanOrEqual(OSLO.south);
        expect(covered.north).toBeGreaterThanOrEqual(OSLO.north);
        expect(grid.tileCount).toBe(grid.columns * grid.rows);
        expect(grid.width).toBe(grid.columns * TILE_SIZE);
    });

    it('lists one grid per zoom level, detail level first', () => {
        const grids = tileGridsForArea({ bounds: OSLO, minZoom: 11, maxZoom: 13 });
        expect(grids.map(grid => grid.zoom)).toEqual([13, 12, 11]);
        expect(grids[0].tileCount).toBeGreaterThan(grids[2].tileCount);
    });

    it('fetches data for the extent of the coarsest level, in detail-zoom pixels', () => {
        const area = { bounds: OSLO, minZoom: 11, maxZoom: 13 };
        const frame = frameForArea(area);
        const coarsest = tileGridForBounds(OSLO, 11);
        expect(frame.zoom).toBe(13);
        expect(frame.originX).toBe(coarsest.tileX0 * TILE_SIZE * 4);
        expect(frame.width).toBe(coarsest.width * 4);
        // Every level's grid lies inside the frame.
        for (const grid of tileGridsForArea(area)) {
            const transform = levelTransform(frame, grid);
            expect(transform.offsetX).toBeLessThanOrEqual(0);
            expect(transform.offsetY).toBeLessThanOrEqual(0);
            expect(frame.width * transform.scale + transform.offsetX).toBeGreaterThanOrEqual(grid.width);
            expect(frame.height * transform.scale + transform.offsetY).toBeGreaterThanOrEqual(grid.height);
        }
    });

    it('flags areas with too many detail tiles', () => {
        expect(summariseArea({ bounds: OSLO, minZoom: 12, maxZoom: 13 }).tooLarge).toBe(false);
        const huge = summariseArea({ bounds: { west: 5, south: 58, east: 12, north: 62 }, minZoom: 13, maxZoom: 13 });
        expect(huge.detailGrid.tileCount).toBeGreaterThan(MAX_DETAIL_TILES);
        expect(huge.tooLarge).toBe(true);
    });

    it('shrinks a large area to a small centered sample patch of at most 3x3 detail tiles', () => {
        const sample = sampleBounds(OSLO, 13);
        expect(sample.west).toBeGreaterThanOrEqual(OSLO.west);
        expect(sample.east).toBeLessThanOrEqual(OSLO.east);
        expect(sample.south).toBeGreaterThanOrEqual(OSLO.south);
        expect(sample.north).toBeLessThanOrEqual(OSLO.north);
        const grid = tileGridForBounds(sample, 13);
        expect(grid.columns).toBeLessThanOrEqual(SAMPLE_SIDE_TILES);
        expect(grid.rows).toBeLessThanOrEqual(SAMPLE_SIDE_TILES);
        // An area already within 3x3 tiles is returned unchanged
        expect(sampleBounds(sample, 13)).toEqual(sample);
        expect(tileKey(13, 4335, 2378)).toBe('13/4335/2378');
    });
});

describe('data cache keys', () => {
    it('tells apart grids of the same zoom that start elsewhere, even when the coarsest frame is the same', () => {
        const area = { bounds: OSLO, minZoom: 11, maxZoom: 13 };
        const shifted = { ...area, bounds: { ...OSLO, west: OSLO.west + 0.03 } };
        expect(frameForArea(shifted)).toEqual(frameForArea(area));
        const before = tileGridsForArea(area)[0];
        const after = tileGridsForArea(shifted)[0];
        expect(gridKey(after)).not.toBe(gridKey(before));
        expect(gridKey(before)).toBe(gridKey(tileGridsForArea(area)[0]));
    });
});

describe('data sources', () => {
    it('offers the Spanish source only in Spain', () => {
        expect(isInSpain(VALENCIA)).toBe(true);
        expect(isInSpain({ west: 2.9, south: 39.5, east: 3.1, north: 39.7 })).toBe(true); // Mallorca
        expect(isInSpain(OSLO)).toBe(false);
        expect(isInSpain({ west: -9.2, south: 38.6, east: -9.0, north: 38.8 })).toBe(false); // Lisbon
        expect(sourcesCovering(OSLO).map(source => source.id)).toEqual(['osm']);
        expect(sourcesCovering(VALENCIA).map(source => source.id)).toEqual(['osm', 'ign-es']);
    });

    it('prefers the regional source unless the user chose otherwise', () => {
        expect(preferredSourceId(VALENCIA, null)).toBe('ign-es');
        expect(preferredSourceId(VALENCIA, 'osm')).toBe('osm');
        expect(preferredSourceId(OSLO, 'ign-es')).toBe('osm');
    });

    it('fills in from OpenStreetMap and combines sources for aviation features', () => {
        const ids = (layerId: string, sourceId: string) => sourcesForLayer(LAYERS_BY_ID[layerId], sourceId).map(s => s.id);
        expect(ids('motorway', 'ign-es')).toEqual(['ign-es']);
        expect(ids('wind_turbine', 'ign-es')).toEqual(['osm']);
        expect(ids('runway', 'ign-es')).toEqual(['ign-es', 'osm']);
        expect(ids('church', 'ign-es')).toEqual(['ign-es']);
        expect(ids('church', 'osm')).toEqual([]);
        expect(ids('motorway', 'osm')).toEqual(['osm']);
    });

    it('leaves out layers that do not exist with the chosen source', () => {
        const selection = { ...defaultLayerSelection(), church: true };
        expect(planLayers(selection, 'osm').some(entry => entry.layer.id === 'church')).toBe(false);
        expect(planLayers(selection, 'ign-es').some(entry => entry.layer.id === 'church')).toBe(true);
    });

    it('keeps the attribution within the length the server stores', () => {
        const all = composeAttribution([sourcesForLayer(LAYERS_BY_ID.runway, 'ign-es')].flat(), true);
        expect(all).toContain('OpenStreetMap');
        expect(all).toContain('IGN');
        expect(all.length).toBeLessThanOrEqual(100);
        expect(composeAttribution([BASE_SOURCE], false)).toBe('© OpenStreetMap contributors (ODbL)');
    });

    it('reads OpenStreetMap tags in every shape Overture has used', () => {
        expect(sourceTag({ source_tags: { 'generator:source': 'wind' } }, 'generator:source')).toBe('wind');
        expect(sourceTag({ source_tags: new Map([['generator:source', 'solar']]) }, 'generator:source')).toBe('solar');
        expect(sourceTag({ source_tags: [{ key: 'generator:source', value: 'wind' }] }, 'generator:source')).toBe('wind');
        expect(sourceTag({ source_tags: [['generator:source', 'wind']] }, 'generator:source')).toBe('wind');
        expect(sourceTag({}, 'generator:source')).toBeUndefined();
    });

    it('clips polygon rings to the tile', () => {
        const clipped = clipRing([[-10, -10], [20, -10], [20, 20], [-10, 20]], 0, 0, 10, 10);
        expect(clipped.every(([x, y]) => x >= 0 && x <= 10 && y >= 0 && y <= 10)).toBe(true);
        expect(clipped.length).toBe(4);
        expect(clipRing([[20, 20], [30, 20], [30, 30]], 0, 0, 10, 10)).toEqual([]);
    });
});

describe('MBTiles writer', () => {
    it('writes metadata and tiles with TMS row numbering', async () => {
        const SQL = await initSqlJs();
        const writer = new MbtilesWriter(SQL, {
            name: 'Test map',
            description: 'Test map',
            attribution: '© OpenStreetMap contributors (ODbL)',
            bounds: OSLO,
            minZoom: 12,
            maxZoom: 13,
        });
        writer.addTile(13, 4335, 2378, new Uint8Array([1, 2, 3]));
        writer.addTile(12, 2167, 1189, new Uint8Array([4]));
        expect(writer.tileCount).toBe(2);
        const file = writer.finish();

        const database = new SQL.Database(file);
        const metadata = Object.fromEntries(database.exec('SELECT name, value FROM metadata')[0].values);
        expect(metadata).toMatchObject({
            name: 'Test map',
            format: 'png',
            minzoom: '12',
            maxzoom: '13',
            bounds: '10.5,59.8,11,60',
            attribution: '© OpenStreetMap contributors (ODbL)',
        });
        const rows = database.exec('SELECT zoom_level, tile_column, tile_row, tile_data FROM tiles ORDER BY zoom_level DESC')[0].values;
        expect(rows[0].slice(0, 3)).toEqual([13, 4335, 2 ** 13 - 1 - 2378]);
        expect(Array.from(rows[0][3] as Uint8Array)).toEqual([1, 2, 3]);
        database.close();
    });
});
