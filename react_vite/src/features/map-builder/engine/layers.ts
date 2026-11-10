/**
 * The catalogue of map elements a user can switch on or off, and how each one is drawn.
 *
 * This file only describes *appearance*. Where the data for a layer comes from is decided by the
 * data sources in `sources/`, each of which declares which of these layer ids it can deliver.
 * The order of the list is the drawing order (later entries are drawn on top), with all point
 * symbols drawn last.
 */

export type LayerGroupId = 'land' | 'water' | 'roads' | 'infrastructure' | 'points';

export const LAYER_GROUPS: { id: LayerGroupId; label: string }[] = [
    { id: 'land', label: 'Land cover' },
    { id: 'water', label: 'Water' },
    { id: 'roads', label: 'Roads and railways' },
    { id: 'infrastructure', label: 'Infrastructure' },
    { id: 'points', label: 'Point symbols' },
];

export type SymbolName = 'triangle' | 'castle' | 'antenna' | 'aerodrome' | 'wind' | 'mill' | 'church';

interface LayerBase {
    id: string;
    label: string;
    group: LayerGroupId;
    /** Switched on when the page is first opened. */
    defaultOn: boolean;
    color: string;
    /**
     * Features that matter to a pilot (runways, aerodromes) are taken from every source that has
     * them, not only from the selected one, so that a gap in one data set does not hide them.
     */
    combineSources?: boolean;
}

export interface FillLayer extends LayerBase {
    kind: 'fill';
    alpha: number;
    /** Painted over the terrain shading instead of being blended with it. */
    opaque?: boolean;
    /** Polygons smaller than this many square pixels at the detail zoom are left out. */
    minimumArea?: number;
}

export interface LineLayer extends LayerBase {
    kind: 'line';
    width: number;
    dash?: number[];
    /** Some sources deliver this element as an outline polygon (runways); fill those solid. */
    fillPolygons?: boolean;
}

export interface PointLayer extends LayerBase {
    kind: 'point';
    symbol: SymbolName;
    size: number;
}

export type LayerDefinition = FillLayer | LineLayer | PointLayer;

export const LAYERS: LayerDefinition[] = [
    // Sea is first so that it replaces the terrain shading before anything else is drawn.
    { id: 'sea', label: 'Sea', group: 'water', kind: 'fill', color: '#b9d3ee', alpha: 1, opaque: true, defaultOn: true },

    { id: 'forest', label: 'Forest', group: 'land', kind: 'fill', color: '#9fc58a', alpha: 0.43, defaultOn: true },
    { id: 'built_up', label: 'Built-up area', group: 'land', kind: 'fill', color: '#c9b37e', alpha: 0.67, defaultOn: true },
    { id: 'industrial', label: 'Industrial area', group: 'land', kind: 'fill', color: '#b7a6b7', alpha: 0.6, defaultOn: false },
    { id: 'quarry', label: 'Quarry', group: 'land', kind: 'fill', color: '#c8b8a0', alpha: 0.8, defaultOn: false },
    // The minimum area drops rooftop panels.
    { id: 'solar_farm', label: 'Solar farm', group: 'land', kind: 'fill', color: '#5c6bc0', alpha: 0.55, minimumArea: 20, defaultOn: true },

    { id: 'lake', label: 'Lake, reservoir or pond', group: 'water', kind: 'fill', color: '#7fb0e0', alpha: 1, minimumArea: 2, defaultOn: true },
    { id: 'stream', label: 'Stream', group: 'water', kind: 'line', color: '#8db6e0', width: 0.8, defaultOn: true },
    { id: 'canal', label: 'Canal', group: 'water', kind: 'line', color: '#4f86c6', width: 1.0, defaultOn: true },
    { id: 'river', label: 'River', group: 'water', kind: 'line', color: '#3d78c2', width: 2.2, defaultOn: true },
    { id: 'dam', label: 'Dam', group: 'water', kind: 'line', color: '#333333', width: 3, defaultOn: false },

    { id: 'track', label: 'Track', group: 'roads', kind: 'line', color: '#a39472', width: 0.6, defaultOn: true },
    { id: 'local_road', label: 'Local road', group: 'roads', kind: 'line', color: '#8a8a8a', width: 0.7, defaultOn: true },
    { id: 'tertiary_road', label: 'Tertiary road', group: 'roads', kind: 'line', color: '#e6b23a', width: 1.6, defaultOn: true },
    { id: 'secondary_road', label: 'Secondary road', group: 'roads', kind: 'line', color: '#f0a020', width: 2.0, defaultOn: true },
    { id: 'primary_road', label: 'Primary road', group: 'roads', kind: 'line', color: '#e8602c', width: 2.6, defaultOn: true },
    { id: 'motorway', label: 'Motorway or trunk road', group: 'roads', kind: 'line', color: '#d7301f', width: 3.2, defaultOn: true },
    { id: 'railway', label: 'Railway', group: 'roads', kind: 'line', color: '#222222', width: 1.6, defaultOn: true },

    { id: 'power_line', label: 'High-voltage power line', group: 'infrastructure', kind: 'line', color: '#d0306a', width: 1.0, dash: [9, 6], defaultOn: true },
    { id: 'minor_power_line', label: 'Medium-voltage power line', group: 'infrastructure', kind: 'line', color: '#e57ca5', width: 0.8, dash: [3, 4], defaultOn: true },
    { id: 'runway', label: 'Runway', group: 'infrastructure', kind: 'line', color: '#333333', width: 4.0, fillPolygons: true, combineSources: true, defaultOn: true },

    { id: 'aerodrome', label: 'Aerodrome', group: 'points', kind: 'point', color: '#7b1fa2', symbol: 'aerodrome', size: 6, combineSources: true, defaultOn: true },
    { id: 'peak', label: 'Peak', group: 'points', kind: 'point', color: '#8b4513', symbol: 'triangle', size: 3.6, defaultOn: true },
    { id: 'mast', label: 'Communications mast', group: 'points', kind: 'point', color: '#000000', symbol: 'antenna', size: 3.6, defaultOn: true },
    { id: 'castle', label: 'Castle or defensive tower', group: 'points', kind: 'point', color: '#000000', symbol: 'castle', size: 3.6, defaultOn: true },
    { id: 'wind_turbine', label: 'Wind turbine', group: 'points', kind: 'point', color: '#1565c0', symbol: 'wind', size: 8, defaultOn: true },
    { id: 'mill', label: 'Traditional mill', group: 'points', kind: 'point', color: '#5d4037', symbol: 'mill', size: 3.6, defaultOn: false },
    { id: 'church', label: 'Church or chapel', group: 'points', kind: 'point', color: '#000000', symbol: 'church', size: 3.4, defaultOn: false },
];

export const LAYERS_BY_ID: Record<string, LayerDefinition> = Object.fromEntries(LAYERS.map(layer => [layer.id, layer]));

export const defaultLayerSelection = (): Record<string, boolean> =>
    Object.fromEntries(LAYERS.map(layer => [layer.id, layer.defaultOn]));
