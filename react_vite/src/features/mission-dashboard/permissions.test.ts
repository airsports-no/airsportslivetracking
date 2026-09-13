// @vitest-environment jsdom
import { canManageContest } from './permissions';

describe('canManageContest', () => {
    beforeEach(() => {
        (document as any).configuration = { is_superuser: false };
    });

    it('returns true when the contest is editor-owned', () => {
        expect(canManageContest({ is_editor: true })).toBe(true);
    });

    it('returns false when neither editor nor superuser', () => {
        expect(canManageContest({ is_editor: false })).toBe(false);
    });

    it('returns true for a superuser even on a non-editor contest', () => {
        (document as any).configuration.is_superuser = true;
        expect(canManageContest({ is_editor: false })).toBe(true);
    });

    it('returns false for a missing contest', () => {
        expect(canManageContest(null)).toBe(false);
        expect(canManageContest(undefined)).toBe(false);
    });
});
