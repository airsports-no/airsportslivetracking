import { Contestant, CrossingEvent } from '../types';

/** A replay that moves further than this between two updates has been scrubbed, not played: no notices for the jump. */
const MAX_PLAYED_STEP_MS = 60_000;

/**
 * The timed gates crossed (from gate_results) while a replay played from `from` to `to`, for every contestant, as
 * notices like the live ones. Nothing when the replay went backwards or jumped.
 */
export function replayCrossings(contestants: Contestant[], from: Date, to: Date): CrossingEvent[] {
    const step = to.getTime() - from.getTime();
    if (step <= 0 || step > MAX_PLAYED_STEP_MS) return [];
    const crossings: CrossingEvent[] = [];
    for (const c of contestants) {
        for (const r of c.gate_results ?? []) {
            if (!r.time_check || r.actual === null || r.offset_seconds === null) continue;
            const t = new Date(r.actual).getTime();
            if (t > from.getTime() && t <= to.getTime()) {
                crossings.push({ key: `${c.id}-${r.gate}`, contestantId: c.id, gate: r.gate, offsetSeconds: r.offset_seconds, missed: false });
            }
        }
    }
    return crossings;
}
