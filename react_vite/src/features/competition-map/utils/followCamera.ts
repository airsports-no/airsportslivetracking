/** A point on the map. */
export interface LatLon {
    lat: number;
    lon: number;
}

/** What the map shows now. */
export interface ViewBounds {
    south: number;
    west: number;
    north: number;
    east: number;
}

export type CameraMove =
    | { kind: 'stay' }
    | { kind: 'pan'; to: LatLon }
    | { kind: 'centre'; to: LatLon }
    | { kind: 'fit'; points: LatLon[] };

/** The aircraft may move freely within this share of the view, centred; leaving it pans the map. */
const COMFORT_SHARE = 0.7;

function insideComfort(view: ViewBounds, p: LatLon): boolean {
    const marginLat = ((view.north - view.south) * (1 - COMFORT_SHARE)) / 2;
    const marginLon = ((view.east - view.west) * (1 - COMFORT_SHARE)) / 2;
    return (
        p.lat >= view.south + marginLat && p.lat <= view.north - marginLat &&
        p.lon >= view.west + marginLon && p.lon <= view.east - marginLon
    );
}

/**
 * The follow camera's decision for one update: when the next gate changes (or is first known), show the aircraft and
 * that gate together; when following starts without a gate (a replay), centre on the aircraft close enough to see it
 * fly; otherwise move only when the aircraft leaves the middle of the view, so the map does not drift with every
 * position.
 */
export function cameraMove(
    view: ViewBounds, aircraft: LatLon, gate: LatLon | null, gateChanged: boolean, starting = false,
): CameraMove {
    if (gate && gateChanged) return { kind: 'fit', points: [aircraft, gate] };
    if (starting) return { kind: 'centre', to: aircraft };
    if (!insideComfort(view, aircraft)) return { kind: 'pan', to: aircraft };
    return { kind: 'stay' };
}
