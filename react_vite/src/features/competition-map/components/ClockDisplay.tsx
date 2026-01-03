import React from 'react';

interface Props {
    time: Date;
}

const ClockDisplay: React.FC<Props> = ({ time }) => {
    const formattedTime = time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone: 'UTC' });
    
    return (
        <div className="font-mono bg-base-100/80 backdrop-blur-sm border border-base-300 rounded-lg shadow-lg py-1 px-3">
            {formattedTime} UTC
        </div>
    );
};

export default ClockDisplay;
