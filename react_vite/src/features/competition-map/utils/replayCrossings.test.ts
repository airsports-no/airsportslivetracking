import { describe, expect, it } from 'vitest';
import { Contestant, GateResult } from '../types';
import { replayCrossings } from './replayCrossings';

const result = (gate: string, actual: string | null, offset: number | null, timeCheck = true): GateResult => ({
    gate, type: 'tp', time_check: timeCheck, hidden: false, planned: null, actual, offset_seconds: offset, missed: false, points: 0,
});
const contestant = { id: 7, gate_results: [
    result('SP', '2026-10-24T10:00:10Z', 2),
    result('TP1', '2026-10-24T10:00:20Z', null, false),
    result('FP', '2026-10-24T10:30:00Z', -3),
] } as unknown as Contestant;

describe('replayCrossings', () => {
    it('gives the timed gates crossed while the replay played', () => {
        expect(replayCrossings([contestant], new Date('2026-10-24T10:00:00Z'), new Date('2026-10-24T10:00:30Z'))).toEqual([
            { key: '7-SP', contestantId: 7, gate: 'SP', offsetSeconds: 2, missed: false },
        ]);
    });

    it('gives nothing when the replay was scrubbed or went backwards', () => {
        expect(replayCrossings([contestant], new Date('2026-10-24T09:00:00Z'), new Date('2026-10-24T10:31:00Z'))).toEqual([]);
        expect(replayCrossings([contestant], new Date('2026-10-24T10:31:00Z'), new Date('2026-10-24T10:00:00Z'))).toEqual([]);
    });
});
