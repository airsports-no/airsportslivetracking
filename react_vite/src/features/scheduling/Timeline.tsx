import React, { useMemo, useRef } from 'react';
import Draggable, { DraggableData, DraggableEvent } from 'react-draggable';

interface TimelineProps {
    navigationTask: any;
    onUpdate: (contestantId: number, data: any) => void;
}

const PIXELS_PER_MINUTE = 5;
const ROW_HEIGHT = 60;
const HEADER_HEIGHT = 30;

interface ContestantBarProps {
    contestant: any;
    minTime: number;
    onUpdate: (contestantId: number, data: any) => void;
    msToPixels: (ms: number) => number;
    pixelsToMs: (px: number) => number;
    formatTime: (date: string | number) => string;
}

const ContestantBar: React.FC<ContestantBarProps> = ({ contestant, minTime, onUpdate, msToPixels, pixelsToMs, formatTime }) => {
    const nodeRef = useRef(null); // Ref for Draggable

    const isAdaptive = contestant.adaptive_start;
    const trackerStart = new Date(contestant.tracker_start_time).getTime();
    const takeoff = new Date(contestant.takeoff_time).getTime();
    const finish = new Date(contestant.finished_by_time).getTime();
    const landing = contestant.landing_time_after_final_gate 
        ? new Date(contestant.landing_time_after_final_gate).getTime() 
        : finish;

    let blockStartTime = isAdaptive ? trackerStart : takeoff;
    let blockEndTime = isAdaptive ? finish : landing;

    // Relative positions
    const startPx = msToPixels(blockStartTime - minTime);
    const widthPx = msToPixels(blockEndTime - blockStartTime);
    const takeoffPx = msToPixels(takeoff - blockStartTime);

    const isLocked = contestant.contestanttrack?.calculator_started;

    const handleStop = (e: DraggableEvent, data: DraggableData) => {
        if (isLocked) return;
        
        const deltaX = data.x - startPx;
        if (Math.abs(deltaX) < 1) return; // Ignore micro-moves

        const deltaMs = pixelsToMs(deltaX);

        const newTrackerStart = new Date(trackerStart + deltaMs);
        const newTakeoff = new Date(takeoff + deltaMs);
        const newFinish = new Date(finish + deltaMs);

        onUpdate(contestant.id, {
            tracker_start_time: newTrackerStart.toISOString(),
            takeoff_time: newTakeoff.toISOString(),
            finished_by_time: newFinish.toISOString()
        });
    };

    return (
        <Draggable
            nodeRef={nodeRef}
            axis="x"
            position={{ x: startPx, y: 0 }}
            onStop={handleStop}
            disabled={isLocked}
            bounds={{ left: 0 }}
        >
            <div 
                ref={nodeRef}
                className={`absolute top-3 h-10 rounded-md shadow-sm cursor-grab active:cursor-grabbing text-xs flex items-center overflow-hidden whitespace-nowrap z-20 hover:z-30 hover:shadow-md transition-shadow
                    ${isLocked ? 'bg-gray-400 cursor-not-allowed' : 'bg-primary text-primary-content'}
                `}
                style={{ width: widthPx }}
                title={`#${contestant.contestant_number} ${contestant.team.crew.member1.last_name}`}
            >
                {isAdaptive && (
                    <div className="h-full bg-black/10 border-r border-black/20" style={{ width: takeoffPx }} />
                )}
                
                {/* Content */}
                <div className="h-full flex-1 flex flex-col justify-center px-2 min-w-0">
                    <div className="font-bold truncate">#{contestant.contestant_number} {contestant.team.crew.member1.last_name}</div>
                    <div className="opacity-80 text-[10px] truncate">{formatTime(blockStartTime)} - {formatTime(blockEndTime)}</div>
                </div>
            </div>
        </Draggable>
    );
};

interface AircraftRowProps {
    registration: string;
    contestants: any[];
    minTime: number;
    onUpdate: (contestantId: number, data: any) => void;
    msToPixels: (ms: number) => number;
    pixelsToMs: (px: number) => number;
    formatTime: (date: string | number) => string;
}

const AircraftRow: React.FC<AircraftRowProps> = ({ registration, contestants, minTime, onUpdate, msToPixels, pixelsToMs, formatTime }) => {
    return (
        <div className="relative border-b border-base-200 bg-base-100" style={{ height: ROW_HEIGHT }}>
            {/* Label */}
            <div className="absolute left-0 top-0 bottom-0 w-40 bg-base-200/50 z-10 flex flex-col justify-center px-2 border-r border-base-300 text-sm shadow-sm font-medium">
                <div className="truncate">{registration}</div>
            </div>

            {/* Bar Container */}
            <div className="absolute top-0 bottom-0 right-0 left-40 overflow-hidden">
                {contestants.map(contestant => (
                    <ContestantBar
                        key={contestant.id}
                        contestant={contestant}
                        minTime={minTime}
                        onUpdate={onUpdate}
                        msToPixels={msToPixels}
                        pixelsToMs={pixelsToMs}
                        formatTime={formatTime}
                    />
                ))}
            </div>
        </div>
    );
};

const Timeline: React.FC<TimelineProps> = ({ navigationTask, onUpdate }) => {
    if (!navigationTask || !navigationTask.contestant_set || navigationTask.contestant_set.length === 0) {
        return <div className="text-center p-4">No contestants scheduled yet.</div>;
    }

    const contestants = useMemo(() => {
        return [...navigationTask.contestant_set].sort((a, b) => 
            new Date(a.takeoff_time).getTime() - new Date(b.takeoff_time).getTime()
        );
    }, [navigationTask.contestant_set]);

    // Group by aircraft
    const contestantsByAircraft = useMemo(() => {
        const groups: Record<string, any[]> = {};
        contestants.forEach(c => {
            const reg = c.team.aeroplane.registration || "Unknown";
            if (!groups[reg]) groups[reg] = [];
            groups[reg].push(c);
        });
        // Sort groups by registration name for consistency
        return Object.keys(groups).sort().reduce((acc, key) => {
            acc[key] = groups[key];
            return acc;
        }, {} as Record<string, any[]>);
    }, [contestants]);

    const minTime = useMemo(() => {
        const times = contestants.flatMap(c => {
            if (c.adaptive_start) {
                return [new Date(c.tracker_start_time).getTime()];
            } else {
                return [new Date(c.takeoff_time).getTime()];
            }
        });
        if (times.length === 0) return Date.now();
        return Math.min(...times) - 30 * 60000;
    }, [contestants]);

    const msToPixels = (ms: number) => (ms / 60000) * PIXELS_PER_MINUTE;
    const pixelsToMs = (px: number) => (px / PIXELS_PER_MINUTE) * 60000;
    const formatTime = (date: string | number) => new Date(date).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

    const aircraftRegistrations = Object.keys(contestantsByAircraft);

    return (
        <div className="overflow-x-auto w-full border border-base-300 rounded-lg bg-base-100">
            <div style={{ minWidth: '100%', position: 'relative', height: (aircraftRegistrations.length * ROW_HEIGHT) + HEADER_HEIGHT + 20 }}>
                
                {/* Time Axis */}
                <div className="flex border-b border-base-300 bg-base-200 sticky top-0 z-40" style={{ height: HEADER_HEIGHT }}>
                    <div className="w-40 border-r border-base-300 flex items-center px-2 text-xs font-bold text-base-content/50 bg-base-200 z-50">
                        Aircraft
                    </div>
                    <div className="flex-1 flex items-center px-2 text-xs text-base-content/50">
                        Time (Scale: {PIXELS_PER_MINUTE}px/min)
                    </div>
                </div>

                {aircraftRegistrations.map((reg) => (
                    <AircraftRow
                        key={reg}
                        registration={reg}
                        contestants={contestantsByAircraft[reg]}
                        minTime={minTime}
                        onUpdate={onUpdate}
                        msToPixels={msToPixels}
                        pixelsToMs={pixelsToMs}
                        formatTime={formatTime}
                    />
                ))}
            </div>
        </div>
    );
};


export default Timeline;
