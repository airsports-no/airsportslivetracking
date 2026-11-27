// The step after booking a flight: the declaration (when the task has one), and then the one ending of the flow the apps know.
import { generatePath } from '../../urls';
import { isEmbeddedInApp, signalApp } from '../../utils/appBridge';
import { needsDeclarationStep } from './declarationForm';
import { DeclarationNeed } from './types';

export interface BookingIds {
    contestId: number;
    navigationTaskId: number;
    /** Where the website goes when the booking ends (default: the task's map). Not used in the app, which always gets the signal. */
    returnTo?: string;
}

/** Only a path on this site is accepted as the place to return to */
export const safeReturnTo = (value: string | null | undefined): string | undefined =>
    value && value.startsWith('/') && !value.startsWith('//') && !value.includes('\\') ? value : undefined;

/** The page of the declaration step. The ids ride along so that every way out of it can end the booking, whatever has loaded. */
export const declarationStepPath = (contestantId: number, ids: BookingIds): string =>
    `${generatePath('PILOT_DECLARATION', { contestantId })}?booking=1&contestId=${ids.contestId}&navigationTaskId=${ids.navigationTaskId}` +
    (safeReturnTo(ids.returnTo) ? `&returnTo=${encodeURIComponent(ids.returnTo as string)}` : '');

/** Where the booking goes after a flight is booked: the declaration step if the task has a declaration, else the end. */
export const nextStepAfterBooking = (need: DeclarationNeed | undefined | null): 'declaration' | 'done' =>
    needsDeclarationStep(need) ? 'declaration' : 'done';

/**
 * The end of every booking, whichever way it got here (finished, "do this later", skipped, nothing to declare, a page that
 * would not load): the app's web view gets airsportsapp://registered, the website goes to where the booking started (ids.returnTo) or, by default, to the task's map.
 */
export const finishBooking = (ids: BookingIds, navigate: (to: string) => void): void => {
    if (isEmbeddedInApp()) signalApp('registered', { contestId: ids.contestId, navigationTaskId: ids.navigationTaskId });
    else navigate(safeReturnTo(ids.returnTo) ?? generatePath('COMPETITION_MAP_DETAIL', { contestId: ids.contestId, navigationTaskId: ids.navigationTaskId }));
};

/** What happens when the booking has been made: on to the declaration step, or the end of the booking. */
export const afterBooked = (
    booked: { id: number; declaration_status?: { need?: DeclarationNeed } } | null | undefined,
    ids: BookingIds,
    navigate: (to: string, options?: { replace?: boolean }) => void,
    /** replace: false keeps the page the booking started on in the history (the dashboard, which has no form page to avoid) */
    options: { replace?: boolean } = {},
): void => {
    if (booked && nextStepAfterBooking(booked.declaration_status?.need) === 'declaration') {
        // Replaced, so that "back" does not return to the booking form and book a second flight
        navigate(declarationStepPath(booked.id, ids), { replace: options.replace ?? true });
    } else {
        finishBooking(ids, navigate);
    }
};

/**
 * The same step after booking for a booking made in a dialog on a page that stays (the contest dashboard), so that the dialog
 * and the booking page cannot diverge: a task with a declaration goes on to the declaration step (history kept, so that "back"
 * returns to the page); otherwise the app gets its signal and the website stays where it is (`stay` closes the dialog).
 * The ids' returnTo is where the declaration step sends the website when it ends.
 */
export const afterBookedInDialog = (
    booked: { id: number; declaration_status?: { need?: DeclarationNeed } } | null | undefined,
    ids: BookingIds,
    navigate: (to: string, options?: { replace?: boolean }) => void,
    stay: () => void,
): 'declaration' | 'signalled' | 'stayed' => {
    if (booked && nextStepAfterBooking(booked.declaration_status?.need) === 'declaration') {
        afterBooked(booked, ids, navigate, { replace: false });
        return 'declaration';
    }
    if (isEmbeddedInApp()) {
        finishBooking(ids, navigate);
        return 'signalled';
    }
    stay();
    return 'stayed';
};
