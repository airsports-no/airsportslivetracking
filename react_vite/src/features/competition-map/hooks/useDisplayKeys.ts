import { useEffect, useRef } from 'react';
import { DisplayKeyAction, displayKeyAction } from '../utils/displayKeys';

/** Whether a key press is typing in a field, where it must not steer the display. */
function inField(target: EventTarget | null): boolean {
    const el = target as HTMLElement | null;
    return !!el && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName));
}

/** Whether the focus is on a control that uses the arrow keys itself (a button, a link, a slider, a menu). */
function usesArrows(target: EventTarget | null): boolean {
    const el = target as HTMLElement | null;
    return !!el && (['BUTTON', 'A', 'SUMMARY'].includes(el.tagName) || !!el.closest?.('[role="slider"], [role="tablist"], [role="menu"], .leaflet-control'));
}

/** The display's keys (see displayKeyAction), while `enabled`. */
export function useDisplayKeys({ enabled, onAction }: { enabled: boolean; onAction: (action: DisplayKeyAction) => void }) {
    const onActionRef = useRef(onAction);
    useEffect(() => {
        onActionRef.current = onAction;
    });
    useEffect(() => {
        if (!enabled) return;
        const pressed = (e: KeyboardEvent) => {
            if (inField(e.target)) return;
            const action = displayKeyAction(e);
            if (!action) return;
            if (action.kind === 'step' && usesArrows(e.target)) return;
            e.preventDefault();
            onActionRef.current(action);
        };
        window.addEventListener('keydown', pressed);
        return () => window.removeEventListener('keydown', pressed);
    }, [enabled]);
}
