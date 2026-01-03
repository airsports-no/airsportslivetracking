import React from 'react';
import { GateArrowData } from '../types';

interface Props {
    gateArrowData?: GateArrowData;
}

const GateScoreArrow = ({ gateArrowData }: Props) => {
    if (!gateArrowData) {
        return <div className="w-48 h-24 bg-base-300/50 rounded flex items-center justify-center text-sm text-white/70">No gate data</div>;
    }
    
    const { waypoint_name, seconds_to_planned_crossing, estimated_crossing_offset, estimated_score } = gateArrowData;

    // Simple arrow representation, can be improved with SVG
    const arrowRotation = Math.max(-90, Math.min(90, estimated_crossing_offset * 5));

    return (
        <div className="text-white p-2 rounded-lg" style={{textShadow: '0 1px 3px rgba(0,0,0,0.5)'}}>
            <div className="text-center font-bold">{waypoint_name}</div>
            <div className="flex justify-between text-lg">
                <span>{Math.abs(seconds_to_planned_crossing)}s</span>
                <span>{estimated_score > 0 ? '+' : ''}{estimated_score}</span>
            </div>
            <div className="h-10 flex items-center justify-center">
                 <div className="relative w-full h-1 bg-white/50 rounded-full">
                    <div className="absolute top-1/2 left-1/2 text-3xl" style={{transform: `translate(-50%, -50%) rotate(${arrowRotation}deg)`}}>
                        &#9650;
                    </div>
                </div>
            </div>
        </div>
    );
};

export default GateScoreArrow;
