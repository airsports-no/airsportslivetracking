import { describe, expect, it } from 'vitest';
import { formatStartsIn } from './startsIn';

describe('formatStartsIn', () => {
    it('counts minutes and hours like a clock, and days from a day ahead', () => {
        expect(formatStartsIn(252)).toBe('4:12');
        expect(formatStartsIn(2 * 3600 + 38 * 60)).toBe('2:38:00');
        expect(formatStartsIn(826 * 3600)).toBe('34 d');
        expect(formatStartsIn(-5)).toBe('0:00');
    });
});
