import { beforeEach, describe, expect, it, vi } from 'vitest';

const bridge = vi.hoisted(() => ({ isEmbeddedInApp: vi.fn(() => false), signalApp: vi.fn() }));
vi.mock('../../utils/appBridge', () => bridge);

import { afterBooked, afterBookedInDialog, declarationStepPath, finishBooking, nextStepAfterBooking, safeReturnTo } from './bookingFlow';

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

describe('where the website returns to', () => {
    const dashboard = { ...ids, returnTo: '/mission-dashboard/7' };

    it('is the page the booking started on when one is given', () => {
        const navigate = vi.fn();
        finishBooking(dashboard, navigate);
        expect(navigate).toHaveBeenCalledWith('/mission-dashboard/7');
    });

    it('rides along in the address of the declaration step', () => {
        expect(declarationStepPath(42, dashboard)).toBe(
            '/declaration/42?booking=1&contestId=7&navigationTaskId=9&returnTo=%2Fmission-dashboard%2F7',
        );
    });

    it('is only ever a path on this site', () => {
        expect(safeReturnTo('/mission-dashboard/7')).toBe('/mission-dashboard/7');
        expect(safeReturnTo('//evil.example')).toBeUndefined();
        expect(safeReturnTo('https://evil.example')).toBeUndefined();
        expect(safeReturnTo('/\\evil.example')).toBeUndefined();
        expect(safeReturnTo(null)).toBeUndefined();
    });
});

describe('a booking made in the dialog of the contest dashboard', () => {
    const dashboard = { ...ids, returnTo: '/mission-dashboard/7' };

    it('goes on to the declaration for a task with one, keeping the dashboard in the history', () => {
        const navigate = vi.fn();
        const stay = vi.fn();
        const result = afterBookedInDialog({ id: 42, declaration_status: { need: 'required' } }, dashboard, navigate, stay);
        expect(result).toBe('declaration');
        expect(navigate).toHaveBeenCalledWith(
            '/declaration/42?booking=1&contestId=7&navigationTaskId=9&returnTo=%2Fmission-dashboard%2F7',
            { replace: false },
        );
        expect(stay).not.toHaveBeenCalled();
        expect(bridge.signalApp).not.toHaveBeenCalled();
    });

    it('does the same for an optional declaration, also inside the app (the signal comes at the end of the step)', () => {
        bridge.isEmbeddedInApp.mockReturnValue(true);
        const navigate = vi.fn();
        expect(afterBookedInDialog({ id: 42, declaration_status: { need: 'optional' } }, dashboard, navigate, vi.fn())).toBe('declaration');
        expect(navigate).toHaveBeenCalledTimes(1);
        expect(bridge.signalApp).not.toHaveBeenCalled();
    });

    it('stays on the dashboard on the website when there is nothing to declare', () => {
        const navigate = vi.fn();
        const stay = vi.fn();
        expect(afterBookedInDialog({ id: 42, declaration_status: { need: 'not_needed' } }, dashboard, navigate, stay)).toBe('stayed');
        expect(stay).toHaveBeenCalledTimes(1);
        expect(navigate).not.toHaveBeenCalled();
        expect(bridge.signalApp).not.toHaveBeenCalled();
    });

    it('signals the app at once when there is nothing to declare, and does not close the dialog by itself', () => {
        bridge.isEmbeddedInApp.mockReturnValue(true);
        const navigate = vi.fn();
        const stay = vi.fn();
        expect(afterBookedInDialog({ id: 42 }, dashboard, navigate, stay)).toBe('signalled');
        expect(bridge.signalApp).toHaveBeenCalledTimes(1);
        expect(bridge.signalApp).toHaveBeenCalledWith('registered', { contestId: 7, navigationTaskId: 9 });
        expect(stay).not.toHaveBeenCalled();
        expect(navigate).not.toHaveBeenCalled();
    });

    it('treats an answer without the booking like a task without a declaration', () => {
        const stay = vi.fn();
        expect(afterBookedInDialog(undefined, dashboard, vi.fn(), stay)).toBe('stayed');
        expect(stay).toHaveBeenCalled();
    });
});
