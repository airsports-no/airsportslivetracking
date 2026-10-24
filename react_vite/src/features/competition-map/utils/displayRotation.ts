/** What an unattended screen shows at a moment: the whole field, or one contestant followed. */
export type RotationStep = { kind: 'overview' } | { kind: 'follow'; id: number };

export const OVERVIEW_MS = 60_000;
export const FOLLOW_MS = 30_000;

/**
 * The screen's rotation: the overview for a minute, then each flying contestant in turn for 30 s, round and round.
 * `elapsedMs` counts from when the rotation (re)started; the flying contestants are taken as they are now, so one who
 * lands drops out of the next round and one who takes off joins it. Nobody flying: the overview.
 */
export function rotationAt(elapsedMs: number, flyingIds: number[]): RotationStep {
    if (flyingIds.length === 0) return { kind: 'overview' };
    const round = OVERVIEW_MS + FOLLOW_MS * flyingIds.length;
    const t = ((elapsedMs % round) + round) % round;
    if (t < OVERVIEW_MS) return { kind: 'overview' };
    return { kind: 'follow', id: flyingIds[Math.floor((t - OVERVIEW_MS) / FOLLOW_MS)] };
}
