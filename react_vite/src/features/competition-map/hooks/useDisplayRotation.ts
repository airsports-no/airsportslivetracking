import { useEffect, useRef } from 'react';
import { rotationAt, RotationStep } from '../utils/displayRotation';

/** How long a touch, click or key holds the rotation, so a person can look around. */
const PAUSE_MS = 120_000;

/**
 * Runs the unattended screen's rotation (see rotationAt): `onStep` is called whenever it moves on to another step. Any
 * click, touch, wheel or key holds it for two minutes, after which it starts again from the overview.
 */
export function useDisplayRotation({ enabled, flyingIds, onStep }: {
    enabled: boolean;
    flyingIds: number[];
    onStep: (step: RotationStep) => void;
}) {
    const startedRef = useRef(0);
    const heldUntilRef = useRef(0);
    const lastRef = useRef<string | null>(null);
    const flyingRef = useRef(flyingIds);
    const onStepRef = useRef(onStep);
    useEffect(() => {
        flyingRef.current = flyingIds;
        onStepRef.current = onStep;
    });

    useEffect(() => {
        if (!enabled) return;
        startedRef.current = Date.now();
        lastRef.current = null;
        const hold = () => {
            heldUntilRef.current = Date.now() + PAUSE_MS;
            lastRef.current = null;
        };
        const tick = () => {
            const now = Date.now();
            if (now < heldUntilRef.current) return;
            if (heldUntilRef.current !== 0) {
                heldUntilRef.current = 0;
                startedRef.current = now; // back from a pause: from the overview
            }
            const step = rotationAt(now - startedRef.current, flyingRef.current);
            const key = step.kind === 'overview' ? 'overview' : `follow-${step.id}`;
            if (key === lastRef.current) return;
            lastRef.current = key;
            onStepRef.current(step);
        };
        tick();
        const timer = window.setInterval(tick, 1000);
        window.addEventListener('pointerdown', hold);
        window.addEventListener('keydown', hold);
        window.addEventListener('wheel', hold, { passive: true });
        return () => {
            window.clearInterval(timer);
            window.removeEventListener('pointerdown', hold);
            window.removeEventListener('keydown', hold);
            window.removeEventListener('wheel', hold);
        };
    }, [enabled]);
}
