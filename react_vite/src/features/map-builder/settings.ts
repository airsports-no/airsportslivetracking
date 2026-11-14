import type { TerrainOptions } from './engine/generate';
import { defaultLayerSelection } from './engine/layers';

/** What the page remembers between visits (in this browser only). */
export interface BuilderSettings {
    /** Text of the four coordinate fields, so that half-typed values survive. */
    west: string;
    south: string;
    east: string;
    north: string;
    minZoom: number;
    maxZoom: number;
    layers: Record<string, boolean>;
    /** The data source the user last picked; null until they pick one. */
    sourcePreference: string | null;
    terrain: TerrainOptions;
    lowerLevels: 'scaled' | 'redrawn';
    lineScale: number;
    name: string;
}

/** Zoom levels offered for the most detailed level of a map. */
export const DETAIL_ZOOMS = [12, 13, 14];
/** How many levels below the detail level a map may reach. */
export const MAX_EXTRA_LEVELS = 3;

export const DEFAULT_SETTINGS: BuilderSettings = {
    west: '',
    south: '',
    east: '',
    north: '',
    minZoom: 12,
    maxZoom: 13,
    layers: defaultLayerSelection(),
    sourcePreference: null,
    terrain: { hillshade: true, exaggeration: 1.8, intensity: 0.82, contours: false, contourInterval: 50 },
    lowerLevels: 'redrawn',
    lineScale: 1,
    name: '',
};

const STORAGE_KEY = 'aslt_map_builder';

export function loadSettings(): BuilderSettings {
    try {
        const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null');
        if (!stored || typeof stored !== 'object') return DEFAULT_SETTINGS;
        const settings: BuilderSettings = {
            ...DEFAULT_SETTINGS,
            ...stored,
            // Merge so that layers and options added in a later version get their defaults.
            layers: { ...DEFAULT_SETTINGS.layers, ...stored.layers },
            terrain: { ...DEFAULT_SETTINGS.terrain, ...stored.terrain },
        };
        if (!DETAIL_ZOOMS.includes(settings.maxZoom)) settings.maxZoom = DEFAULT_SETTINGS.maxZoom;
        settings.minZoom = Math.min(settings.maxZoom, Math.max(settings.maxZoom - MAX_EXTRA_LEVELS, settings.minZoom));
        if (!Number.isFinite(settings.lineScale) || settings.lineScale <= 0) settings.lineScale = DEFAULT_SETTINGS.lineScale;
        return settings;
    } catch {
        return DEFAULT_SETTINGS;
    }
}

export function saveSettings(settings: BuilderSettings): void {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    } catch {
        // Private browsing or a full store: the page works without remembering.
    }
}
