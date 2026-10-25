import { TrackPosition } from '../types';

/**
 * The positions already known together with freshly fetched ones, oldest first, a position (by its time) once. A
 * refetch of a track (back from a replay, after a lost connection) may return less than the page already holds, for
 * instance when a slice cached a minute ago is missing the end of that minute: the track must never get shorter.
 */
export function mergePositions(known: TrackPosition[] | undefined, fetched: TrackPosition[] | undefined): TrackPosition[] {
    const byTime = new Map<number, TrackPosition>();
    for (const position of known ?? []) byTime.set(new Date(position.time).getTime(), position);
    for (const position of fetched ?? []) byTime.set(new Date(position.time).getTime(), position);
    return [...byTime.entries()].sort((a, b) => a[0] - b[0]).map(([, position]) => position);
}
