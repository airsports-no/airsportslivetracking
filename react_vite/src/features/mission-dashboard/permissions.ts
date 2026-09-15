import type { AccessStatus, Contest } from './types';

/** Whether the current user may manage (not just view) this contest - an organizer/editor, or a superuser. */
export const canManageContest = (contest?: Pick<Contest, 'is_editor'> | null): boolean =>
    Boolean(contest?.is_editor) || document.configuration.is_superuser;

/**
 * Whether the contest's current tier already covers what's actually been registered/created so
 * far (its current contestants and tasks) - as opposed to covering hypothetical future growth.
 * The token panel promotes assigning/upgrading capacity, which is just noise for an organizer
 * whose free-tier (or existing token's) limits already comfortably fit what they actually have,
 * so it should only be shown once there's no longer headroom for what's already there.
 * A null limit means unlimited, i.e. always enough headroom.
 */
export const hasCapacityHeadroomForCurrentUsage = (accessStatus?: AccessStatus | null): boolean =>
    Boolean(
        accessStatus &&
            (accessStatus.contestant_limit == null || accessStatus.contestants_used < accessStatus.contestant_limit) &&
            (accessStatus.task_limit == null || accessStatus.tasks_used < accessStatus.task_limit)
    );
