import React from "react";

interface GateCountdownTimerProps {
    secondsToPlannedCrossing: number;
    crossingOffsetEstimate: number;
}

const GateCountdownTimer: React.FC<GateCountdownTimerProps> = ({ secondsToPlannedCrossing, crossingOffsetEstimate }) => {
    // Note that the seconds to planned crossing is negative before and positive after. We therefore play with 
    // signs to make it correct.
    return (
        <div className="gate-score-next-gate text-right">
            <div
                className={`${secondsToPlannedCrossing >= 1 ? "text-red-600" : ""}`}
            >
                COUNTDOWN SEC {secondsToPlannedCrossing <= 0 ? (-secondsToPlannedCrossing).toFixed(0) : secondsToPlannedCrossing.toFixed(0)}s
                <span className="text-base ml-2">({crossingOffsetEstimate < 0 ? "" : "+"}{crossingOffsetEstimate.toFixed(0)}s)</span>
            </div>
        </div>
    );
}

export default GateCountdownTimer;
