import { describe, expect, it } from 'vitest';
import { declarationTimesPayload, toDatetimeLocalValue } from './declarationSequences';

const KEY = 'compulsory_point_times';
// A declaration a pilot made as seconds after the start point: SP at 10:00, A at +10:00, B at +20:30
const relative = {
    time_reference: 'start_point',
    relative_times: { A: 600, B: 1230 },
    [KEY]: { A: '2026-08-01T10:10:00+00:00', B: '2026-08-01T10:20:30+00:00' },
};

describe('declarationTimesPayload', () => {
    it('sends clock times as they are for a declaration in clock times', () => {
        const entries = { A: '2026-08-01T10:10' };
        expect(declarationTimesPayload({ [KEY]: { A: '2026-08-01T10:10:00Z' } }, KEY, entries)).toEqual({ [KEY]: entries });
        expect(declarationTimesPayload(undefined, KEY, entries)).toEqual({ [KEY]: entries });
    });

    it('keeps a declaration in seconds after the start point in seconds, unchanged entries exactly as they were', () => {
        const entries = { A: toDatetimeLocalValue(relative[KEY].A), B: toDatetimeLocalValue(relative[KEY].B) };
        // B is 10:20:30: the input only holds minutes, but the seconds are kept because the entry was not touched
        expect(declarationTimesPayload(relative, KEY, entries)).toEqual({
            [KEY]: { A: 600, B: 1230 },
            time_reference: 'start_point',
        });
    });

    it('moves a changed entry by the change and leaves the others', () => {
        const entries = { A: toDatetimeLocalValue('2026-08-01T10:15:00+00:00'), B: toDatetimeLocalValue(relative[KEY].B) };
        expect(declarationTimesPayload(relative, KEY, entries)).toEqual({
            [KEY]: { A: 900, B: 1230 },
            time_reference: 'start_point',
        });
    });

    it('works out the seconds of a point that had no time from the start point the others imply', () => {
        const entries = { A: toDatetimeLocalValue(relative[KEY].A), C: toDatetimeLocalValue('2026-08-01T10:30:00+00:00') };
        const result = declarationTimesPayload(relative, KEY, entries) as any;
        expect(result.time_reference).toBe('start_point');
        expect(result[KEY].A).toBe(600);
        expect(result[KEY].C).toBe(1800);
    });

    it('leaves a point out that the organiser took out', () => {
        const result = declarationTimesPayload(relative, KEY, { A: toDatetimeLocalValue(relative[KEY].A) }) as any;
        expect(result[KEY]).toEqual({ A: 600 });
    });
});
