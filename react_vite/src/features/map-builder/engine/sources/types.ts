import type { Bounds, Frame } from '../tiles';
import type { FeaturesByLayer, TaskContext } from '../types';

export interface FetchResult {
    features: FeaturesByLayer;
    /** False when part of the data could not be downloaded; the result is then not reused. */
    complete: boolean;
}

/**
 * A provider of vector map data, read directly by the browser.
 *
 * To add a country-specific source (for example a national mapping agency's vector tiles):
 *  1. write a module that exports a `VectorSource`, mapping the provider's own feature classes
 *     onto the layer ids in `../layers.ts` (add new layers there if the provider has elements
 *     nobody else has);
 *  2. add it to `REGIONAL_SOURCES` in `./index.ts`.
 * Nothing else needs to change: the page offers the source whenever `covers()` says the selected
 * area is inside it, and any layer the source does not deliver is filled in from the global
 * OpenStreetMap source.
 *
 * The provider must allow cross-origin requests (CORS) from the browser - the Air Sports Live
 * Tracking server never fetches map data on the user's behalf.
 */
export interface VectorSource {
    id: string;
    /** Full name, shown in the source selector. */
    name: string;
    /** A few characters, shown as a badge next to each layer that comes from this source. */
    shortName: string;
    /** One sentence for the user about what choosing this source means. */
    description: string;
    /** Licence credit; ends up in the generated file and on printed maps. */
    attribution: string;
    /** Whether the source has data for this area. */
    covers(bounds: Bounds): boolean;
    /** The ids of the layers (see `../layers.ts`) this source can deliver. */
    layerIds: ReadonlySet<string>;
    /**
     * Download the features of the requested layers that fall inside the frame, in frame pixels.
     *
     * A source may return more layers than were asked for when they come at no extra cost (they
     * arrive in the same files or tiles); whatever is returned is kept, so switching such a layer
     * on later needs no new download. It must return an entry for every requested layer.
     */
    fetch(frame: Frame, layerIds: string[], context: TaskContext): Promise<FetchResult>;
}
