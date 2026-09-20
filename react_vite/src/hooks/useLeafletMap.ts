import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Import images directly so Vite handles pathing.
import iconRetinaUrl from '/leaflet/marker-icon-2x.png';
import iconUrl from '/leaflet/marker-icon.png';
import shadowUrl from '/leaflet/marker-shadow.png';

// Fix for Leaflet's default icon path issue with bundlers.
// This directly manipulates the prototype to ensure all new markers
// use the correct, imported assets.
// @ts-ignore
delete L.Icon.Default.prototype._getIconUrl;

L.Icon.Default.mergeOptions({
  iconRetinaUrl: iconRetinaUrl,
  iconUrl: iconUrl,
  shadowUrl: shadowUrl,
});

interface UseLeafletMapOptions {
    initialCenter?: L.LatLngExpression;
    initialZoom?: number;
    zoomControl?: boolean;
    minZoom?: number;
    maxZoom?: number;
}

/**
 * Hook to initialize a Leaflet map within a given HTML element.
 * @param {React.RefObject<HTMLDivElement>} mapContainerRef A ref to the HTMLDivElement that will contain the map.
 * @param {UseLeafletMapOptions} options Configuration options for the map.
 * @returns {L.Map | null} The Leaflet map instance.
 */
export default function useLeafletMap(
    mapContainerRef: React.RefObject<HTMLDivElement | null>,
    options?: UseLeafletMapOptions
): L.Map | null {
    const [map, setMap] = useState<L.Map | null>(null);
    // Synchronous guard against React StrictMode's dev-only double-invoke of effects: creation
    // and cleanup used to live in two separate effects, each keyed off the `map` *state* value.
    // On StrictMode's mount -> cleanup -> remount replay, the cleanup effect's closure still saw
    // the pre-setMap `null`, so it never removed the map the setup effect had just created -
    // the remount's setup effect then called L.map() on the same container a second time, and
    // Leaflet throws "Map container is already initialized". A ref (updated synchronously,
    // unlike state) plus creating/removing the instance within the same effect closes that gap:
    // the cleanup that runs before a replay always tears down exactly the instance that replay's
    // own setup would otherwise collide with.
    const mapInstanceRef = useRef<L.Map | null>(null);

    useEffect(() => {
        if (!mapContainerRef.current || mapInstanceRef.current) return;

        var southWest = L.latLng(-90, -180),
        northEast = L.latLng(90, 180),
        bounds = L.latLngBounds(southWest, northEast);
        const mapInstance = L.map(mapContainerRef.current, {
            zoomControl: options?.zoomControl ?? true,
            minZoom: options?.minZoom,
            maxZoom: options?.maxZoom,
            maxBounds: bounds
        }).setView(
            options?.initialCenter ?? [20, 0], // Default to global view
            options?.initialZoom ?? 2 // Default zoom level
        );

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            noWrap: true
        }).addTo(mapInstance);

        mapInstanceRef.current = mapInstance;
        setMap(mapInstance);

        return () => {
            // Leaflet workaround (Sentry JAVASCRIPT-REACT-5): map.remove() stops pan/fly
            // animations and removes the map's DOM pane, but never resets _animatingZoom nor
            // cancels the raw setTimeout(_onZoomTransitionEnd, 250) that _animateZoom
            // schedules. If we unmount mid zoom-animation, that timeout later fires
            // _onZoomTransitionEnd against an already-removed map and crashes.
            // _onZoomTransitionEnd's own first line is `if (!this._animatingZoom) return;`,
            // so forcing the flag off here makes the stale timeout a no-op.
            (mapInstance as unknown as { _animatingZoom?: boolean })._animatingZoom = false;
            mapInstance.remove();
            mapInstanceRef.current = null;
        };
        // options is only ever read for the map's initial setup (zoom/center/bounds), not meant
        // to be reactive - re-running this effect on every new inline options object would fight
        // the mapInstanceRef guard for no benefit. See ContestMap.tsx/LocationMapField.tsx's call
        // sites, both of which pass a fresh object literal per render.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [mapContainerRef]);

    return map;
}
