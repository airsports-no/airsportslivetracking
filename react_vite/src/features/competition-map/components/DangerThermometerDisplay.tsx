import React from 'react';
import { DangerData } from '../types';

interface Props {
    dangerData?: DangerData;
}

const DangerThermometerDisplay = ({ dangerData }: Props) => {
    const value = dangerData?.danger_level ?? 0;
    const accumulatedScore = dangerData?.accumulated_score ?? 0;

    const clamped = Math.max(0, Math.min(100, value));

    return (
        <div className="flex flex-col items-center">
            {clamped === 100 && accumulatedScore > 0 && (
                <div className="relative mb-2">
                    <img alt="Accumulated score background" src={`${document.configuration.STATIC_FILE_LOCATION}img/gate_score_arrow_black.gif`} style={{width: "100px"}}/>
                    <div className="absolute inset-0 flex items-center justify-center text-white font-bold text-[10px]">
                        {accumulatedScore}
                    </div>
                </div>
            )}
            <div className="relative w-6 h-48">
                <div className="absolute inset-0 rounded-full bg-base-300/50" />
                <div
                className="absolute bottom-0 w-full rounded-b-full bg-red-500"
                style={{ height: `${clamped}%`, transition: 'height 0.3s ease' }}
                />
            </div>
            <div className="mt-1 text-lg text-black bg-white">{clamped.toFixed(0)}%</div>
        </div>
    );
}

export default DangerThermometerDisplay;
