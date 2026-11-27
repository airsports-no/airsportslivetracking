import { beforeEach, describe, expect, it, vi } from 'vitest';

const bridge = vi.hoisted(() => ({ isEmbeddedInApp: vi.fn(() => false), signalApp: vi.fn() }));
vi.mock('../../utils/appBridge', () => bridge);

import { afterBooked, declarationStepPath, finishBooking, nextStepAfterBooking } from './bookingFlow';

const ids = { contestId: 7, navigationTaskId: 9 };

beforeEach(() => {
    bridge.signalApp.mockReset();
    bridge.isEmbeddedInApp.mockReset();
    bridge.isEmbeddedInApp.mockReturnValue(false);
});

describe('the step after booking', () => {
    it('is the declaration for a task that needs one or allows one', () => {
        expect(nextStepAfterBooking('required')).toBe('declaration');
        expect(nextStepAfterBooking('optional')).toBe('declaration');
        expect(nextStepAfterBooking('not_needed')).toBe('done');
        expect(nextStepAfterBooking(undefined)).toBe('done');
    });

    it('carries the ids of the booking in the address, so that any way out can end it', () => {
        expect(declarationStepPath(42, ids)).toBe('/declaration/42?booking=1&contestId=7&navigationTaskId=9');
    });

    it('goes to the declaration step, replacing the booking form in the history, without signalling the app yet', () => {
        bridge.isEmbeddedInApp.mockReturnValue(true);
        const navigate = vi.fn();
        afterBooked({ id: 42, declaration_status: { need: 'required' } }, ids, navigate);
        expect(navigate).toHaveBeenCalledWith('/declaration/42?booking=1&contestId=7&navigationTaskId=9', { replace: true });
        expect(bridge.signalApp).not.toHaveBeenCalled();
    });

    it('ends at once, with the signal in the app, for a task without a declaration', () => {
        bridge.isEmbeddedInApp.mockReturnValue(true);
        const navigate = vi.fn();
        afterBooked({ id: 42, declaration_status: { need: 'not_needed' } }, ids, navigate);
        expect(bridge.signalApp).toHaveBeenCalledWith('registered', ids);
        expect(navigate).not.toHaveBeenCalled();
    });

    it('ends at once when the answer says nothing about the booking', () => {
        bridge.isEmbeddedInApp.mockReturnValue(true);
        afterBooked(undefined, ids, vi.fn());
        expect(bridge.signalApp).toHaveBeenCalledWith('registered', ids);
    });
});

describe('the end of a booking', () => {
    it('signals the app inside the app', () => {
        bridge.isEmbeddedInApp.mockReturnValue(true);
        const navigate = vi.fn();
        finishBooking(ids, navigate);
        expect(bridge.signalApp).toHaveBeenCalledTimes(1);
        expect(bridge.signalApp).toHaveBeenCalledWith('registered', { contestId: 7, navigationTaskId: 9 });
        expect(navigate).not.toHaveBeenCalled();
    });

    it('opens the map of the task on the website', () => {
        const navigate = vi.fn();
        finishBooking(ids, navigate);
        expect(navigate).toHaveBeenCalledWith('/competition-map/7/9');
        expect(bridge.signalApp).not.toHaveBeenCalled();
    });
});
