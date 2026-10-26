import { useCallback, useState, useSyncExternalStore } from 'react';

/** The viewer's choice for the map panel's look: follow the device (as the rest of the site does), or always light or dark. */
export type MapAppearance = 'device' | 'light' | 'dark';

const STORAGE_KEY = 'competitionMap.appearance';
const DARK_QUERY = '(prefers-color-scheme: dark)';

function readStored(): MapAppearance {
    try {
        const value = window.localStorage.getItem(STORAGE_KEY);
        return value === 'light' || value === 'dark' ? value : 'device';
    } catch {
        return 'device'; // storage blocked (private window): follow the device
    }
}

function subscribeToDevice(onChange: () => void) {
    const query = window.matchMedia?.(DARK_QUERY);
    query?.addEventListener('change', onChange);
    return () => query?.removeEventListener('change', onChange);
}

const deviceIsDark = () => !!window.matchMedia?.(DARK_QUERY).matches;

/**
 * The map panel's look, light or dark: the device's light or dark mode, like the rest of the site (base_tailwind.html),
 * unless the viewer picked one in the map's settings menu. The choice is kept in this browser only.
 */
export function useMapAppearance() {
    const [appearance, setAppearanceState] = useState<MapAppearance>(readStored);
    const dark = useSyncExternalStore(subscribeToDevice, deviceIsDark, () => true);

    const setAppearance = useCallback((next: MapAppearance) => {
        setAppearanceState(next);
        try {
            if (next === 'device') window.localStorage.removeItem(STORAGE_KEY);
            else window.localStorage.setItem(STORAGE_KEY, next);
        } catch {
            // Not kept, but still applied for this visit.
        }
    }, []);

    const resolved: 'light' | 'dark' = appearance === 'device' ? (dark ? 'dark' : 'light') : appearance;
    return { appearance, setAppearance, resolved };
}
