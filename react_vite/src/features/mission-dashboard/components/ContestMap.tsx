import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import { Contest } from '../types';
import { useNavigate } from 'react-router-dom';
import useLeafletMap from '../../../hooks/useLeafletMap';

interface ContestMapProps {
    contests: Contest[];
    onBoundsChanged: (bounds: L.LatLngBounds) => void;
    minZoom?: number;
    onInteraction: () => void;
}

const ContestMap: React.FC<ContestMapProps> = ({ contests, onBoundsChanged, minZoom, onInteraction }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const map = useLeafletMap(containerRef, {
        initialCenter: [20, 0], // Default to global view
        initialZoom: minZoom ? Math.max(1, minZoom) : 1,
        zoomControl: false,
        minZoom: minZoom,
    });
    const wasHidden = useRef(false);
    const navigate = useNavigate();

    useEffect(() => {
        if (!map) return;

        // Clear existing markers
        map.eachLayer(layer => {
            if (layer instanceof L.Marker) {
                map.removeLayer(layer);
            }
        });

        const validContests = contests.filter(c => c.latitude != null && c.longitude != null);
        
        map.invalidateSize();

        if (validContests.length === 1) {
            map.setView([validContests[0].latitude, validContests[0].longitude], 13);
        } else if (validContests.length > 1) {
            const bounds = L.latLngBounds(validContests.map(c => [c.latitude, c.longitude]));
            map.fitBounds(bounds, { padding: [50, 50] });
        }

        validContests.forEach(contest => {
            const marker = L.marker([contest.latitude, contest.longitude]).addTo(map);
            marker.bindPopup(`<b>${contest.name}</b>`).on('click', () => {
                navigate(`/mission-dashboard/${contest.id}`);
            });
        });

    }, [contests, navigate, map]);

    useEffect(() => {
        if (!map || !onBoundsChanged) return;

        const handleMapChange = () => {
            onBoundsChanged(map.getBounds());
        };

        map.on('moveend', handleMapChange);
        map.on('zoomend', handleMapChange);

        return () => {
            map.off('moveend', handleMapChange);
            map.off('zoomend', handleMapChange);
        };
    }, [map, onBoundsChanged]);

    useEffect(() => {
        if (!map || !onInteraction) return;

        const handleFirstInteraction = () => {
            onInteraction();
            map.off('mousedown', handleFirstInteraction);
            map.off('zoomstart', handleFirstInteraction);
        };

        map.on('mousedown', handleFirstInteraction);
        map.on('zoomstart', handleFirstInteraction);

        return () => {
            map.off('mousedown', handleFirstInteraction);
            map.off('zoomstart', handleFirstInteraction);
        };
    }, [map, onInteraction]);

    useEffect(() => {
        if (!map || !containerRef.current) return;

        const resizeObserver = new ResizeObserver((entries) => {
            for (const entry of entries) {
                const { width, height } = entry.contentRect;
                if (width === 0 && height === 0) {
                    wasHidden.current = true;
                    if (onBoundsChanged) {
                        onBoundsChanged(null);
                    }
                } else {
                    map.invalidateSize();
                    if (wasHidden.current) {
                        wasHidden.current = false;
                        const validContests = contests.filter(c => c.latitude != null && c.longitude != null);
                        if (validContests.length === 1) {
                            map.setView([validContests[0].latitude, validContests[0].longitude], 13);
                        } else if (validContests.length > 1) {
                            const bounds = L.latLngBounds(validContests.map(c => [c.latitude, c.longitude]));
                            map.fitBounds(bounds, { padding: [50, 50] });
                        }
                    }
                }
            }
        });

        resizeObserver.observe(containerRef.current);

        return () => {
            resizeObserver.disconnect();
        };
    }, [map, containerRef, onBoundsChanged, contests, navigate]);


    return <div ref={containerRef} style={{ height: '400px', width: '100%' }} className="rounded-lg" />;
};

export default ContestMap;
