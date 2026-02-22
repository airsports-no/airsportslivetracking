import React, { useState, useEffect, useRef } from "react";
import "./gateScore.css";
import GateScoreArrowRenderer from "./GateScoreArrowRenderer";
import GateCountdownTimer from "./GateCountdownTimer";
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

    // ... rest of the component

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
        if (!currentArrowData?.waypoint_name || !navigationTask.scorecard) return 0;

        try {
            const waypointType = getWaypointType(currentArrowData.waypoint_name);
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

    if (!currentArrowData || finished[contestant.id]) {
        return null;
    }

    return (
        <div className={"gate-score-arrow"} ref={containerRef}>
            <div className="flex justify-between items-start p-1">
                <div className={"gate-score-next-gate"}>
                    NEXT GATE: {currentArrowData.waypoint_name}
                </div>
                <GateCountdownTimer
                    secondsToPlannedCrossing={currentArrowData.seconds_to_planned_crossing}
                    crossingOffsetEstimate={currentArrowData.estimated_crossing_offset}
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
                    crossingOffsetEstimate={currentArrowData.estimated_crossing_offset}
                    estimatedScore={currentArrowData.estimated_score}
                    contestantId={contestant.id}
                    final={currentArrowData.final}
                    missed={currentArrowData.missed}
                />
            </div>
        </div>
    );
};


export default GateScoreArrowV2;
