import React from "react";
import { formatCountdown, formatOffset } from "./gateCountdown";

interface GateCountdownTimerProps {
    waypointName: string;
    /** Seconds left until the gate's required time, negative once it has passed. */
    secondsToRequiredTime: number;
    /** Predicted (or, once final, actual) crossing minus required time in seconds; positive is late. */
    crossingOffset: number;
    offsetWithinGrace: boolean;
    final: boolean;
    missed: boolean;
}

/**
 * One large countdown to the gate's REQUIRED time, which never moves, and beside it how far off the pilot is predicted
 * to cross. Counting down to the predicted crossing instead would jump with every new estimate.
 */
const GateCountdownTimer: React.FC<GateCountdownTimerProps> = ({
    waypointName,
    secondsToRequiredTime,
    crossingOffset,
    offsetWithinGrace,
    final,
    missed,
}) => {
    const offsetColour = offsetWithinGrace ? "bg-success text-success-content" : "bg-error text-error-content";
    const late = secondsToRequiredTime < 0;
    return (
        <div className="gate-score-next-gate flex items-end justify-between gap-4 w-full">
            <div className="leading-tight">
                <div className="text-xs opacity-70">{final || missed ? "GATE" : "NEXT GATE"}</div>
                <div className="text-2xl">{waypointName}</div>
            </div>
            <div className="flex items-end gap-3">
                {missed ? (
                    <div className="text-4xl text-error">MISSED</div>
                ) : final ? (
                    <div className={`badge badge-lg text-2xl h-auto py-1 px-3 ${offsetColour}`}>{formatOffset(crossingOffset)}</div>
                ) : (
                    <>
                        <div className="flex flex-col items-end leading-tight">
                            <div className="text-xs opacity-70">PREDICTED</div>
                            <div className={`badge badge-lg font-bold ${offsetColour}`}>{formatOffset(crossingOffset)}</div>
                        </div>
                        <div className={`text-5xl tabular-nums leading-none ${late ? "text-error" : ""}`}>
                            {formatCountdown(secondsToRequiredTime)}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};

export default GateCountdownTimer;
