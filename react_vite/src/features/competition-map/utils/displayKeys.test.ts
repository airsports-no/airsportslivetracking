import { describe, expect, it } from 'vitest';
import { displayKeyAction, stepThrough } from './displayKeys';

describe('displayKeyAction', () => {
    it('maps the display keys', () => {
        expect(displayKeyAction({ key: '3' })).toEqual({ kind: 'place', place: 3 });
        expect(displayKeyAction({ key: 'ArrowLeft' })).toEqual({ kind: 'step', by: -1 });
        expect(displayKeyAction({ key: 'f' })).toEqual({ kind: 'camera' });
        expect(displayKeyAction({ key: 'Escape' })).toEqual({ kind: 'overview' });
        expect(displayKeyAction({ key: '?' })).toEqual({ kind: 'help' });
    });

    it('leaves other keys and browser shortcuts alone', () => {
        expect(displayKeyAction({ key: '0' })).toBeNull();
        expect(displayKeyAction({ key: 'a' })).toBeNull();
        expect(displayKeyAction({ key: 'f', ctrlKey: true })).toBeNull();
        expect(displayKeyAction({ key: '1', metaKey: true })).toBeNull();
    });
});

describe('stepThrough', () => {
    it('goes round the contestants in the air', () => {
        expect(stepThrough([4, 7, 9], 7, 1)).toBe(9);
        expect(stepThrough([4, 7, 9], 9, 1)).toBe(4);
        expect(stepThrough([4, 7, 9], 4, -1)).toBe(9);
        expect(stepThrough([4, 7, 9], null, 1)).toBe(4);
        expect(stepThrough([4, 7, 9], 12, -1)).toBe(9);
        expect(stepThrough([], 4, 1)).toBeNull();
    });
});
