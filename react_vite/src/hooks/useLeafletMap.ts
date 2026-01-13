import { useEffect, useState } from 'react';
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
}

/**
 * Hook to initialize a Leaflet map within a given HTML element.
 * @param {React.RefObject<HTMLDivElement>} mapContainerRef A ref to the HTMLDivElement that will contain the map.
 * @param {UseLeafletMapOptions} options Configuration options for the map.
 * @returns {L.Map | null} The Leaflet map instance.
 */
export default function useLeafletMap(
    mapContainerRef: React.RefObject<HTMLDivElement>,
    options?: UseLeafletMapOptions
): L.Map | null {
    const [map, setMap] = useState<L.Map | null>(null);

    useEffect(() => {
        if (mapContainerRef.current && !map) {
            const mapInstance = L.map(mapContainerRef.current, {
                zoomControl: options?.zoomControl ?? true,
            }).setView(
                options?.initialCenter ?? [20, 0], // Default to global view
                options?.initialZoom ?? 2 // Default zoom level
            );

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            }).addTo(mapInstance);

            setMap(mapInstance);
        }
    }, [mapContainerRef, options, map]);

    useEffect(() => {
        // Cleanup function for when the component unmounts
        return () => {
            if (map) {
                map.remove();
            }
        };
    }, [map]);

    return map;
}
