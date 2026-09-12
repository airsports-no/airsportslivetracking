// Mirrors display.utilities.navigation_task_type_definitions.NAVIGATION_TASK_TYPES's family keys.
export const PRECISION = 'precision';
export const ANR_CORRIDOR = 'anr_corridor';
export const AIRSPORTS = 'airsports';
export const AIRSPORT_CHALLENGE = 'airsportchallenge';
export const POKER = 'poker';
export const LANDING = 'landing';

export type NavigationTaskCreationStep = 'template' | 'contest' | 'route' | 'parameters' | 'details';

export type NavigationTaskCreationEntry =
    | { kind: 'contest'; contestId: number }
    | { kind: 'route'; editableRouteId: number };

// Mirrors EditableRoute.create_route()'s per-family parameter requirements
// (display/models/editable_route.py) - which of the two write-only parameter fields on
// NavigationTaskEditableRoutReferenceSerialiser this task family needs before it can be created.
export function requiredParameters(taskType: string): Array<'corridor_width' | 'rounded_corners'> {
    if (taskType === ANR_CORRIDOR) {
        return ['rounded_corners', 'corridor_width'];
    }
    if (taskType === AIRSPORTS || taskType === AIRSPORT_CHALLENGE) {
        return ['rounded_corners'];
    }
    return [];
}

// Which step comes after the current one, given what's already been picked. `entry.kind ===
// 'route'` skips the route-selection step (the route is already fixed by the entry context) -
// this is what lets NavigationTaskCreationFlow serve both NewNavigationTaskWizard's replacement
// (entry: contest) and RouteToTaskWizard's (entry: route) as one component.
// Converts a <input type="datetime-local"> value (naive, no timezone) into an ISO string with
// the *contest's* UTC offset embedded - mirroring ScheduleFlightForm.tsx's getContestTimeWithOffset.
// NewNavigationTaskWizard achieves the equivalent server-side via timezone.activate(contest.time_zone)
// before interpreting the wizard form's naive datetime fields; this API-driven flow has no such
// per-request context to lean on, so the offset has to be made explicit in the payload instead.
export function contestLocalTimeToIso(dateStr: string, timeZone: string): string {
    const withSeconds = dateStr.length === 16 ? `${dateStr}:00` : dateStr;
    const d = new Date(`${withSeconds}Z`);
    const parts = new Intl.DateTimeFormat('en-US', {
        timeZone: timeZone || 'UTC',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
    }).formatToParts(d);
    const part = (type: string) => parseInt(parts.find(item => item.type === type)!.value);
    const localInTimeZone = Date.UTC(part('year'), part('month') - 1, part('day'), part('hour'), part('minute'), part('second'));
    const diffMinutes = (localInTimeZone - d.getTime()) / 60000;
    const absDiff = Math.abs(diffMinutes);
    const hours = Math.floor(absDiff / 60);
    const minutes = absDiff % 60;
    const sign = diffMinutes >= 0 ? '+' : '-';
    const offset = `${sign}${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
    return `${withSeconds}${offset}`;
}

export function nextStep(
    step: NavigationTaskCreationStep,
    entry: NavigationTaskCreationEntry,
    taskType: string | null
): NavigationTaskCreationStep | 'submit' {
    switch (step) {
        case 'template':
            // entry.kind === 'route': the route is already fixed by the entry context, but which
            // contest the task belongs to still needs picking/creating (RouteToTaskWizard's
            // contest_selection/contest_creation steps). entry.kind === 'contest': the reverse -
            // the contest is already fixed, but which route to use still needs picking.
            return entry.kind === 'route' ? 'contest' : 'route';
        case 'contest':
        case 'route':
            return requiredParameters(taskType ?? '').length > 0 ? 'parameters' : 'details';
        case 'parameters':
            return 'details';
        case 'details':
            return 'submit';
        default:
            return 'template';
    }
}
