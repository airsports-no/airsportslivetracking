import { describe, expect, it } from 'vitest';
import { mergePositions } from './mergePositions';
import { TrackPosition } from '../types';

const at = (time: string) => ({ time } as TrackPosition);

describe('mergePositions', () => {
    it('keeps what is known when the fetch returns less', () => {
        const known = [at('2026-10-25T10:00:00Z'), at('2026-10-25T10:00:10Z'), at('2026-10-25T10:00:20Z')];
        expect(mergePositions(known, [at('2026-10-25T10:00:20Z')])).toHaveLength(3);
    });

    it('adds what is new, in order, a position once even if its time is written differently', () => {
        const known = [at('2026-10-25T10:00:00Z'), at('2026-10-25T10:00:10Z')];
        const fetched = [at('2026-10-25T10:00:10+00:00'), at('2026-10-25T10:00:20Z')];
        const merged = mergePositions(known, fetched);
        expect(merged.map(p => new Date(p.time).getTime())).toEqual([
            Date.parse('2026-10-25T10:00:00Z'), Date.parse('2026-10-25T10:00:10Z'), Date.parse('2026-10-25T10:00:20Z'),
        ]);
    });

    it('copes with nothing known or nothing fetched', () => {
        expect(mergePositions(undefined, [at('2026-10-25T10:00:00Z')])).toHaveLength(1);
        expect(mergePositions([at('2026-10-25T10:00:00Z')], undefined)).toHaveLength(1);
        expect(mergePositions(undefined, undefined)).toEqual([]);
    });
});
