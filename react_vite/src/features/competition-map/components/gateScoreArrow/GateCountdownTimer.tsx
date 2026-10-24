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
 * to cross. Counting down to the predicted crossing instead would jump with every new estimate. Styled for the map's
 * dark follow bar (components/hud/hud.css).
 */
const GateCountdownTimer: React.FC<GateCountdownTimerProps> = ({
    waypointName,
    secondsToRequiredTime,
    crossingOffset,
    offsetWithinGrace,
    final,
    missed,
}) => {
    const offsetColour = offsetWithinGrace ? "var(--hud-ok)" : "var(--hud-red)";
    const late = secondsToRequiredTime < 0;
    return (
        <div className="flex items-end justify-between gap-4 w-full"
            title="The big figure counts down to the gate's required time. The smaller one is how many seconds early (-) or late (+) the contestant is predicted to cross.">
            <div className="leading-tight min-w-0">
                <div className="hud-label min-[100rem]:text-base">{final || missed ? "Gate" : "Next gate"}</div>
                <div className="hud-figure text-2xl min-[100rem]:text-4xl truncate">{waypointName}</div>
            </div>
            <div className="flex items-end gap-4">
                {missed ? (
                    <div className="hud-figure text-4xl min-[100rem]:text-6xl leading-none" style={{ color: "var(--hud-red)" }}>Missed</div>
                ) : final ? (
                    <div className="leading-none text-right">
                        <div className="hud-figure text-4xl min-[100rem]:text-6xl" style={{ color: offsetColour }}>{formatOffset(crossingOffset)}</div>
                        <div className="hud-label min-[100rem]:text-base mt-1">Crossed</div>
                    </div>
                ) : (
                    <>
                        <div className="leading-none text-right">
                            <div className="hud-figure text-2xl min-[100rem]:text-4xl" style={{ color: offsetColour }}>{formatOffset(crossingOffset)}</div>
                            <div className="hud-label min-[100rem]:text-base mt-1">Predicted</div>
                        </div>
                        <div className="hud-figure text-5xl min-[100rem]:text-7xl leading-none" style={{ color: late ? "var(--hud-red)" : undefined }}>
                            {formatCountdown(secondsToRequiredTime)}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};

export default GateCountdownTimer;
