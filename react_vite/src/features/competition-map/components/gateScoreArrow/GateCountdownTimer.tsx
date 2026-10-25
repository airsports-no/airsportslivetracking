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
    /** Whether there is a prediction to show beside the countdown (not before the start, which has none). */
    predicted?: boolean;
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
    predicted = true,
}) => {
    const offsetColour = offsetWithinGrace ? "var(--hud-ok)" : "var(--hud-red)";
    const late = secondsToRequiredTime < 0;
    return (
        <div className="flex items-end justify-between gap-4 w-full"
            title="The big figure counts down to the gate's required time. The smaller one is how many seconds early (-) or late (+) the contestant is predicted to cross.">
            <div className="leading-tight min-w-0">
                {final || missed ? (
                    // The result of a gate just crossed, held for a few seconds: not the live countdown.
                    <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs min-[100rem]:text-base font-bold uppercase tracking-wide"
                        style={{ background: missed || !offsetWithinGrace ? "var(--hud-red)" : "var(--hud-ok)", color: "var(--hud-surface)" }}>
                        {missed ? "✗ Missed" : "✓ Passed"}
                    </span>
                ) : (
                    <div className="hud-label min-[100rem]:text-base">Next gate</div>
                )}
                <div className="hud-figure text-xl sm:text-2xl min-[100rem]:text-4xl truncate">{waypointName}</div>
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
                        {predicted && (
                            <div className="leading-none text-right">
                                <div className="hud-figure text-xl sm:text-2xl min-[100rem]:text-4xl" style={{ color: offsetColour }}>{formatOffset(crossingOffset)}</div>
                                <div className="hud-label min-[100rem]:text-base mt-1 hidden sm:block">Predicted</div>
                            </div>
                        )}
                        <div className="hud-figure text-3xl sm:text-5xl min-[100rem]:text-7xl leading-none" style={{ color: late ? "var(--hud-red)" : undefined }}>
                            {formatCountdown(secondsToRequiredTime)}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};

export default GateCountdownTimer;
