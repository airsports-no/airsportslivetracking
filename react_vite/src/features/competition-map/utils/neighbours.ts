/** A neighbour in the ranking and the points between them and the followed contestant. */
export interface NeighbourGap {
    id: number;
    points: number;
}

/**
 * The contestants just above and below the one at `index` in the standings (best first), among those who have started,
 * with the points between them. Only where both have a score.
 */
export function neighbourGaps(
    standings: { id: number; score: number | string }[],
    index: number,
    startedCount: number,
): { above: NeighbourGap | null; below: NeighbourGap | null } {
    const own = standings[index];
    if (!own || index >= startedCount || typeof own.score !== 'number') return { above: null, below: null };
    const gapTo = (i: number): NeighbourGap | null => {
        const other = standings[i];
        if (!other || i < 0 || i >= startedCount || typeof other.score !== 'number') return null;
        return { id: other.id, points: Math.round(Math.abs(other.score - (own.score as number))) };
    };
    return { above: gapTo(index - 1), below: gapTo(index + 1) };
}
