// @vitest-environment jsdom
import { canManageContest, hasCapacityHeadroomForCurrentUsage } from './permissions';
import type { AccessStatus } from './types';

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

describe('hasCapacityHeadroomForCurrentUsage', () => {
    const accessStatus = (overrides: Partial<AccessStatus> = {}): AccessStatus => ({
        tier_code: 'free',
        tier_label: 'Free',
        source_type: 'default',
        source_id: null,
        contestant_limit: 10,
        task_limit: 5,
        contestants_used: 0,
        tasks_used: 0,
        enforcement_mode: 'enforce',
        ...overrides,
    });

    it('returns false for a missing access status', () => {
        expect(hasCapacityHeadroomForCurrentUsage(null)).toBe(false);
        expect(hasCapacityHeadroomForCurrentUsage(undefined)).toBe(false);
    });

    it('returns true when usage is below both limits', () => {
        expect(hasCapacityHeadroomForCurrentUsage(accessStatus({ contestants_used: 3, tasks_used: 2 }))).toBe(true);
    });

    it('returns false when contestant usage is at the limit', () => {
        expect(hasCapacityHeadroomForCurrentUsage(accessStatus({ contestants_used: 10 }))).toBe(false);
    });

    it('returns false when task usage is at the limit', () => {
        expect(hasCapacityHeadroomForCurrentUsage(accessStatus({ tasks_used: 5 }))).toBe(false);
    });

    it('treats a null limit as unlimited headroom', () => {
        expect(
            hasCapacityHeadroomForCurrentUsage(
                accessStatus({ contestant_limit: null, task_limit: null, contestants_used: 999, tasks_used: 999 })
            )
        ).toBe(true);
    });
});
