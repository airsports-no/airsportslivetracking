import React, { useEffect, useState } from 'react';
import { Map as MapIcon, Maximize, Minimize } from 'lucide-react';

interface Props {
    /** Zooms the map out to the whole route. */
    onFitRoute: () => void;
    /** On air the buttons show only while the mouse moves, so they stay out of the picture. */
    hideWhenIdle: boolean;
}

/** How long the buttons stay after the mouse last moved, where they hide when idle. */
const IDLE_MS = 2500;

/** The map's own buttons, top right: full screen on and off, and fit the whole route. */
export default function MapControls({ onFitRoute, hideWhenIdle }: Props) {
    const [fullScreen, setFullScreen] = useState(() => !!document.fullscreenElement);
    const [active, setActive] = useState(true);

    useEffect(() => {
        const changed = () => setFullScreen(!!document.fullscreenElement);
        document.addEventListener('fullscreenchange', changed);
        return () => document.removeEventListener('fullscreenchange', changed);
    }, []);

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

    const toggleFullScreen = () => {
        if (document.fullscreenElement) void document.exitFullscreen();
        else void document.documentElement.requestFullscreen?.();
    };
    const canFullScreen = !!document.documentElement.requestFullscreen;
    const shown = !hideWhenIdle || active;

    return (
        <div className={`hud absolute top-3 right-3 z-[1100] flex flex-col gap-1 p-1 rounded-lg border hud-divider shadow-lg transition-opacity ${shown ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
            {canFullScreen && (
                <button className="hud-button" onClick={toggleFullScreen} aria-pressed={fullScreen}
                    aria-label={fullScreen ? 'Leave full screen' : 'Full screen'} title={fullScreen ? 'Leave full screen' : 'Full screen'}>
                    {fullScreen ? <Minimize size={18} /> : <Maximize size={18} />}
                </button>
            )}
            <button className="hud-button" onClick={onFitRoute} aria-label="Show the whole route" title="Show the whole route">
                <MapIcon size={18} />
            </button>
        </div>
    );
}
