import { useEffect, useRef } from 'react';
import { DisplayKeyAction, displayKeyAction } from '../utils/displayKeys';

/** Whether a key press is typing in a field, where it must not steer the display. */
function inField(target: EventTarget | null): boolean {
    const el = target as HTMLElement | null;
    return !!el && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName));
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
            e.preventDefault();
            onActionRef.current(action);
        };
        window.addEventListener('keydown', pressed);
        return () => window.removeEventListener('keydown', pressed);
    }, [enabled]);
}
