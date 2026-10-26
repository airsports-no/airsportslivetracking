import { describe, expect, it } from 'vitest';
import { FOLLOW_MS, OVERVIEW_MS, rotationAt } from './displayRotation';

describe('rotationAt', () => {
    it('shows the overview, then each flying contestant in turn, round and round', () => {
        const flying = [3, 7];
        expect(rotationAt(0, flying)).toEqual({ kind: 'overview' });
        expect(rotationAt(OVERVIEW_MS, flying)).toEqual({ kind: 'follow', id: 3 });
        expect(rotationAt(OVERVIEW_MS + FOLLOW_MS, flying)).toEqual({ kind: 'follow', id: 7 });
        expect(rotationAt(OVERVIEW_MS + 2 * FOLLOW_MS, flying)).toEqual({ kind: 'overview' });
        expect(rotationAt(2 * OVERVIEW_MS + 2 * FOLLOW_MS + 1, flying)).toEqual({ kind: 'follow', id: 3 });
    });

    it('stays on the overview while nobody flies', () => {
        expect(rotationAt(OVERVIEW_MS * 5, [])).toEqual({ kind: 'overview' });
    });
});
