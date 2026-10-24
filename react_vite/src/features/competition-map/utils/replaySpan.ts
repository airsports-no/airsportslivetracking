/** A replay's span: from the start to the end time, both included. */
export interface ReplaySpan {
    start: Date;
    end: Date;
}

/** Margin around one contestant's flight, so the replay starts just before their first position and ends just after. */
const FLIGHT_MARGIN_MS = 60_000;

/**
 * The span of one contestant's flight, from their first position to their last with a minute either side, or null when
 * they have no positions. Positions arrive sorted, but the first and last are looked up rather than assumed.
 */
export function flightSpan(positions: { time: string }[] | undefined): ReplaySpan | null {
    if (!positions || positions.length === 0) return null;
    let first = Infinity;
    let last = -Infinity;
    for (const p of positions) {
        const t = new Date(p.time).getTime();
        if (t < first) first = t;
        if (t > last) last = t;
    }
    return { start: new Date(first - FLIGHT_MARGIN_MS), end: new Date(last + FLIGHT_MARGIN_MS) };
}

/** The time moved into the span (unchanged when inside it). */
export function clampToSpan(time: Date, span: ReplaySpan): Date {
    if (time < span.start) return span.start;
    if (time > span.end) return span.end;
    return time;
}
