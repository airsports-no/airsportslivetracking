import { describe, expect, it } from 'vitest';
import { GateResult } from '../types';
import { gateStates } from './gateStates';

const gate = (name: string, actual: string | null, missed = false): GateResult => ({
    gate: name, type: 'tp', time_check: true, hidden: false, planned: null, actual, offset_seconds: null, missed, points: 0,
});

const flight = [
    gate('SP', '2026-10-24T10:00:00Z'),
    gate('TP1', '2026-10-24T10:05:00Z'),
    gate('TP2', null, true),
    gate('TP3', '2026-10-24T10:15:00Z'),
    gate('FP', null),
];

describe('gateStates', () => {
    it('shows the whole flight once it is over', () => {
        expect(gateStates(flight, new Date('2026-10-24T11:00:00Z'))).toEqual(['crossed', 'crossed', 'missed', 'crossed', 'next']);
    });

    it('shows the flight as it was at a moment of the replay', () => {
        // TP2 was missed, but that is only known once TP3 is crossed
        expect(gateStates(flight, new Date('2026-10-24T10:06:00Z'))).toEqual(['crossed', 'crossed', 'next', 'ahead', 'ahead']);
    });

    it('counts a miss at once where misses are known (live, or the end of a replay)', () => {
        const unfinished = [gate('SP', '2026-10-24T10:00:00Z'), gate('TP1', null, true), gate('FP', null)];
        expect(gateStates(unfinished, new Date('2026-10-24T11:00:00Z'))).toEqual(['crossed', 'next', 'ahead']);
        expect(gateStates(unfinished, new Date('2026-10-24T11:00:00Z'), true)).toEqual(['crossed', 'missed', 'next']);
    });

    it('has the starting point next before anything is crossed', () => {
        expect(gateStates(flight, new Date('2026-10-24T09:00:00Z'))).toEqual(['next', 'ahead', 'ahead', 'ahead', 'ahead']);
    });
});
