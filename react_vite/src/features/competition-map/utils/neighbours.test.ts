import { describe, expect, it } from 'vitest';
import { neighbourGaps } from './neighbours';

const standings = [
    { id: 1, score: 100 },
    { id: 2, score: 112 },
    { id: 3, score: 142 },
    { id: 4, score: 'Not started' },
];

describe('neighbourGaps', () => {
    it('gives the points to the contestants just above and below', () => {
        expect(neighbourGaps(standings, 1, 3)).toEqual({ above: { id: 1, points: 12 }, below: { id: 3, points: 30 } });
    });

    it('has nobody above the leader, and leaves out those who have not started', () => {
        expect(neighbourGaps(standings, 0, 3).above).toBeNull();
        expect(neighbourGaps(standings, 2, 3).below).toBeNull();
        expect(neighbourGaps(standings, 3, 3)).toEqual({ above: null, below: null });
    });
});
