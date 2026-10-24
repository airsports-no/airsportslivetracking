import { describe, expect, it } from 'vitest';
import { cameraMove } from './followCamera';

const view = { south: 60, west: 10, north: 61, east: 12 };

describe('cameraMove', () => {
    it('stays while the aircraft is in the middle of the view', () => {
        expect(cameraMove(view, { lat: 60.5, lon: 11 }, null, false)).toEqual({ kind: 'stay' });
    });

    it('pans to the aircraft when it nears the edge', () => {
        expect(cameraMove(view, { lat: 60.95, lon: 11 }, null, false)).toEqual({ kind: 'pan', to: { lat: 60.95, lon: 11 } });
        expect(cameraMove(view, { lat: 60.5, lon: 10.1 }, null, false).kind).toBe('pan');
    });

    it('shows the aircraft and its next gate together when the gate changes', () => {
        const gate = { lat: 60.2, lon: 11.5 };
        expect(cameraMove(view, { lat: 60.5, lon: 11 }, gate, true)).toEqual({
            kind: 'fit',
            points: [{ lat: 60.5, lon: 11 }, gate],
        });
    });

    it('centres on the aircraft when following starts without a gate', () => {
        expect(cameraMove(view, { lat: 60.5, lon: 11 }, null, false, true)).toEqual({ kind: 'centre', to: { lat: 60.5, lon: 11 } });
    });

    it('does not fit again for the same gate', () => {
        expect(cameraMove(view, { lat: 60.5, lon: 11 }, { lat: 60.2, lon: 11.5 }, false)).toEqual({ kind: 'stay' });
    });
});
