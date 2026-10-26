import React, { useState, useEffect, useRef } from "react";
import "./gateScore.css";
import GateScoreArrowRenderer from "./GateScoreArrowRenderer";
import GateCountdownTimer from "./GateCountdownTimer";
import { useMapClock } from "../../utils/mapClock";
import { addLagSample, clockOffsetMs, secondsToRequiredTime, withinGrace } from "./gateCountdown";
import { Contestant, NavigationTask, GateArrowData, Waypoint, GateScoreRule } from "../../types";

interface GateScoreArrowV2Props {
    contestant: Contestant;
    navigationTask: NavigationTask; // Need this to get scorecard and waypoints
    gateArrowData?: GateArrowData;
    /** Whether the viewer sees secret and unknown-leg gates: no countdown to them otherwise. */
    showSecrets?: boolean;
    /** The danger level (0-100) and the penalty accumulated, shown in the top row where its bar is horizontal (below lg). */
    danger?: { level: number; accumulated: number } | null;
}

// How long before a set start time the countdown to it shows.
const START_COUNTDOWN_WINDOW_MS = 30 * 60_000;

const GATE_FREEZE_TIME = 5; // seconds a gate's result stays up before the countdown moves on

/**
 * The danger level as a horizontal strip, wherever the bar is horizontal (below lg): between the gate's name and the
 * figures, or on its own once the arrow is gone (after the finish line there can still be a zone to keep out of). From
 * lg the bar is vertical, at the far right beside the arrow (FollowBar).
 */
const DangerStrip: React.FC<{ danger: { level: number; accumulated: number }; className?: string }> = ({ danger, className = "" }) => (
    <div className={`flex items-center gap-1.5 ${className}`} title="How close the contestant is to a penalty">
        <span className="hud-label flex-none">Danger</span>
        <div className="relative h-1.5 flex-1 rounded-full overflow-hidden" style={{ background: "var(--hud-raised)" }}>
            <div className="absolute left-0 top-0 h-full" style={{ width: `${danger.level}%`, background: danger.level >= 100 ? "var(--hud-red)" : "var(--hud-warn)" }} />
        </div>
        <span className="hud-figure text-sm leading-none" style={{ color: danger.level >= 100 ? "var(--hud-red)" : undefined }}>
            {danger.level.toFixed(0)}%
        </span>
        {danger.level >= 100 && danger.accumulated > 0 && (
            // The penalty so far for being outside the corridor or inside a zone: a tag of its own.
            <span className="hud-figure text-sm leading-none rounded px-1 py-0.5 flex-none"
                style={{ background: "var(--hud-red)", color: "var(--hud-surface)" }}
                title="Penalty points accumulated outside the corridor or inside a zone">
                +{Math.round(danger.accumulated)} pts
            </span>
        )}
    </div>
);

const GateScoreArrowV2: React.FC<GateScoreArrowV2Props> = ({
    contestant,
    navigationTask,
    gateArrowData,
    showSecrets = true,
    danger = null,
}) => {
    // A callback ref, not a mount-time effect: the container is only rendered once there is something to show, and an
    // arrow that appears later (a contestant selected before the start) must be measured then, or it stays small.
    const [container, setContainer] = useState<HTMLDivElement | null>(null);
    // The scale has a set height rather than growing with its width as it used to: taller as it gets wider (an event
    // display), so its labels stay readable from a distance.
    const [size, setSize] = useState({ width: 512, height: 76 });

    useEffect(() => {
        const element = container;
        if (!element) return;

        const observer = new ResizeObserver(entries => {
            if (entries[0]) {
                const { width } = entries[0].contentRect;
                if (width > 0) {
                    setSize({ width, height: width >= 1000 ? 112 : width >= 700 ? 96 : width < 480 ? 52 : 76 });
                }
            }
        });
        observer.observe(element);
        return () => observer.disconnect();
    }, [container]);

    const [currentArrowData, setCurrentArrowData] = useState<GateArrowData | undefined>(gateArrowData);
    const [finished, setFinished] = useState<{ [key: number]: boolean }>({});
    const frozenUntilRef = useRef(0);

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
            const ms = clockOffsetMs(samples, delayMinutes);
            setClockOffset({ contestantId: contestant.id, ms });
            useMapClock.getState().set(contestant.id, ms);
        }
    }, [gateArrowData, delayMinutes, contestant.id]);
    const clockOffsetForContestant = clockOffset.contestantId === contestant.id ? clockOffset.ms : null;

    // The countdown ticks locally; the server only sends a new estimate now and then.
    const [nowMs, setNowMs] = useState(() => Date.now());
    // A start at a set time is counted down to as any gate is. An adaptive start is not: the pilot crosses when ready.
    const startName = navigationTask.route.waypoints.find((waypoint: Waypoint) => waypoint.type === "sp")?.name;
    const startTimeMs = startName && contestant.gate_times?.[startName] ? new Date(contestant.gate_times[startName]).getTime() : null;
    const countingToStart = !currentArrowData
        && !contestant.adaptive_start
        && !contestant.contestanttrack?.passed_starting_gate
        && startName !== undefined
        && startTimeMs !== null
        && startTimeMs - (nowMs - delayMinutes * 60_000) < START_COUNTDOWN_WINDOW_MS;
    const ticking = countingToStart || (!!currentArrowData && !currentArrowData.final && !currentArrowData.missed);
    // Before the start's window opens the clock still moves, slowly, or the window would never be seen to open.
    const waitingForStart = !contestant.adaptive_start && !contestant.contestanttrack?.passed_starting_gate && startTimeMs !== null;
    useEffect(() => {
        if (!ticking && !waitingForStart) return;
        const timer = setInterval(() => setNowMs(Date.now()), ticking ? 200 : 5000);
        return () => clearInterval(timer);
    }, [ticking, waitingForStart]);

    const debugMode = false; // Toggle this to force display for placement work
    const startData: GateArrowData | undefined = countingToStart && startName && startTimeMs !== null
        ? {
            waypoint_name: startName,
            seconds_to_planned_crossing: 0,
            estimated_crossing_offset: 0,
            estimated_score: 0,
            final: false,
            missed: false,
            expected_time: new Date(startTimeMs).toISOString(),
        }
        : undefined;
    const displayData = currentArrowData || startData || (debugMode ? {
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

    // What the arrow shows follows the server's messages, with a gate's result held up for GATE_FREEZE_TIME seconds
    // before it moves on: the results wait their turn when gates come close together, an estimate for a gate that has
    // had its result is stale and skipped, and so is anything for a gate the viewer does not see. The hold ends by
    // itself (a timer), not with the next message.
    const queuedResultsRef = useRef<GateArrowData[]>([]);
    const seenRef = useRef(new WeakSet<GateArrowData>());
    const lastResultRef = useRef<GateArrowData | null>(null);
    const settledGateRef = useRef<string | null>(null);
    const [releaseTick, setReleaseTick] = useState(0);
    const hiddenFromViewer = (waypointName: string) => {
        const type = getWaypointType(waypointName);
        return (type === "secret" || type === "ul") && !showSecrets;
    };

    useEffect(() => {
        const now = Date.now();
        if (gateArrowData && !seenRef.current.has(gateArrowData)) {
            seenRef.current.add(gateArrowData);
            if ((gateArrowData.final || gateArrowData.missed) && !hiddenFromViewer(gateArrowData.waypoint_name)) {
                queuedResultsRef.current = [...queuedResultsRef.current, gateArrowData].slice(-3);
            }
        }
        if (now < frozenUntilRef.current) {
            const timer = window.setTimeout(() => setReleaseTick(tick => tick + 1), frozenUntilRef.current - now + 20);
            return () => window.clearTimeout(timer);
        }
        const nextResult = queuedResultsRef.current.shift();
        if (nextResult) {
            frozenUntilRef.current = now + GATE_FREEZE_TIME * 1000;
            lastResultRef.current = nextResult;
            settledGateRef.current = nextResult.waypoint_name;
            setCurrentArrowData(nextResult);
            return;
        }
        // Nothing waiting: the latest estimate, unless it is stale or not for the viewer's eyes, then nothing (the
        // arrow is back when the next gate has an estimate).
        const usable = gateArrowData
            && !gateArrowData.final && !gateArrowData.missed
            && gateArrowData.waypoint_name !== settledGateRef.current
            && !hiddenFromViewer(gateArrowData.waypoint_name);
        if (usable) {
            settledGateRef.current = null;
            if (gateArrowData !== currentArrowData) setCurrentArrowData(gateArrowData);
        } else if (currentArrowData) {
            setCurrentArrowData(undefined);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [gateArrowData, currentArrowData, releaseTick, showSecrets, navigationTask]);

    // The arrow is gone a little after the finish line, once its result has been seen.
    useEffect(() => {
        if (!contestant.contestanttrack?.passed_finish_gate || finished[contestant.id]) return;
        const timer = window.setTimeout(() => {
            setFinished(prev => ({ ...prev, [contestant.id]: true }));
        }, GATE_FREEZE_TIME * 1000);
        return () => window.clearTimeout(timer);
    }, [contestant.id, contestant.contestanttrack?.passed_finish_gate, finished]);

    if (!displayData || finished[contestant.id]) {
        // No arrow (before the first estimate, after the finish line): the danger bar stays on phones, where it was
        // part of the arrow.
        return danger ? <DangerStrip danger={danger} className="lg:hidden px-1" /> : null;
    }

    const secondsLeft =
        displayData.expected_time && (clockOffsetForContestant !== null || startData)
            ? secondsToRequiredTime(nowMs, new Date(displayData.expected_time).getTime(), clockOffsetForContestant ?? 0, delayMinutes)
            : // An older server sends no times: count on from what the last message said.
              -displayData.seconds_to_planned_crossing - (nowMs - (displayData.received_at ?? nowMs)) / 1000;

    return (
        <div
            className={"gate-score-arrow" + (displayData.final || displayData.missed ? " rounded-lg px-2 -mx-2" : "")}
            ref={setContainer}
            // A recorded result (held a few seconds) looks unlike the live countdown: tinted, with an edge in its colour.
            style={displayData.final || displayData.missed ? {
                background: "var(--hud-raised)",
                borderLeft: `4px solid ${displayData.missed || !withinGrace(displayData.estimated_crossing_offset, getGracePeriodBefore(), getGracePeriodAfter()) ? "var(--hud-red)" : "var(--hud-ok)"}`,
            } : undefined}
        >
            <div className="flex items-end pb-1 sm:pb-1.5">
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
                    predicted={!startData}
                    middle={danger && <DangerStrip danger={danger} className="lg:hidden flex-1 min-w-0 self-center px-2" />}
                />
            </div>
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
                showPointer={!startData}
            />
        </div>
    );
};


export default GateScoreArrowV2;
