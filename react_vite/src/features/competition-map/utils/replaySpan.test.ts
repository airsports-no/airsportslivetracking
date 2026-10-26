import { describe, expect, it } from 'vitest';
import { clampToSpan, flightSpan } from './replaySpan';

describe('flightSpan', () => {
    it('runs from the first to the last position with a minute either side', () => {
        const span = flightSpan([
            { time: '2026-10-24T10:05:00Z' },
            { time: '2026-10-24T10:00:00Z' },
            { time: '2026-10-24T10:42:30Z' },
        ])!;
        expect(span.start.toISOString()).toBe('2026-10-24T09:59:00.000Z');
        expect(span.end.toISOString()).toBe('2026-10-24T10:43:30.000Z');
    });

    it('is null without positions', () => {
        expect(flightSpan([])).toBeNull();
        expect(flightSpan(undefined)).toBeNull();
    });
});

describe('clampToSpan', () => {
    const span = { start: new Date('2026-10-24T10:00:00Z'), end: new Date('2026-10-24T11:00:00Z') };
    it('keeps a time inside the span and moves one outside to the nearest end', () => {
        const inside = new Date('2026-10-24T10:30:00Z');
        expect(clampToSpan(inside, span)).toBe(inside);
        expect(clampToSpan(new Date('2026-10-24T09:00:00Z'), span)).toBe(span.start);
        expect(clampToSpan(new Date('2026-10-24T12:00:00Z'), span)).toBe(span.end);
    });
});
