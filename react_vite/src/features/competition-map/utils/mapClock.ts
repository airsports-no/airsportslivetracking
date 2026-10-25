import { create } from 'zustand';

/**
 * The followed contestant's clock offset (see gateCountdown.ts), shared so that every countdown on the page counts on
 * the same time: the gate score arrow measures it from its messages, and the flight timeline in the side panel uses it
 * too. Without it the panel would count on the browser's clock minus the calculation delay and run the pipeline's lag
 * (several seconds from device to browser) ahead of the arrow.
 */
interface MapClock {
    contestantId: number | null;
    offsetMs: number | null;
    set: (contestantId: number, offsetMs: number | null) => void;
}

export const useMapClock = create<MapClock>((set) => ({
    contestantId: null,
    offsetMs: null,
    set: (contestantId, offsetMs) => set({ contestantId, offsetMs }),
}));
