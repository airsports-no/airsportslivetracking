import { describe, expect, it } from 'vitest';
import { cameraMove, nextFollowSession } from './followCamera';

const view = { south: 60, west: 10, north: 61, east: 12 };

describe('nextFollowSession', () => {
    it('keeps the session while the same contestant is followed', () => {
        const session = { id: 7, n: 3 };
        expect(nextFollowSession(session, 7)).toBe(session);
    });

    it('starts a new session when another contestant, or nobody, is followed', () => {
        expect(nextFollowSession({ id: 7, n: 3 }, 9)).toEqual({ id: 9, n: 4 });
        expect(nextFollowSession({ id: 7, n: 3 }, null)).toEqual({ id: null, n: 4 });
    });

    it('makes the same contestant followed again after nobody a new session, so an old pause is over', () => {
        const first = { id: 7, n: 1 };
        const nobody = nextFollowSession(first, null);
        const again = nextFollowSession(nobody, 7);
        expect(again.n).not.toBe(first.n);
    });
});

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
