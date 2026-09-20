// @vitest-environment node
//
// Regression test for the overtake-flag bug: overtakeContestantIds used to compare raw
// finished_by_time for every contestant, while the timeline bar itself ends at landing_time once
// a contestant has actually landed. A contestant whose real landing came in earlier or later than
// their scheduled finished_by_time could get flagged (or missed) as an overtake that the bars -
// which use getBlockEndTime - don't visually show at all. Both now derive from this same
// function, tested here in isolation (a pure function, no need to render vis-timeline, which has
// known jsdom incompatibilities - see Timeline.rulesOfHooks.test.ts).

import { describe, expect, it } from 'vitest';
import { getBlockEndTime } from './Timeline';

describe('getBlockEndTime', () => {
    it('uses landing_time when the contestant has actually landed', () => {
        const contestant = {
            adaptive_start: false,
            finished_by_time: '2026-08-01T12:00:00Z',
            landing_time: '2026-08-01T11:30:00Z',
        };
        expect(getBlockEndTime(contestant)).toBe(new Date('2026-08-01T11:30:00Z').getTime());
    });

    it('falls back to finished_by_time when there is no landing_time yet', () => {
        const contestant = {
            adaptive_start: false,
            finished_by_time: '2026-08-01T12:00:00Z',
            landing_time: null,
        };
        expect(getBlockEndTime(contestant)).toBe(new Date('2026-08-01T12:00:00Z').getTime());
    });

    it('always uses finished_by_time for an adaptive-start contestant, even with a landing_time', () => {
        const contestant = {
            adaptive_start: true,
            finished_by_time: '2026-08-01T12:00:00Z',
            landing_time: '2026-08-01T11:30:00Z',
        };
        expect(getBlockEndTime(contestant)).toBe(new Date('2026-08-01T12:00:00Z').getTime());
    });
});
