import type { Contest } from './types';

/** Whether the current user may manage (not just view) this contest - an organizer/editor, or a superuser. */
export const canManageContest = (contest?: Pick<Contest, 'is_editor'> | null): boolean =>
    Boolean(contest?.is_editor) || document.configuration.is_superuser;
