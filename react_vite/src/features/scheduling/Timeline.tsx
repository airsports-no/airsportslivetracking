import React, { useEffect, useRef, useMemo } from 'react';
import { Timeline as VisTimeline, TimelineOptions, DataItem, DataGroup } from 'vis-timeline/standalone';
import { DataSet } from 'vis-data';
import 'vis-timeline/styles/vis-timeline-graph2d.css';
import { v4 as uuidv4 } from 'uuid';

interface TimelineProps {
    navigationTask: any;
    firstTakeoffTime: string;
    onUpdate: (contestantId: number, data: any) => void;
    onToggleLock?: (contestantId: number, currentLockState: boolean) => void;
}

const Timeline: React.FC<TimelineProps> = ({ navigationTask, firstTakeoffTime, onUpdate, onToggleLock }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const timelineRef = useRef<VisTimeline | null>(null);
    const itemsRef = useRef<DataSet<DataItem> | null>(null); // DataSet
    const groupsRef = useRef<DataSet<DataGroup> | null>(null); // DataSet

    if (!navigationTask || !navigationTask.contestant_set || navigationTask.contestant_set.length === 0) {
        return <div className="text-center p-4">No contestants scheduled yet.</div>;
    }

    const contestants = useMemo(() => {
        return [...navigationTask.contestant_set].sort((a, b) => 
            new Date(a.takeoff_time).getTime() - new Date(b.takeoff_time).getTime()
        );
    }, [navigationTask.contestant_set]);

    // Group by aircraft
    const aircraftGroups = useMemo(() => {
        const groupsMap = new Map<string, { id: string, content: string, style: string, minTime: number }>();

        contestants.forEach(c => {
            const reg = c.team.aeroplane.registration || "Unknown";
            
            const isAdaptive = c.adaptive_start;
            const trackerStart = new Date(c.tracker_start_time).getTime();
            const takeoff = new Date(c.takeoff_time).getTime();
            const startTime = isAdaptive ? trackerStart : takeoff;

            if (!groupsMap.has(reg)) {
                groupsMap.set(reg, {
                    id: reg,
                    content: reg,
                    style: "font-weight: bold;",
                    minTime: startTime
                });
            } else {
                const group = groupsMap.get(reg)!;
                if (startTime < group.minTime) {
                    group.minTime = startTime;
                }
            }
        });
        
        return Array.from(groupsMap.values()).sort((a, b) => a.minTime - b.minTime);
    }, [contestants]);

    const timelineItems = useMemo(() => {
        const formatTimeLocal = (date: string | number) => new Date(date).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

        return contestants.map(contestant => {
            const isAdaptive = contestant.adaptive_start;
            const trackerStart = new Date(contestant.tracker_start_time).getTime();
            const takeoff = new Date(contestant.takeoff_time).getTime();
            const finish = new Date(contestant.finished_by_time).getTime();
            const landing = contestant.landing_time_after_final_gate 
                ? new Date(contestant.landing_time_after_final_gate).getTime() 
                : finish;

            const blockStartTime = isAdaptive ? trackerStart : takeoff;
            const blockEndTime = isAdaptive ? finish : landing;
            const isCalculatorLocked = contestant.contestanttrack?.calculator_started;
            const isScheduleLocked = contestant.schedule_locked;
            const isLocked = isCalculatorLocked || isScheduleLocked;

            const lockIcon = isScheduleLocked ? '🔒 ' : '';
            const content = `${lockIcon}<b>#${contestant.contestant_number}</b> ${contestant.team.crew.member1.last_name}`;

            const takeoffText = isAdaptive ? 'Adaptive' : formatTimeLocal(takeoff);

            return {
                id: contestant.id,
                group: contestant.team.aeroplane.registration || "Unknown",
                start: blockStartTime,
                end: blockEndTime,
                content: content,
                editable: !isLocked,
                className: isLocked ? 'vis-item-locked' : 'vis-item-normal',
                title: `#${contestant.contestant_number} ${contestant.team.crew.member1.first_name} ${contestant.team.crew.member1.last_name} (${contestant.team.aeroplane.registration})\nTake-off: ${takeoffText}`,
                // Custom data to help with updates
                data: {
                    trackerStart,
                    takeoff,
                    finish,
                    landing,
                    isAdaptive,
                    scheduleLocked: isScheduleLocked
                }
            };
        });
    }, [contestants]);

    useEffect(() => {
        if (!containerRef.current) return;

        // Initialize DataSets
        const items = new DataSet(timelineItems);
        const groups = new DataSet(aircraftGroups);

        itemsRef.current = items;
        groupsRef.current = groups;

        const options: TimelineOptions = {
            min: navigationTask?.start_time ? new Date(navigationTask.start_time).getTime() : undefined,
            moveable: false,
            groupHeightMode: 'fixed',
            stack: false,
            editable: {
                add: false,
                remove: false,
                updateGroup: false,
                updateTime: true,
                overrideItems: false
            },
            margin: {
                item: {
                    horizontal: 0
                }
            },
            orientation: 'top',
            selectable: true,
            multiselect: false,
            snap: null, // Fluid movement
            onMove: (item: any, callback: (item: any) => void) => {
                // Find the *original* item from our prop-derived list, not the mutated 'item' passed by vis
                const oldItem = timelineItems.find(i => i.id === item.id);
                if (!oldItem) {
                    callback(null);
                    return;
                }

                const newStart = new Date(item.start).getTime();
                const oldStart = oldItem.start;
                const delta = newStart - oldStart;

                if (Math.abs(delta) < 1000) { 
                    callback(item);
                    return;
                }

                // Access custom data from the old item
                const { trackerStart, takeoff, finish } = oldItem.data;

                const newTrackerStart = new Date(trackerStart + delta);
                const newTakeoff = new Date(takeoff + delta);
                const newFinish = new Date(finish + delta);

                onUpdate(item.id, {
                    tracker_start_time: newTrackerStart.toISOString(),
                    takeoff_time: newTakeoff.toISOString(),
                    finished_by_time: newFinish.toISOString()
                });

                callback(item); // Optimistically update UI
            }
        };

        const timeline = new VisTimeline(containerRef.current, items, groups, options);
        timelineRef.current = timeline;

        timeline.on('doubleClick', (properties) => {
            if (properties.item && onToggleLock) {
                const item = itemsRef.current?.get(properties.item);
                if (item) {
                    const originalItem = timelineItems.find(i => i.id === item.id);
                    if (originalItem) {
                        onToggleLock(Number(item.id), originalItem.data.scheduleLocked);
                    }
                }
            }
        });

        // Fit once on init
        if (timelineItems.length > 0) {
            timeline.fit();
        }

        // Cleanup
        return () => {
            timeline.destroy();
        };
    }, []); // Run once on mount

    // Effect to update data when props change
    useEffect(() => {
        if (!timelineRef.current || !itemsRef.current || !groupsRef.current) return;

        const items = itemsRef.current;
        const groups = groupsRef.current;

        // Update groups
        groups.update(aircraftGroups);

        // Update items
        // Note: items.update() merges data. If an item is being dragged, updating it might conflict.
        // But since we control the 'start'/'end' via props which come from the backend response 
        // to our update, this loop ensures eventual consistency.
        items.update(timelineItems);
        
    }, [timelineItems, aircraftGroups]);

    // Update timeline window when first takeoff time changes
    useEffect(() => {
        if (timelineRef.current && firstTakeoffTime) {
            const start = new Date(firstTakeoffTime).getTime();
            const currentWindow = timelineRef.current.getWindow();
            const duration = currentWindow.end.getTime() - currentWindow.start.getTime();
            
            // If the start time shifted, we might want to shift the window too
            if (Math.abs(start - currentWindow.start.getTime()) > 1000) {
                timelineRef.current.setWindow(start, start + duration);
            }
        }
    }, [firstTakeoffTime]);

    return (
        <div className="w-full">
            <style>{`
                .vis-item-locked {
                    background-color: #9ca3af;
                    border-color: #6b7280;
                    color: white;
                    cursor: not-allowed;
                }
                .vis-item-normal {
                    background-color: #3b82f6; /* primary */
                    border-color: #2563eb;
                    color: white;
                }
                .vis-item .vis-item-content {
                    padding: 2px 5px;
                }
                .vis-item.vis-selected {
                    background-color: #2563eb;
                    border-color: #1d4ed8;
                    color: white;
                    z-index: 2;
                }
            `}</style>
            <div ref={containerRef} className="w-full border border-base-300 rounded-lg bg-base-100 h-[600px]" />
        </div>
    );
};

export default Timeline;