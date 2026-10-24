import { GateResult } from '../types';

/** Where a gate stands at a moment of the flight: crossed, missed, the next one to cross, or further ahead. */
export type GateState = 'crossed' | 'missed' | 'next' | 'ahead';

/**
 * Each gate's state at `now`, in route order. A gate counts as crossed once its actual time has come (so a replay
 * shows the flight as it was at the replay's time). A miss has no time of its own: it counts once a later gate has been
 * crossed, or at once when `missesKnown` (live, where the server says so as it happens, or at the end of a replay).
 * The next gate is the first after the last crossed or missed one.
 */
export function gateStates(results: GateResult[], now: Date, missesKnown = false): GateState[] {
    const crossed = results.map(r => r.actual !== null && new Date(r.actual) <= now);
    const lastCrossed = crossed.lastIndexOf(true);
    const states: GateState[] = results.map((r, i) => {
        if (crossed[i]) return 'crossed';
        if (r.missed && (missesKnown || i < lastCrossed)) return 'missed';
        return 'ahead';
    });
    const lastDone = Math.max(lastCrossed, states.lastIndexOf('missed'));
    const next = states.findIndex((s, i) => s === 'ahead' && i > lastDone);
    if (next >= 0) states[next] = 'next';
    return states;
}
