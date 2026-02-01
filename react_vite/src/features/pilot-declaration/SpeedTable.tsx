import React from 'react';
import { getDistance } from '../../utils/geoUtils';

interface SpeedTableProps {
    waypoints: any[];
    speeds: Record<string, number>;
    onChange: (speeds: Record<string, number>) => void;
}

export const SpeedTable: React.FC<SpeedTableProps> = ({ waypoints, speeds, onChange }) => {
    
    const handleSpeedChange = (gateName: string, value: string) => {
        const num = parseFloat(value);
        if (isNaN(num)) return;
        
        onChange({
            ...speeds,
            [gateName]: num
        });
    };

    // Filter out dummy points if any
    const validWaypoints = waypoints.filter(wp => wp.type !== 'dummy');

    return (
        <div className="overflow-x-auto">
            <table className="table table-zebra w-full">
                <thead>
                    <tr>
                        <th>Leg Start</th>
                        <th>Leg End</th>
                        <th>Distance (NM)</th>
                        <th>Declared Speed (kts)</th>
                        <th>Est. Duration</th>
                    </tr>
                </thead>
                <tbody>
                    {validWaypoints.map((wp, index) => {
                        if (index === validWaypoints.length - 1) return null;
                        const nextWp = validWaypoints[index + 1];
                        const speed = speeds[wp.name] || 0;
                        
                        // Calculate distance between points in NM
                        const distMeters = getDistance(
                            { lat: wp.latitude, lng: wp.longitude },
                            { lat: nextWp.latitude, lng: nextWp.longitude }
                        );
                        const distNm = distMeters / 1852;

                        let duration = "-";
                        if (speed > 0 && distNm > 0) {
                            const hours = distNm / speed;
                            const minutes = Math.floor(hours * 60);
                            const seconds = Math.round((hours * 3600) % 60);
                            duration = `${minutes}m ${seconds}s`;
                        }

                        return (
                            <tr key={`${wp.name}-${index}`}>
                                <td>{wp.name}</td>
                                <td>{nextWp.name}</td>
                                <td>{distNm.toFixed(2)}</td>
                                <td>
                                    <input 
                                        type="number" 
                                        className="input input-bordered input-sm w-24"
                                        value={speeds[wp.name] || ''}
                                        onChange={(e) => handleSpeedChange(wp.name, e.target.value)}
                                    />
                                </td>
                                <td>{duration}</td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
};
