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
// The UTC offset `timeZone` observes at a given instant, in minutes to ADD to UTC to get local
// wall-clock time (e.g. +60 for Europe/Oslo in winter).
function offsetMinutesAt(instant: Date, timeZone: string): number {
    const parts = new Intl.DateTimeFormat('en-US', {
        timeZone: timeZone || 'UTC',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
    }).formatToParts(instant);
    const part = (type: string) => parseInt(parts.find(item => item.type === type)!.value);
    const localAsUtc = Date.UTC(part('year'), part('month') - 1, part('day'), part('hour'), part('minute'), part('second'));
    return (localAsUtc - instant.getTime()) / 60000;
}

// Converts a <input type="datetime-local"> value (naive, no timezone) into an ISO string with
// the *contest's* UTC offset embedded - mirroring ScheduleFlightForm.tsx's getContestTimeWithOffset.
// NewNavigationTaskWizard achieves the equivalent server-side via timezone.activate(contest.time_zone)
// before interpreting the wizard form's naive datetime fields; this API-driven flow has no such
// per-request context to lean on, so the offset has to be made explicit in the payload instead.
export function contestLocalTimeToIso(dateStr: string, timeZone: string): string {
    const withSeconds = dateStr.length === 16 ? `${dateStr}:00` : dateStr;
    // Treating the wall-clock value as if it were UTC only gives the *offset that applies at that
    // provisional (generally wrong) instant* - which is usually the target's real offset, but can
    // be the wrong side of a DST transition for a local time within an hour or so of one. Correct
    // for this with the standard fixed-point iteration: apply the first guess's offset, then
    // re-derive the offset at the resulting instant and use that instead if it differs. This
    // converges after one extra pass everywhere except the DST transition's own ambiguous
    // (fall-back) or nonexistent (spring-forward) hour, where no single answer is uniquely
    // correct - the second pass's offset is used as the resolution in that case too.
    const naiveUtcGuess = new Date(`${withSeconds}Z`);
    let offsetMinutes = offsetMinutesAt(naiveUtcGuess, timeZone);
    const resolvedInstant = new Date(naiveUtcGuess.getTime() - offsetMinutes * 60000);
    const secondPassOffset = offsetMinutesAt(resolvedInstant, timeZone);
    if (secondPassOffset !== offsetMinutes) {
        offsetMinutes = secondPassOffset;
    }
    const absDiff = Math.abs(offsetMinutes);
    const hours = Math.floor(absDiff / 60);
    const minutes = absDiff % 60;
    const sign = offsetMinutes >= 0 ? '+' : '-';
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
