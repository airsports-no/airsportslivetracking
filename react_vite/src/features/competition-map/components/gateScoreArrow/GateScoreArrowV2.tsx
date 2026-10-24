import React, { useState, useEffect, useRef } from "react";
import "./gateScore.css";
import GateScoreArrowRenderer from "./GateScoreArrowRenderer";
import GateCountdownTimer from "./GateCountdownTimer";
import { addLagSample, clockOffsetMs, secondsToRequiredTime, withinGrace } from "./gateCountdown";
import { Contestant, NavigationTask, GateArrowData, Waypoint, GateScoreRule } from "../../types";

interface GateScoreArrowV2Props {
    contestant: Contestant;
    navigationTask: NavigationTask; // Need this to get scorecard and waypoints
    gateArrowData?: GateArrowData;
}

const GATE_FREEZE_TIME = 15; // seconds

const GateScoreArrowV2: React.FC<GateScoreArrowV2Props> = ({
    contestant,
    navigationTask,
    gateArrowData,
}) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [size, setSize] = useState({ width: 512, height: 90 }); // Default aspect ratio

    useEffect(() => {
        const element = containerRef.current;
        if (!element) return;

        const observer = new ResizeObserver(entries => {
            if (entries[0]) {
                const { width } = entries[0].contentRect;
                if (width > 0) {
                    setSize({ width, height: (width * 90) / 512 });
                }
            }
        });
        observer.observe(element);
        return () => observer.disconnect();
    }, []);

    const [currentArrowData, setCurrentArrowData] = useState<GateArrowData | undefined>(gateArrowData);
    const [finished, setFinished] = useState<{ [key: number]: boolean }>({});
    const frozenTimeRef = useRef<number | null>(null);

    // Arrival minus position time of the recent messages, for the countdown's clock correction (gateCountdown.ts).
    // Kept per contestant: another contestant's positions come from another device clock.
    const lagSamplesRef = useRef<{ contestantId: number; samples: number[] }>({ contestantId: contestant.id, samples: [] });
    const [clockOffset, setClockOffset] = useState<{ contestantId: number; ms: number | null }>({ contestantId: contestant.id, ms: null });
    const delayMinutes = navigationTask.calculation_delay_minutes || 0;
    useEffect(() => {
        if (gateArrowData?.position_time && gateArrowData.received_at) {
            const previous = lagSamplesRef.current.contestantId === contestant.id ? lagSamplesRef.current.samples : [];
            const samples = addLagSample(previous, gateArrowData.received_at, new Date(gateArrowData.position_time).getTime());
            lagSamplesRef.current = { contestantId: contestant.id, samples };
            setClockOffset({ contestantId: contestant.id, ms: clockOffsetMs(samples, delayMinutes) });
        }
    }, [gateArrowData, delayMinutes, contestant.id]);
    const clockOffsetForContestant = clockOffset.contestantId === contestant.id ? clockOffset.ms : null;

    // The countdown ticks locally; the server only sends a new estimate now and then.
    const [nowMs, setNowMs] = useState(() => Date.now());
    const ticking = !!currentArrowData && !currentArrowData.final && !currentArrowData.missed;
    useEffect(() => {
        if (!ticking) return;
        const timer = setInterval(() => setNowMs(Date.now()), 200);
        return () => clearInterval(timer);
    }, [ticking]);

    const debugMode = false; // Toggle this to force display for placement work
    const displayData = currentArrowData || (debugMode ? {
        waypoint_name: "DEBUG GATE",
        seconds_to_planned_crossing: -15,
        estimated_crossing_offset: 5,
        estimated_score: 50,
        final: false,
        missed: false
    } : undefined);

    // Helper functions (converted from class methods)
    const getWaypointType = (waypointName: string) => {
        try {
            return navigationTask.route.waypoints.find((waypoint: Waypoint) => {
                return waypoint.name === waypointName;
            })?.type;
        } catch (e) {
            console.error("No type for waypoint name " + waypointName + ": " + e);
            return undefined;
        }
    };

    const getRule = (ruleName: string) => {
        const waypointName = displayData?.waypoint_name;
        if (!waypointName || !navigationTask.scorecard) return 0;

        try {
            const waypointType = getWaypointType(waypointName);
            if (!waypointType) return 0;

            const gateScore = navigationTask.scorecard.gatescore_set.find((gate: GateScoreRule) => {
                return gate.gate_type === waypointType;
            });
            
            return gateScore ? (gateScore[ruleName as keyof GateScoreRule] as number) : 0;
        } catch (e) {
            console.error("Unknown rule " + ruleName + ": " + e);
            return 0;
        }
    };

    const getGracePeriodBefore = () => getRule("graceperiod_before");
    const getGracePeriodAfter = () => getRule("graceperiod_after");
    const getPointsPerSecond = () => getRule("penalty_per_second");
    const getMaximumTimingPenalty = () => getRule("maximum_penalty");

    // Effect to handle updates similar to componentDidUpdate
    useEffect(() => {
        const isCurrentlyFrozen = frozenTimeRef.current && (new Date().getTime() - frozenTimeRef.current) < (GATE_FREEZE_TIME * 1000);

        if (gateArrowData) {
            if (gateArrowData.missed || gateArrowData.final) {
                // If a gate is missed or finalized, start freeze timer if not already frozen
                if (!isCurrentlyFrozen) {
                    frozenTimeRef.current = new Date().getTime();
                    setCurrentArrowData(gateArrowData); // Update immediately on final/missed
                }
            } else if (!isCurrentlyFrozen && gateArrowData !== currentArrowData) {
                // Only update if not frozen and data has actually changed
                frozenTimeRef.current = null; // Clear frozen state if new non-final/missed data comes in
                setCurrentArrowData(gateArrowData);
            }
        } else if (!isCurrentlyFrozen && currentArrowData) {
            // If gateArrowData becomes undefined/null and not frozen, clear currentArrowData
            setCurrentArrowData(undefined);
        }


        // Handle finished state for contestant
        if (contestant.contestanttrack && contestant.contestanttrack.passed_finish_gate && !finished[contestant.id]) {
            setTimeout(() => {
                setFinished(prev => ({ ...prev, [contestant.id]: true }));
            }, GATE_FREEZE_TIME * 1000);
        }
    }, [gateArrowData, currentArrowData, contestant, finished, navigationTask]);

    if (!displayData || finished[contestant.id]) {
        return null;
    }

    const secondsLeft =
        displayData.expected_time && clockOffsetForContestant !== null
            ? secondsToRequiredTime(nowMs, new Date(displayData.expected_time).getTime(), clockOffsetForContestant, delayMinutes)
            : // An older server sends no times: count on from what the last message said.
              -displayData.seconds_to_planned_crossing - (nowMs - (displayData.received_at ?? nowMs)) / 1000;

    return (
        <div className={"gate-score-arrow"} ref={containerRef}>
            <div className="flex items-end p-1">
                <GateCountdownTimer
                    waypointName={displayData.waypoint_name}
                    secondsToRequiredTime={secondsLeft}
                    crossingOffset={displayData.estimated_crossing_offset}
                    offsetWithinGrace={withinGrace(
                        displayData.estimated_crossing_offset,
                        getGracePeriodBefore(),
                        getGracePeriodAfter(),
                    )}
                    final={displayData.final}
                    missed={displayData.missed}
                />
            </div>
            <div className={"gate-arrow-shadow"}>
                <GateScoreArrowRenderer
                    width={size.width}
                    height={size.height}
                    pointsPerSecond={getPointsPerSecond()}
                    maximumTimingPenalty={getMaximumTimingPenalty()}
                    gracePeriodBefore={getGracePeriodBefore()}
                    gracePeriodAfter={getGracePeriodAfter()}
                    crossingOffsetEstimate={displayData.estimated_crossing_offset}
                    estimatedScore={displayData.estimated_score}
                    contestantId={contestant.id}
                    final={displayData.final}
                    missed={displayData.missed}
                />
            </div>
        </div>
    );
};


export default GateScoreArrowV2;
