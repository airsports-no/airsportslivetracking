import React, { useEffect, useRef, useMemo } from 'react';
import { Timeline as VisTimeline, TimelineOptions, DataItem, DataGroup } from 'vis-timeline/standalone';
import { DataSet } from 'vis-data';
import 'vis-timeline/styles/vis-timeline-graph2d.css';
import { v4 as uuidv4 } from 'uuid';

interface TimelineProps {
    navigationTask: any;
    firstTakeoffTime: Date;
    onUpdate: (contestantId: number, data: any) => void;
    onToggleLock?: (contestantId: number, currentLockState: boolean) => void;
    onDelete?: (contestantId: number) => void;
}

const Timeline: React.FC<TimelineProps> = ({ navigationTask, firstTakeoffTime, onUpdate, onToggleLock, onDelete }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const timelineRef = useRef<VisTimeline | null>(null);
    const itemsRef = useRef<DataSet<DataItem> | null>(null); // DataSet
    const groupsRef = useRef<DataSet<DataGroup> | null>(null); // DataSet

    const contestantSet = navigationTask?.contestant_set;
    const hasContestants = Boolean(contestantSet?.length);

    // Hooks must run unconditionally on every render (Rules of Hooks) - an early
    // return here based on a prop that changes over the component's lifetime
    // (contestant_set going from empty to populated, or back) changes how many
    // hooks run between renders and crashes the whole subtree ("Rendered more
    // hooks than during the previous render"). The empty-state message is
    // rendered as an overlay in the JSX below instead, so the container div -
    // and every hook - stays mounted regardless of contestant count.
    const contestants = useMemo(() => {
        if (!contestantSet) return [];
        return [...contestantSet].sort((a, b) =>
            new Date(a.takeoff_time).getTime() - new Date(b.takeoff_time).getTime()
        );
    }, [contestantSet]);

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

    // A contestant "overtakes" another when it takes off later but finishes earlier - i.e. the
    // finish-time order (sorted by takeoff time, which `contestants` already is) has an
    // inversion. Informational only: this never affects `editable`, dragging is never blocked.
    // For each contestant, flag it if either direction of inversion involves it:
    // - some contestant departing after it finishes before it (it gets overtaken), or
    // - it finishes before some contestant that departed before it (it does the overtaking).
    // Both directions reduce to one O(n) pass (after the existing takeoff-time sort) using a
    // suffix-min and a prefix-max of finish times.
    const overtakeContestantIds = useMemo(() => {
        const n = contestants.length;
        const flagged = new Set<number>();
        if (n < 2) return flagged;

        const finishTimes = contestants.map(c => new Date(c.finished_by_time).getTime());

        const suffixMinAfter = new Array<number>(n).fill(Infinity);
        for (let i = n - 2; i >= 0; i--) {
            suffixMinAfter[i] = Math.min(finishTimes[i + 1], suffixMinAfter[i + 1]);
        }
        const prefixMaxBefore = new Array<number>(n).fill(-Infinity);
        for (let i = 1; i < n; i++) {
            prefixMaxBefore[i] = Math.max(finishTimes[i - 1], prefixMaxBefore[i - 1]);
        }

        for (let i = 0; i < n; i++) {
            if (finishTimes[i] > suffixMinAfter[i] || finishTimes[i] < prefixMaxBefore[i]) {
                flagged.add(contestants[i].id);
            }
        }
        return flagged;
    }, [contestants]);

    const timelineItems = useMemo(() => {
        const formatTimeLocal = (date: string | number) => new Date(date).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

        return contestants.map(contestant => {
            const isAdaptive = contestant.adaptive_start;
            const trackerStart = new Date(contestant.tracker_start_time).getTime();
            const takeoff = new Date(contestant.takeoff_time).getTime();
            const finish = new Date(contestant.finished_by_time).getTime();
            const landing = contestant.landing_time 
                ? new Date(contestant.landing_time).getTime() 
                : finish;

            const blockStartTime = isAdaptive ? trackerStart : takeoff;
            const blockEndTime = isAdaptive ? finish : landing;
            const isCalculatorLocked = contestant.contestanttrack?.calculator_started;
            const isScheduleLocked = contestant.schedule_locked;
            const isLocked = isCalculatorLocked || isScheduleLocked;

            let lockIcon = '';
            let lockTooltip = '';

            if (isCalculatorLocked) {
                lockIcon = '📡 ';
                lockTooltip = '\nTracking started.\nCannot move, but can delete.';
            } else if (isScheduleLocked) {
                lockIcon = '🔒 ';
                lockTooltip = '\nSchedule locked.';
            }

            const hasOverlaps = contestant.overlap_warnings && contestant.overlap_warnings.length > 0;
            let warningIcon = '';
            let warningTooltip = '';

            if (hasOverlaps) {
                // Not an inline <svg> string: vis-timeline runs item content through an XSS
                // sanitizer (the bundled `xss` package) whose default tag allowlist doesn't
                // include svg/path/line, so the raw markup leaked through as literal visible
                // text instead of being rendered - matches the lockIcon emoji below, which
                // renders fine for the same reason (plain text needs no allowlisted tags).
                warningIcon = '⚠️ ';
                warningTooltip = '\nWarning: Overlapping contestants\ndetected on this tracker.';
            }

            const isOvertaking = overtakeContestantIds.has(contestant.id);
            let overtakeIcon = '';
            let overtakeTooltip = '';

            if (isOvertaking) {
                // See the warningIcon comment above - same vis-timeline XSS-sanitizer issue.
                overtakeIcon = '🔀 ';
                overtakeTooltip =
                    "\nNote: this contestant's finishing order crosses\nanother contestant's relative to takeoff order\n(an overtake). Not blocked, just flagged.";
            }

            const content = `${warningIcon}${overtakeIcon}${lockIcon}<b>#${contestant.contestant_number}</b> ${contestant.team.crew.member1.last_name}`;

            const takeoffText = isAdaptive ? 'Adaptive' : formatTimeLocal(takeoff);
            
            // Editable logic:
            // Calculator locked: No moving (updateTime: false), but allow remove.
            // Schedule locked: Fully locked (editable: false) - consistent with "Lock".
            // Unlocked: Fully editable.
            
            let itemEditable: boolean | { remove?: boolean; updateGroup?: boolean; updateTime?: boolean } = true;
            
            if (isCalculatorLocked) {
                itemEditable = { updateTime: false, remove: true };
            } else if (isScheduleLocked) {
                itemEditable = false;
            }

            return {
                id: contestant.id,
                group: contestant.team.aeroplane.registration || "Unknown",
                start: blockStartTime,
                end: blockEndTime,
                content: content,
                editable: itemEditable,
                className: [isLocked ? 'vis-item-locked' : 'vis-item-normal', isOvertaking ? 'vis-item-overtake' : '']
                    .filter(Boolean)
                    .join(' '),
                title: `#${contestant.contestant_number} ${contestant.team.crew.member1.first_name} ${contestant.team.crew.member1.last_name}\n(${contestant.team.aeroplane.registration})\nTake-off: ${takeoffText}${lockTooltip}${warningTooltip}${overtakeTooltip}`,
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
    }, [contestants, overtakeContestantIds]);

    const timelineItemsRef = useRef(timelineItems);
    const contestantsRef = useRef(contestants);

    useEffect(() => {
        timelineItemsRef.current = timelineItems;
    }, [timelineItems]);

    useEffect(() => {
        contestantsRef.current = contestants;
    }, [contestants]);

    useEffect(() => {
        if (!containerRef.current) return;

        // Initialize DataSets
        const items = new DataSet(timelineItems);
        const groups = new DataSet(aircraftGroups);

        itemsRef.current = items;
        groupsRef.current = groups;

        // Panning/zooming is bounded to the competition's own start/finish time plus a small
        // fixed padding either side - enough slack to see a slightly early/late contestant,
        // not enough to wander off arbitrarily far from the actual event.
        const PAN_ZOOM_PADDING_MS = 60 * 60 * 1000;
        const panZoomMin = navigationTask?.start_time
            ? new Date(new Date(navigationTask.start_time).getTime() - PAN_ZOOM_PADDING_MS)
            : undefined;
        const panZoomMax = navigationTask?.finish_time
            ? new Date(new Date(navigationTask.finish_time).getTime() + PAN_ZOOM_PADDING_MS)
            : undefined;

        const options: TimelineOptions = {
            moveable: true,
            zoomable: true,
            min: panZoomMin,
            max: panZoomMax,
            groupHeightMode: 'fixed',
            stack: false,
            showCurrentTime: true,
            editable: {
                add: false,
                remove: true, // Enable removal
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
                const oldItem = timelineItemsRef.current.find(i => i.id === item.id);
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
            },
            onRemove: (item: any, callback: (item: any) => void) => {
                if (onDelete) {
                    onDelete(Number(item.id));
                    callback(item);
                } else {
                    callback(null); // Cancel deletion if no handler
                }
            }
        };

        const timeline = new VisTimeline(containerRef.current, items, groups, options);
        timelineRef.current = timeline;

        timeline.on('doubleClick', (properties) => {
            if (properties.item && onToggleLock) {
                const item = itemsRef.current?.get(properties.item);
                if (item) {
                    const originalItem = timelineItemsRef.current.find(i => i.id === item.id);
                    if (originalItem) {
                        onToggleLock(Number(item.id), originalItem.data.scheduleLocked);
                    }
                }
            }
        });

        // // Fit once on init
        // if (timelineItems.length > 0) {
        //     timeline.fit();
        // }

        // Cleanup
        return () => {
            timeline.destroy();
        };
    }, []); // Run once on mount

    // Effect to update data and window when props change
    useEffect(() => {
        if (!timelineRef.current || !itemsRef.current || !groupsRef.current) return;

        const items = itemsRef.current;
        const groups = groupsRef.current;

        // Update groups
        const existingGroupIds = groups.getIds();
        const newGroupIds = aircraftGroups.map(g => g.id);
        const groupsToRemove = existingGroupIds.filter(id => !newGroupIds.includes(String(id)));
        groups.remove(groupsToRemove);
        groups.update(aircraftGroups);

        // Update items
        const existingItemIds = items.getIds();
        const newItemIds = timelineItems.map(i => i.id);
        const itemsToRemove = existingItemIds.filter(id => !newItemIds.includes(id));
        items.remove(itemsToRemove);
        items.update(timelineItems);
    }, [timelineItems, aircraftGroups]);

    // Frames the visible window around "Reschedule From" - deliberately separate from the data
    // sync effect above and keyed only on firstTakeoffTime, not on contestants/timelineItems:
    // dragging a single contestant (which round-trips through onUpdate and updates the
    // contestants prop) must not reset whatever zoom/pan the organizer currently has.
    useEffect(() => {
        if (!timelineRef.current || !firstTakeoffTime) return;

        let maxFinishTime: Date;
        const currentContestants = contestantsRef.current;
        if (currentContestants.length > 0) {
            const times = currentContestants.map(c => new Date(c.finished_by_time).getTime());
            maxFinishTime = new Date(Math.max(...times) + 2 * 60 * 60 * 1000);
        } else {
            // Default view if no contestants (e.g. 4 hours)
            maxFinishTime = new Date(firstTakeoffTime.getTime() + 4 * 60 * 60 * 1000);
        }

        timelineRef.current.setWindow(firstTakeoffTime, maxFinishTime, { animation: false });
    }, [firstTakeoffTime]);

    return (
        <div className="w-full h-full relative">
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
                .vis-item-overtake {
                    /* Informational only - layers on top of the locked/normal background,
                       never changes editability. */
                    outline: 2px dashed #a855f7;
                    outline-offset: -2px;
                }
                .vis-item.vis-selected {
                    background-color: #2563eb;
                    border-color: #1d4ed8;
                    color: white;
                    z-index: 2;
                }
            `}</style>
            {!hasContestants && (
                <div className="absolute inset-0 z-10 flex items-center justify-center text-center p-4 bg-base-100">
                    No contestants scheduled yet.
                </div>
            )}
            <div ref={containerRef} className="w-full border border-base-300 rounded-lg bg-base-100 h-full" />
        </div>
    );
};

export default Timeline;