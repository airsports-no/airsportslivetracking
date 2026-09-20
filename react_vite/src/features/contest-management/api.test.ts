import { describe, expect, it } from 'vitest';
import { extractPictureFile } from './api';

describe('extractPictureFile', () => {
    it('returns undefined and leaves the entity untouched when there is no file', () => {
        const entity = { registration: 'LN-ABC', type: 'Cessna 172' };
        const result = extractPictureFile(entity, 'picture');

        expect(result).toBeUndefined();
        expect(entity).toEqual({ registration: 'LN-ABC', type: 'Cessna 172' });
    });

    it('pulls a File out of the entity and removes it, so it can travel outside the JSON payload', () => {
        const file = new File(['fake'], 'plane.jpg', { type: 'image/jpeg' });
        const entity: Record<string, unknown> = { registration: 'LN-ABC', picture: file };

        const result = extractPictureFile(entity, 'picture');

        expect(result).toBe(file);
        expect(entity).toEqual({ registration: 'LN-ABC' });
    });

    it('returns undefined for an undefined entity (e.g. a skipped copilot)', () => {
        expect(extractPictureFile(undefined, 'picture')).toBeUndefined();
    });
});
