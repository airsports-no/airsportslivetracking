import { reverse } from '../../urls';
import { getCookie } from '../../utils/csrf';

/** The server's limit on the length of a map's attribution text. */
export const MAX_ATTRIBUTION_LENGTH = 100;

export interface SaveMapRequest {
    name: string;
    file: Uint8Array;
    defaultZoom: number;
    attribution: string;
}

export const fileNameFor = (name: string): string =>
    `${name.trim().replace(/[^\p{L}\p{N}_-]+/gu, '_').replace(/^_+|_+$/g, '') || 'map'}.mbtiles`;

/**
 * Stores a generated map in the user's "My maps", through the same view as the upload form (so the
 * same validation and processing apply). Throws an Error with a message fit for the user.
 */
export async function saveGeneratedMap(request: SaveMapRequest): Promise<void> {
    const body = new FormData();
    body.append('name', request.name);
    body.append('default_zoom_level', String(request.defaultZoom));
    body.append('attribution', request.attribution.slice(0, MAX_ATTRIBUTION_LENGTH));
    body.append('user', String(document.configuration.userId ?? ''));
    body.append('map_file', new Blob([request.file as BlobPart], { type: 'application/vnd.sqlite3' }), fileNameFor(request.name));

    let response: Response;
    try {
        response = await fetch(reverse('useruploadedmap_add'), {
            method: 'POST',
            headers: { Accept: 'application/json', 'X-CSRFToken': getCookie('csrftoken') ?? '' },
            body,
        });
    } catch {
        throw new Error('The map could not be sent. Check your connection and try again.');
    }
    if (response.status === 201) return;
    if (response.status === 400) {
        const errors: Record<string, string[]> = (await response.json().catch(() => ({}))).errors ?? {};
        const messages = Object.values(errors).flat();
        throw new Error(messages.length ? messages.join(' ') : 'The server did not accept the map.');
    }
    if (response.status === 403 || response.redirected) {
        throw new Error('You need to be signed in as an organiser to save maps. You can still download the file.');
    }
    if (response.status === 413) {
        throw new Error('The file is too large for the server to accept. Make the area smaller or drop a zoom level.');
    }
    throw new Error(`The server could not store the map (HTTP ${response.status}).`);
}
