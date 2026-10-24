import { RefObject, useCallback, useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { cameraMove, LatLon } from '../utils/followCamera';

/** The closest the camera zooms in when it shows the aircraft and its next gate. */
const MAX_FIT_ZOOM = 13;
/** The zoom it starts following at without a gate (a replay): close enough to see the aircraft move. */
const FOLLOW_ZOOM = 12;

/**
 * Keeps the followed aircraft in view (see cameraMove). Moving the map by hand pauses it, so the viewer can look
 * around; `resume` (the "Follow again" button) starts it again. A new contestant to follow starts it again too.
 */
export function useFollowCamera({ mapRef, enabled, followId, aircraft, gate }: {
    mapRef: RefObject<L.Map | null>;
    enabled: boolean;
    /** Who is followed: following someone else starts the camera again. */
    followId: number | null;
    aircraft: LatLon | null;
    gate: { name: string; position: LatLon } | null;
}) {
    const [paused, setPaused] = useState<{ id: number | null } | null>(null);
    const isPaused = paused !== null && paused.id === followId;
    const lastGateRef = useRef<string | null>(null);
    // Whether the next move is the first since following started (or was resumed, or switched on).
    const startingRef = useRef(true);

    // Only what a person does pauses it: a drag, the mouse wheel, a double-click or a two-finger pinch. (Leaflet's
    // zoom and move events do not tell the camera's own moves, or the map fitting the route on load, from the viewer's.)
    useEffect(() => {
        const map = mapRef.current;
        if (!map || !enabled) return;
        const byViewer = () => setPaused({ id: followId });
        const pinch = (e: TouchEvent) => { if (e.touches.length > 1) byViewer(); };
        const container = map.getContainer();
        map.on('dragstart', byViewer);
        container.addEventListener('wheel', byViewer, { passive: true });
        container.addEventListener('dblclick', byViewer);
        container.addEventListener('touchstart', pinch, { passive: true });
        return () => {
            map.off('dragstart', byViewer);
            container.removeEventListener('wheel', byViewer);
            container.removeEventListener('dblclick', byViewer);
            container.removeEventListener('touchstart', pinch);
        };
    }, [mapRef, enabled, followId]);

    useEffect(() => {
        // The first update for someone new, or after the camera is switched on, frames them afresh.
        lastGateRef.current = null;
        startingRef.current = true;
    }, [followId, enabled]);

    // Plain values, so the camera reacts to a new position or gate and not to new objects with the same values.
    const aLat = aircraft?.lat, aLon = aircraft?.lon;
    const gName = gate?.name ?? null, gLat = gate?.position.lat, gLon = gate?.position.lon;
    useEffect(() => {
        const map = mapRef.current;
        if (!map || !enabled || isPaused || aLat === undefined || aLon === undefined) return;
        const b = map.getBounds();
        const gatePosition = gName !== null && gLat !== undefined && gLon !== undefined ? { lat: gLat, lon: gLon } : null;
        const gateChanged = gatePosition !== null && gName !== lastGateRef.current;
        const move = cameraMove(
            { south: b.getSouth(), west: b.getWest(), north: b.getNorth(), east: b.getEast() },
            { lat: aLat, lon: aLon },
            gatePosition,
            gateChanged,
            startingRef.current,
        );
        startingRef.current = false;
        if (gatePosition) lastGateRef.current = gName;
        if (move.kind === 'stay') return;
        if (move.kind === 'pan') {
            map.panTo([move.to.lat, move.to.lon], { animate: true, duration: 0.8 });
        } else if (move.kind === 'centre') {
            map.setView([move.to.lat, move.to.lon], Math.max(map.getZoom(), FOLLOW_ZOOM), { animate: true });
        } else {
            map.fitBounds(L.latLngBounds(move.points.map(p => [p.lat, p.lon] as [number, number])), {
                padding: [80, 80],
                maxZoom: MAX_FIT_ZOOM,
                animate: true,
            });
        }
    }, [mapRef, enabled, isPaused, aLat, aLon, gName, gLat, gLon]);

    const resume = useCallback(() => {
        lastGateRef.current = null;
        startingRef.current = true;
        setPaused(null);
    }, []);

    return { paused: enabled && isPaused, resume };
}
