import React from "react";

interface GateCountdownTimerProps {
    secondsToPlannedCrossing: number;
    crossingOffsetEstimate: number;
}

const GateCountdownTimer: React.FC<GateCountdownTimerProps> = ({ secondsToPlannedCrossing, crossingOffsetEstimate }) => {
    // Note that the seconds to planned crossing is negative before and positive after. We therefore play with 
    // signs to make it correct.
    return (
        <div className="text-black mt-2"> {/* color: black; margin-top: 7px; */}
            <div
                className={`text-center text-xl ${secondsToPlannedCrossing >= 1 ? "text-red-600" : ""}`} // text-align: center; font-size: x-large; color: #e50000;
            >
                {secondsToPlannedCrossing <= 0 ? (-secondsToPlannedCrossing).toFixed(0) : secondsToPlannedCrossing.toFixed(0)}
            </div>
            <div className="text-center text-xs w-full">COUNTDOWN SEC</div> {/* font-size: 8px; width: 100vw; (changed to w-full) */}
            <div className="text-center text-base"> {/* text-align: center; font-size: medium; */}
                {crossingOffsetEstimate < 0 ? "-" : "+"}{Math.abs(crossingOffsetEstimate).toFixed(0)}s
            </div>
        </div>
    );
}

export default GateCountdownTimer;
