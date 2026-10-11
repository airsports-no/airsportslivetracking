import { useEffect, useRef } from 'react';
import L from 'leaflet';
import type { PhotoObservation } from '../types';

export interface TargetPhoto {
    id: number | null;
    name: string;
    file: string | null;
    latitude: number;
    longitude: number;
    // Contestant-specific coordinates as [longitude, latitude]
    compiled_coordinates?: [number, number] | null;
}

interface PhotoLayersProps {
    mapRef: React.MutableRefObject<L.Map | null>;
    photos: TargetPhoto[];
    observations: PhotoObservation[];
    visible: boolean;
}

const escapeHtml = (value: string) =>
    value.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] as string));

// Green when fully scored, amber for partial, red for no score and grey when it could not be scored
export function observationColour(observation: PhotoObservation): string {
    if (!observation.scored) return '#6b7280';
    if (observation.score_fraction >= 1) return '#16a34a';
    if (observation.score_fraction > 0) return '#d97706';
    return '#dc2626';
}

export function describeObservation(observation: PhotoObservation): string {
    const time = new Date(observation.time).toLocaleTimeString();
    if (!observation.scored) {
        return `Observation of <b>${escapeHtml(observation.photo_name)}</b> at ${time}<br/>Not scored (${escapeHtml(observation.status)})`;
    }
    const error = observation.error_mm !== null ? `${observation.error_mm.toFixed(1)} mm (${Math.round(observation.error_m ?? 0)} m) along track` : '';
    const reason = observation.status === 'out_of_track' ? '<br/>Out of track' : '';
    return `Observation of <b>${escapeHtml(observation.photo_name)}</b> at ${time}<br/>${error}${reason}<br/>Score: ${observation.score_fraction}`;
}

const targetIcon = (name: string) =>
    L.divIcon({
        className: '',
        html: `<div style="background:#2563eb;color:#fff;border:2px solid #fff;border-radius:50%;width:22px;height:22px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;box-shadow:0 0 3px #000;">${escapeHtml(name.slice(0, 2))}</div>`,
        iconSize: [22, 22],
        iconAnchor: [11, 11],
    });

const observationIcon = (colour: string) =>
    L.divIcon({
        className: '',
        html: `<div style="background:${colour};border:2px solid #fff;border-radius:3px;width:14px;height:14px;transform:rotate(45deg);box-shadow:0 0 3px #000;"></div>`,
        iconSize: [14, 14],
        iconAnchor: [7, 7],
    });

/**
 * Draws the observation photo targets (a labelled point whose hover shows the photo) and, for the selected
 * contestant, where each observation was registered, linked to the point on the track it was projected to.
 */
export function usePhotoLayers({ mapRef, photos, observations, visible }: PhotoLayersProps) {
    const groupRef = useRef<L.LayerGroup | null>(null);

    useEffect(() => {
        const map = mapRef.current;
        if (!map) return;
        if (!groupRef.current) {
            groupRef.current = L.layerGroup().addTo(map);
        }
        const group = groupRef.current;
        group.clearLayers();
        if (!visible) return;

        photos.forEach((photo) => {
            const [lng, lat] = photo.compiled_coordinates ?? [photo.longitude, photo.latitude];
            if (lat == null || lng == null) return;
            const marker = L.marker([lat, lng], { icon: targetIcon(photo.name), zIndexOffset: 500 });
            const image = photo.file
                ? `<img src="${escapeHtml(photo.file)}" alt="${escapeHtml(photo.name)}" style="display:block;width:260px;max-width:60vw;border-radius:4px;"/>`
                : '';
            marker.bindTooltip(`<div><b>${escapeHtml(photo.name)}</b>${image}</div>`, {
                direction: 'right',
                opacity: 1,
                sticky: false,
            });
            marker.addTo(group);
        });

        observations.forEach((observation) => {
            const colour = observationColour(observation);
            const marker = L.marker([observation.latitude, observation.longitude], {
                icon: observationIcon(colour),
                zIndexOffset: 600,
            });
            marker.bindTooltip(describeObservation(observation), { direction: 'top' });
            marker.addTo(group);
            if (observation.projected_latitude != null && observation.projected_longitude != null) {
                L.polyline(
                    [
                        [observation.latitude, observation.longitude],
                        [observation.projected_latitude, observation.projected_longitude],
                    ],
                    { color: colour, weight: 2, dashArray: '3 4' },
                ).addTo(group);
            }
            // The segment between where the crew marked the track and where the target projects onto it
            if (
                observation.projected_latitude != null &&
                observation.projected_longitude != null &&
                observation.photo_projected_latitude != null &&
                observation.photo_projected_longitude != null
            ) {
                L.polyline(
                    [
                        [observation.projected_latitude, observation.projected_longitude],
                        [observation.photo_projected_latitude, observation.photo_projected_longitude],
                    ],
                    { color: colour, weight: 5, opacity: 0.8 },
                ).addTo(group);
            }
        });
    }, [mapRef, photos, observations, visible]);

    useEffect(
        () => () => {
            groupRef.current?.remove();
            groupRef.current = null;
        },
        [],
    );
}
