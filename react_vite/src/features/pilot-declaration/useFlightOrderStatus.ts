import { useEffect, useRef, useState } from 'react';
import { shouldPoll } from './declarationForm';
import { FlightOrderStatus } from './types';

export const POLL_INTERVAL_MS = 5000;

/**
 * The flight order status, asked again every [intervalMs] while it is being made. Stops when it is ready or has failed,
 * and does not ask while the page is hidden (it asks at once when the page is shown again).
 */
export const useFlightOrderStatus = (
    initial: FlightOrderStatus | null,
    refresh: () => Promise<FlightOrderStatus | null>,
    intervalMs: number = POLL_INTERVAL_MS,
): FlightOrderStatus | null => {
    // What polling found is only good for the answer it followed: a new answer from the page (after saving) replaces it.
    // Compared by content, not identity.
    const initialKey = JSON.stringify(initial);
    const [polled, setPolled] = useState<{ key: string; status: FlightOrderStatus } | null>(null);
    const status = polled && polled.key === initialKey ? polled.status : initial;
    const refreshRef = useRef(refresh);
    useEffect(() => {
        refreshRef.current = refresh;
    });

    const polling = shouldPoll(status);
    useEffect(() => {
        if (!polling) return undefined;
        let cancelled = false;
        let inFlight = false;
        let timer: ReturnType<typeof setTimeout> | undefined;

        const run = async () => {
            if (cancelled || inFlight || document.hidden) return;
            inFlight = true;
            let keepGoing = true;
            try {
                const next = await refreshRef.current();
                if (cancelled) return;
                if (next) {
                    setPolled({ key: initialKey, status: next });
                    keepGoing = shouldPoll(next);
                }
            } catch {
                // The next round tries again
            } finally {
                inFlight = false;
            }
            if (keepGoing && !cancelled) timer = setTimeout(run, intervalMs);
        };
        const onVisibilityChange = () => {
            if (document.hidden) return;
            clearTimeout(timer);
            void run();
        };

        document.addEventListener('visibilitychange', onVisibilityChange);
        timer = setTimeout(run, intervalMs);
        return () => {
            cancelled = true;
            clearTimeout(timer);
            document.removeEventListener('visibilitychange', onVisibilityChange);
        };
    }, [polling, intervalMs, initialKey]);

    return status;
};
