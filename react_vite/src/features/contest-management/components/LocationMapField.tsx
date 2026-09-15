import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import useLeafletMap from '../../../hooks/useLeafletMap';

interface LocationMapFieldProps {
    value: string;
    onChange: (value: string) => void;
}

// Oslo - a more useful default center than the ocean at (0,0) for a location that hasn't been set
// yet (most contests using this form so far have been in Norway).
const DEFAULT_CENTER: [number, number] = [59.91, 10.75];

function parseLocation(value: string): [number, number] | null {
    const [latStr, lonStr] = (value ?? '').split(',');
    const lat = parseFloat(latStr);
    const lon = parseFloat(lonStr);
    return Number.isFinite(lat) && Number.isFinite(lon) ? [lat, lon] : null;
}

// Small embedded map, mirroring the classic ContestForm's django-location-field widget: click
// anywhere or drag the marker to set the contest's lat,lon instead of typing coordinates by hand.
const LocationMapField: React.FC<LocationMapFieldProps> = ({ value, onChange }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const initialParsed = parseLocation(value);
    const map = useLeafletMap(containerRef, {
        initialCenter: initialParsed ?? DEFAULT_CENTER,
        initialZoom: initialParsed ? 9 : 4,
    });
    const markerRef = useRef<L.Marker | null>(null);
    // Keeps the click/dragend handlers calling the latest onChange without having to recreate the
    // marker (and its listeners) every time the parent re-renders with a new inline callback.
    const onChangeRef = useRef(onChange);
    useEffect(() => {
        onChangeRef.current = onChange;
    }, [onChange]);

    useEffect(() => {
        if (!map) return;
        const initial = parseLocation(value) ?? DEFAULT_CENTER;
        const marker = L.marker(initial, { draggable: true }).addTo(map);
        markerRef.current = marker;

        const emitChange = (latlng: L.LatLng) => onChangeRef.current(`${latlng.lat.toFixed(6)},${latlng.lng.toFixed(6)}`);
        marker.on('dragend', () => emitChange(marker.getLatLng()));
        const handleMapClick = (event: L.LeafletMouseEvent) => {
            marker.setLatLng(event.latlng);
            emitChange(event.latlng);
        };
        map.on('click', handleMapClick);

        return () => {
            map.off('click', handleMapClick);
            marker.remove();
            markerRef.current = null;
        };
        // Deliberately only re-runs when the map instance itself changes - re-reads `value` fresh
        // from the closure at setup time, and the sync effect below handles later external changes.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [map]);

    // Keep the marker in sync when `value` changes from outside (typing directly into the text
    // input, or the form loading its initial value) - skip moves that already match the marker's
    // current position so a drag/click's own onChange round-trip doesn't fight the gesture.
    useEffect(() => {
        if (!map || !markerRef.current) return;
        const parsed = parseLocation(value);
        if (!parsed) return;
        const current = markerRef.current.getLatLng();
        if (Math.abs(current.lat - parsed[0]) > 1e-6 || Math.abs(current.lng - parsed[1]) > 1e-6) {
            markerRef.current.setLatLng(parsed);
            map.setView(parsed, Math.max(map.getZoom(), 9));
        }
    }, [value, map]);

    return <div ref={containerRef} className="rounded-lg border border-base-300" style={{ height: '200px', width: '100%' }} />;
};

export default LocationMapField;
