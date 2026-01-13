import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import { Contest } from '../types';
import { useNavigate } from 'react-router-dom';
import useLeafletMap from '../../../hooks/useLeafletMap';

interface ContestMapProps {
    contests: Contest[];
    onBoundsChanged: (bounds: L.LatLngBounds) => void;
}

const ContestMap: React.FC<ContestMapProps> = ({ contests, onBoundsChanged }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const map = useLeafletMap(containerRef, {
        initialCenter: [20, 0], // Default to global view
        initialZoom: 2, // Default zoom level
        zoomControl: false,
    });
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

        if(validContests.length > 0) {
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
        
        // Initial bounds update after map is ready and possibly fit to bounds
        handleMapChange();

        return () => {
            map.off('moveend', handleMapChange);
            map.off('zoomend', handleMapChange);
        };
    }, [map, onBoundsChanged]); // No need for contests.length, as map.fitBounds will trigger events


    return <div ref={containerRef} style={{ height: '400px', width: '100%' }} className="rounded-lg" />;
};

export default ContestMap;
