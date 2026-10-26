import React, { useEffect, useState } from 'react';
import { Map as MapIcon, X } from 'lucide-react';

/** How the map is shown: the usual page, an airfield screen, or a clean picture for broadcast (?display=...). */
export type DisplayMode = 'standard' | 'screen' | 'broadcast';

interface Props {
    display: DisplayMode;
    /** Back to the standard view (in broadcast mode, where the panel and its settings menu are not there). */
    onLeaveBroadcast: () => void;
    /** Zooms the map out to the whole route. */
    onFitRoute: () => void;
}

/** How long the buttons stay after the mouse last moved, in broadcast mode. */
const IDLE_MS = 2500;

/**
 * The map's own buttons, top right: fit the whole route, and in broadcast mode a way out of it. (The display choice
 * is in the settings menu, and full screen is the browser's own, F11.) On air the buttons show only while the mouse
 * moves, so they stay out of the picture.
 */
export default function MapControls({ display, onLeaveBroadcast, onFitRoute }: Props) {
    const hideWhenIdle = display === 'broadcast';
    const [active, setActive] = useState(true);

    useEffect(() => {
        if (!hideWhenIdle) return;
        let timer = window.setTimeout(() => setActive(false), IDLE_MS);
        const moved = () => {
            setActive(true);
            window.clearTimeout(timer);
            timer = window.setTimeout(() => setActive(false), IDLE_MS);
        };
        window.addEventListener('mousemove', moved);
        window.addEventListener('touchstart', moved);
        return () => {
            window.clearTimeout(timer);
            window.removeEventListener('mousemove', moved);
            window.removeEventListener('touchstart', moved);
        };
    }, [hideWhenIdle]);

    const shown = !hideWhenIdle || active;

    return (
        <div className={`hud absolute top-3 right-3 z-[1100] flex flex-col gap-1 p-1 rounded-lg border hud-divider shadow-lg transition-opacity ${shown ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
            <button className="hud-button" onClick={onFitRoute} aria-label="Show the whole route" title="Show the whole route">
                <MapIcon size={18} />
            </button>
            {display === 'broadcast' && (
                <button className="hud-button" onClick={onLeaveBroadcast} aria-label="Leave broadcast" title="Leave broadcast">
                    <X size={18} />
                </button>
            )}
        </div>
    );
}
