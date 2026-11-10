/** A rectangle in frame pixels: [minX, minY, maxX, maxY]. */
export type PixelBox = [number, number, number, number];

/**
 * A drawable feature in frame pixels (see `Frame` in tiles.ts). Coordinates are flat
 * `[x0, y0, x1, y1, ...]` arrays.
 */
export type Feature =
    | { kind: 'point'; point: [number, number]; box: PixelBox }
    | { kind: 'line'; line: Float32Array; box: PixelBox }
    | { kind: 'polygon'; rings: Float32Array[]; box: PixelBox };

/** Features keyed by layer id. */
export type FeaturesByLayer = Record<string, Feature[]>;

export type LogLevel = 'info' | 'success' | 'warning' | 'error';

/** How the engine tells the page what it is doing. */
export interface Reporter {
    log(message: string, level?: LogLevel): void;
    /** Overall progress, 0..1. */
    progress(fraction: number): void;
    /** A transient one-line status ("12 of 80 MB processed"); empty string clears it. */
    status(message: string): void;
}

export interface TaskContext {
    signal: AbortSignal;
    reporter: Reporter;
}

export class CancelledError extends Error {
    constructor() {
        super('Cancelled');
        this.name = 'CancelledError';
    }
}

export function throwIfCancelled(signal: AbortSignal): void {
    if (signal.aborted) throw new CancelledError();
}

export const sleep = (milliseconds: number): Promise<void> => new Promise(resolve => setTimeout(resolve, milliseconds));

/** Signed area of a flat ring, in square pixels. */
export function ringArea(ring: ArrayLike<number>): number {
    let sum = 0;
    for (let i = 0, n = ring.length; i < n; i += 2) {
        const j = (i + 2) % n;
        sum += ring[i] * ring[j + 1] - ring[j] * ring[i + 1];
    }
    return sum / 2;
}

export const boxesIntersect = (a: ArrayLike<number>, b: ArrayLike<number>): boolean =>
    !(a[2] < b[0] || a[0] > b[2] || a[3] < b[1] || a[1] > b[3]);
