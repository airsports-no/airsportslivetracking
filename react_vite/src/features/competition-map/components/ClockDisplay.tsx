import React from 'react';

interface Props {
    time: Date;
    timeZone?: string;
}

const ClockDisplay: React.FC<Props> = ({ time, timeZone = 'UTC' }) => {
    const formattedTime = time.toLocaleTimeString([], { 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit', 
        hour12: false, 
        timeZone: timeZone 
    });

    const timeZoneName = new Intl.DateTimeFormat([], { timeZone: timeZone, timeZoneName: 'short' })
        .formatToParts(time)
        .find(part => part.type === 'timeZoneName')?.value;
    
    return (
        <div className="font-mono bg-base-100/80 backdrop-blur-sm border border-base-300 rounded-lg shadow-lg py-0.5 px-2 sm:py-1 sm:px-3 text-xs sm:text-base">
            {formattedTime} {timeZoneName}
        </div>
    );
};

export default ClockDisplay;
