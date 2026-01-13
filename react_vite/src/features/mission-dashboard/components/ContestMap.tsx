import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import { Contest } from '../types';
import { useNavigate } from 'react-router-dom';
import useLeafletMap from '../../../hooks/useLeafletMap';

interface ContestMapProps {
    contests: Contest[];
}

const ContestMap: React.FC<ContestMapProps> = ({ contests }) => {
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

            validContests.forEach(contest => {
                const marker = L.marker([contest.latitude, contest.longitude]).addTo(map);
                marker.bindPopup(`<b>${contest.name}</b>`).on('click', () => {
                    navigate(`/mission-dashboard/${contest.id}`);
                });
            });
        }

    }, [contests, navigate, map]);

    return <div ref={containerRef} style={{ height: '400px', width: '100%' }} className="rounded-lg" />;
};

export default ContestMap;
