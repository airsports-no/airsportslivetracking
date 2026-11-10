/**
 * Writes an MBTiles file (a SQLite database of map tiles) in memory.
 *
 * The SQLite engine (sql.js) is passed in rather than imported, so that the page can load its
 * WebAssembly lazily and the tests can use the Node build.
 */
import type { Database, SqlJsStatic, Statement } from 'sql.js';

import type { Bounds } from './tiles';

export interface MbtilesMetadata {
    name: string;
    description: string;
    attribution: string;
    /** The extent covered by the tiles. */
    bounds: Bounds;
    minZoom: number;
    maxZoom: number;
}

export const GENERATOR_NAME = 'Air Sports Live Tracking map builder';

export class MbtilesWriter {
    private database: Database;
    private insert: Statement;
    private count = 0;

    constructor(SQL: SqlJsStatic, metadata: MbtilesMetadata) {
        this.database = new SQL.Database();
        this.database.run(
            'CREATE TABLE metadata (name text, value text);' +
                'CREATE TABLE tiles (zoom_level integer, tile_column integer, tile_row integer, tile_data blob);' +
                'CREATE UNIQUE INDEX tile_index on tiles (zoom_level, tile_column, tile_row);',
        );
        const { bounds } = metadata;
        const rows: Record<string, string> = {
            name: metadata.name,
            type: 'baselayer',
            description: metadata.description,
            version: '1.1',
            format: 'png',
            minzoom: String(metadata.minZoom),
            maxzoom: String(metadata.maxZoom),
            bounds: [bounds.west, bounds.south, bounds.east, bounds.north].join(','),
            center: [(bounds.west + bounds.east) / 2, (bounds.south + bounds.north) / 2, metadata.maxZoom].join(','),
            attribution: metadata.attribution,
            generator: GENERATOR_NAME,
        };
        const statement = this.database.prepare('INSERT INTO metadata VALUES (?, ?)');
        for (const [name, value] of Object.entries(rows)) statement.run([name, value]);
        statement.free();
        this.database.run('BEGIN');
        this.insert = this.database.prepare('INSERT INTO tiles VALUES (?, ?, ?, ?)');
    }

    /** Adds a tile given in XYZ numbering (y grows southwards); MBTiles stores rows the TMS way. */
    addTile(zoom: number, x: number, y: number, image: Uint8Array): void {
        this.insert.run([zoom, x, 2 ** zoom - 1 - y, image]);
        this.count++;
    }

    get tileCount(): number {
        return this.count;
    }

    /** Returns the finished file and releases the database. */
    finish(): Uint8Array {
        this.insert.free();
        this.database.run('COMMIT');
        const file = this.database.export();
        this.database.close();
        return file;
    }

    /** Releases the database without producing a file (after an error or a cancellation). */
    discard(): void {
        try {
            this.insert.free();
            this.database.close();
        } catch {
            // Already closed.
        }
    }
}
