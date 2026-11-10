import initSqlJs from 'sql.js';
import type { SqlJsStatic } from 'sql.js';
import wasmUrl from 'sql.js/dist/sql-wasm.wasm?url';

let loading: Promise<SqlJsStatic> | null = null;

/** Loads the SQLite engine (WebAssembly) once; it is served from our own static files. */
export function loadSqlJs(): Promise<SqlJsStatic> {
    loading ??= initSqlJs({ locateFile: () => wasmUrl }).catch(error => {
        loading = null;
        throw error;
    });
    return loading;
}
