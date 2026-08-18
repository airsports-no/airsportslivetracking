import { TrackPosition } from '../types';

// Split out of useMapLayers.ts, which does a top-level `import L from
// 'leaflet'` - that import touches `window` at module-load time, so it
// crashes outside a DOM. These three functions are pure and only need
// TrackPosition, so isolating them here lets them be imported and tested
// without a DOM.

export function hslColor(index: number, total: number): string {
    const hue = Math.round((index / Math.max(1, total)) * 360);
    return `hsl(${hue}, 70%, 50%)`;
}

export function lastMinutesPositions(all: TrackPosition[], minutes: number, currentTime: Date): TrackPosition[] {
    const cutoff = new Date(currentTime.getTime() - minutes * 60_000);
    return all.filter(p => new Date(p.time) >= cutoff);
}

export function splitSegments(positions: TrackPosition[]): { solid: [number, number][][], dashed: [number, number][][] } {
    const solid: [number, number][][] = [];
    const dashed: [number, number][][] = [];

    if (positions.length < 2) return { solid, dashed };

    const numSegments = positions.length - 1;
    const isSegmentDashed = new Array(numSegments).fill(false);

    // Identify runs of interpolated points that are at least 10 points long.
    // A run of points P_j...P_{j+k-1} has length k.
    let j = 0;
    while (j < positions.length) {
        if (positions[j].interpolated) {
            let k = j;
            while (k < positions.length && positions[k].interpolated) {
                k++;
            }
            const runLength = k - j;
            if (runLength >= 10) {
                // If the run of interpolated points is >= 10,
                // mark all segments connecting them (and to adjacent real points) as dashed.
                for (let m = Math.max(0, j - 1); m < Math.min(numSegments, k); m++) {
                    isSegmentDashed[m] = true;
                }
            }
            j = k;
        } else {
            j++;
        }
    }

    let currentSolid: [number, number][] = [];
    let currentDashed: [number, number][] = [];

    for (let i = 0; i < numSegments; i++) {
        const p1 = positions[i];
        const p2 = positions[i+1];

        if (isSegmentDashed[i]) {
            if (currentSolid.length > 1) {
                solid.push(currentSolid);
            }
            currentSolid = [];

            if (currentDashed.length === 0) {
                currentDashed.push([p1.latitude, p1.longitude]);
            }
            currentDashed.push([p2.latitude, p2.longitude]);
        } else {
            if (currentDashed.length > 1) {
                dashed.push(currentDashed);
            }
            currentDashed = [];

            if (currentSolid.length === 0) {
                currentSolid.push([p1.latitude, p1.longitude]);
            }
            currentSolid.push([p2.latitude, p2.longitude]);
        }
    }

    if (currentSolid.length > 1) solid.push(currentSolid);
    if (currentDashed.length > 1) dashed.push(currentDashed);

    return { solid, dashed };
}
