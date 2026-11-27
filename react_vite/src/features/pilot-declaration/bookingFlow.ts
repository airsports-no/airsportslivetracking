// The step after booking a flight: the declaration (when the task has one), and then the one ending of the flow the apps know.
import { generatePath } from '../../urls';
import { isEmbeddedInApp, signalApp } from '../../utils/appBridge';
import { needsDeclarationStep } from './declarationForm';
import { DeclarationNeed } from './types';

export interface BookingIds {
    contestId: number;
    navigationTaskId: number;
}

/** The page of the declaration step. The ids ride along so that every way out of it can end the booking, whatever has loaded. */
export const declarationStepPath = (contestantId: number, ids: BookingIds): string =>
    `${generatePath('PILOT_DECLARATION', { contestantId })}?booking=1&contestId=${ids.contestId}&navigationTaskId=${ids.navigationTaskId}`;

/** Where the booking goes after a flight is booked: the declaration step if the task has a declaration, else the end. */
export const nextStepAfterBooking = (need: DeclarationNeed | undefined | null): 'declaration' | 'done' =>
    needsDeclarationStep(need) ? 'declaration' : 'done';

/**
 * The end of every booking, whichever way it got here (finished, "do this later", skipped, nothing to declare, a page that
 * would not load): the app's web view gets airsportsapp://registered, the website goes to the task's map.
 */
export const finishBooking = (ids: BookingIds, navigate: (to: string) => void): void => {
    if (isEmbeddedInApp()) signalApp('registered', { contestId: ids.contestId, navigationTaskId: ids.navigationTaskId });
    else navigate(generatePath('COMPETITION_MAP_DETAIL', { contestId: ids.contestId, navigationTaskId: ids.navigationTaskId }));
};

/** What happens when the booking has been made: on to the declaration step, or the end of the booking. */
export const afterBooked = (
    booked: { id: number; declaration_status?: { need?: DeclarationNeed } } | null | undefined,
    ids: BookingIds,
    navigate: (to: string, options?: { replace?: boolean }) => void,
): void => {
    if (booked && nextStepAfterBooking(booked.declaration_status?.need) === 'declaration') {
        // Replaced, so that "back" does not return to the booking form and book a second flight
        navigate(declarationStepPath(booked.id, ids), { replace: true });
    } else {
        finishBooking(ids, navigate);
    }
};
