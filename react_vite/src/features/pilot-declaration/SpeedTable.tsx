import React from 'react';

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
                        
                        let duration = "-";
                        if (speed > 0 && wp.distance_next > 0) {
                            const hours = wp.distance_next / speed;
                            const minutes = Math.round(hours * 60);
                            const seconds = Math.round((hours * 3600) % 60);
                            duration = `${minutes}m ${seconds}s`;
                        }

                        return (
                            <tr key={wp.name}>
                                <td>{wp.name}</td>
                                <td>{nextWp.name}</td>
                                <td>{wp.distance_next.toFixed(2)}</td>
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
