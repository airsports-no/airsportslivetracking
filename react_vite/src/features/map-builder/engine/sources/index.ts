import type { LayerDefinition } from '../layers';
import type { Bounds } from '../tiles';
import { ignSpainSource } from './ignSpain';
import { overtureSource } from './overture';
import type { VectorSource } from './types';

export type { VectorSource } from './types';

/** Worldwide coverage; fills in whatever a regional source does not deliver. */
export const BASE_SOURCE: VectorSource = overtureSource;

/** Country-specific sources, offered when the selected area is inside their coverage. */
export const REGIONAL_SOURCES: VectorSource[] = [ignSpainSource];

export const ALL_SOURCES: VectorSource[] = [BASE_SOURCE, ...REGIONAL_SOURCES];

export const sourceById = (id: string): VectorSource => ALL_SOURCES.find(source => source.id === id) ?? BASE_SOURCE;

/** The sources the user can choose between for this area, the global one first. */
export const sourcesCovering = (bounds: Bounds): VectorSource[] => [
    BASE_SOURCE,
    ...REGIONAL_SOURCES.filter(source => source.covers(bounds)),
];

/**
 * Which source to select when the area changes: keep the user's choice while it still covers the
 * area, otherwise prefer a regional source (official survey data) over the global one.
 */
export function preferredSourceId(bounds: Bounds, preference: string | null): string {
    const available = sourcesCovering(bounds);
    if (preference && available.some(source => source.id === preference)) return preference;
    return (available[1] ?? BASE_SOURCE).id;
}

/**
 * The sources a layer is drawn from when `selectedId` is the chosen source. Empty when the layer
 * does not exist with that choice (elements only a regional source has).
 */
export function sourcesForLayer(layer: LayerDefinition, selectedId: string): VectorSource[] {
    const selected = sourceById(selectedId);
    const inBase = BASE_SOURCE.layerIds.has(layer.id);
    if (selected !== BASE_SOURCE && selected.layerIds.has(layer.id)) {
        return layer.combineSources && inBase ? [selected, BASE_SOURCE] : [selected];
    }
    return inBase ? [BASE_SOURCE] : [];
}
