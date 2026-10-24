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
    return gateStatesIn(results, now, missesKnown, true);
}

/**
 * The gates in the order they were crossed, for tasks where the pilot chooses the order (turnpoint hunt): crossed ones
 * by their time, then the rest in route order. No gate is "next", as the route does not say which one comes next.
 */
export function inCrossingOrder(results: GateResult[], now: Date, missesKnown = false): { result: GateResult; state: GateState }[] {
    const states = gateStatesIn(results, now, missesKnown, false);
    const rows = results.map((result, i) => ({ result, state: states[i], i }));
    const crossedAt = (r: { result: GateResult; state: GateState }) =>
        r.state === 'crossed' ? new Date(r.result.actual!).getTime() : Infinity;
    return rows.sort((a, b) => crossedAt(a) - crossedAt(b) || a.i - b.i).map(({ result, state }) => ({ result, state }));
}

function gateStatesIn(results: GateResult[], now: Date, missesKnown: boolean, routeOrder: boolean): GateState[] {
    const crossed = results.map(r => r.actual !== null && new Date(r.actual) <= now);
    const lastCrossed = crossed.lastIndexOf(true);
    const states: GateState[] = results.map((r, i) => {
        if (crossed[i]) return 'crossed';
        if (r.missed && (missesKnown || i < lastCrossed)) return 'missed';
        return 'ahead';
    });
    if (!routeOrder) return states;
    const lastDone = Math.max(lastCrossed, states.lastIndexOf('missed'));
    const next = states.findIndex((s, i) => s === 'ahead' && i > lastDone);
    if (next >= 0) states[next] = 'next';
    return states;
}
