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

// A tracking source can partially backfill an outage with a handful of real
// (non-interpolated) fixes recovered after the fact (e.g. Traccar's own device
// buffer), each triggering its own short interpolated run against the previous
// point. That chops one genuine multi-point gap into several runs individually
// too short to qualify, so a real outage rendered solid. Bridging a lone real
// point between two interpolated runs treats them as one gap for length purposes,
// while 2+ consecutive real points still means normal tracking resumed.
const MAX_BRIDGE_REAL_POINTS = 1;
// Minimum number of interpolated points a (possibly bridged) run must contain
// before it's rendered dashed rather than solid.
const MIN_DASHED_RUN_LENGTH = 10;

export function splitSegments(positions: TrackPosition[]): { solid: [number, number][][], dashed: [number, number][][] } {
    const solid: [number, number][][] = [];
    const dashed: [number, number][][] = [];

    if (positions.length < 2) return { solid, dashed };

    const numSegments = positions.length - 1;
    const isSegmentDashed = new Array(numSegments).fill(false);

    // 1. Find raw runs of consecutive interpolated points.
    const runs: { start: number; end: number }[] = [];
    let j = 0;
    while (j < positions.length) {
        if (positions[j].interpolated) {
            let k = j;
            while (k < positions.length && positions[k].interpolated) {
                k++;
            }
            runs.push({ start: j, end: k });
            j = k;
        } else {
            j++;
        }
    }

    // 2. Merge runs separated by a small number of real (bridging) points into
    // a single cluster, so their interpolated-point counts combine for the
    // length check below instead of each being judged in isolation.
    const clusters: { start: number; end: number; interpolatedCount: number }[] = [];
    for (const run of runs) {
        const previousCluster = clusters[clusters.length - 1];
        if (previousCluster && run.start - previousCluster.end <= MAX_BRIDGE_REAL_POINTS) {
            previousCluster.end = run.end;
            previousCluster.interpolatedCount += run.end - run.start;
        } else {
            clusters.push({ start: run.start, end: run.end, interpolatedCount: run.end - run.start });
        }
    }

    // 3. Mark segments dashed for clusters whose combined interpolated-point
    // count reaches the threshold, including the connecting segments to the
    // adjacent real points.
    for (const cluster of clusters) {
        if (cluster.interpolatedCount >= MIN_DASHED_RUN_LENGTH) {
            for (let m = Math.max(0, cluster.start - 1); m < Math.min(numSegments, cluster.end); m++) {
                isSegmentDashed[m] = true;
            }
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
