import { useState, useEffect, useRef, useCallback } from 'react';
import { fetchNavigationTask, fetchContestantPaginatedTrack, fetchContestantScoreData, makeWebSocket, fetchContestantSlice } from '../api';
import type { Contestant, NavigationTask, TrackPosition, ScoreAnnotation, ScoreLogEntry, DangerData, GateArrowData, Waypoint } from '../types';
import { evaluateIncomingMessage, mergeAcceptedVersions, takeHigherVersion, VersionState } from './wsMessageOrdering';

export function useCompetitionData(contestIdNum: number, navigationTaskIdNum: number, mode: 'realtime' | 'playback', showToast: (message: string, type?: 'success' | 'error' | 'info' | 'warning') => void) {
    const [staticNavTaskData, setStaticNavTaskData] = useState<NavigationTask | null>(null);
    const [contestantsById, setContestantsById] = useState<Record<number, Contestant>>({});
    const [positionsByContestant, setPositionsByContestant] = useState<Record<number, TrackPosition[]>>({});
    const [annotationsByContestant, setAnnotationsByContestant] = useState<Record<number, ScoreAnnotation[]>>({});
    const [scoreLogByContestant, setScoreLogByContestant] = useState<Record<number, ScoreLogEntry[]>>({});
    const [gateScoresByContestant, setGateScoresByContestant] = useState<Record<number, any[]>>({});
    const [dangerDataByContestant, setDangerDataByContestant] = useState<Record<number, DangerData>>({});
    const [gateArrowDataByContestant, setGateArrowDataByContestant] = useState<Record<number, GateArrowData>>({});
    const [progress, setProgress] = useState({ loaded: 0, total: 0, message: '' });
    const [shouldConnectWs, setShouldConnectWs] = useState(false); // New state
    const [wsStatus, setWsStatus] = useState<'connected' | 'disconnected'>('disconnected');
    const [error, setError] = useState<{ status?: number; message: string } | null>(null);


    const navTaskRef = useRef(staticNavTaskData);
    useEffect(() => {
        navTaskRef.current = staticNavTaskData;
    }, [staticNavTaskData]);
    
    // New refs for staticNavTaskData and contestantsById to stabilize processWsMessage dependencies
    const staticNavTaskDataRef = useRef(staticNavTaskData);
    useEffect(() => {
        staticNavTaskDataRef.current = staticNavTaskData;
    }, [staticNavTaskData]);

    const contestantsByIdRef = useRef(contestantsById);
    useEffect(() => {
        contestantsByIdRef.current = contestantsById;
    }, [contestantsById]);

    const [isReFetching, setIsReFetching] = useState(false);
    const isReFetchingRef = useRef(isReFetching);
    useEffect(() => {
        isReFetchingRef.current = isReFetching;
    }, [isReFetching]);

    // Refs for state setters
    const setPositionsByContestantRef = useRef(setPositionsByContestant);
    useEffect(() => { setPositionsByContestantRef.current = setPositionsByContestant; }, [setPositionsByContestant]);

    const setAnnotationsByContestantRef = useRef(setAnnotationsByContestant);
    useEffect(() => { setAnnotationsByContestantRef.current = setAnnotationsByContestant; }, [setAnnotationsByContestant]);

    const setScoreLogByContestantRef = useRef(setScoreLogByContestant);
    useEffect(() => { setScoreLogByContestantRef.current = setScoreLogByContestant; }, [setScoreLogByContestant]);

    // Keyed by `${contestantId}:${msg.type}`, not just contestantId: position_data (main
    // thread) and score_log/gate_score/annotations (score_updater_thread, see
    // ContestantProcessor.score_updater_thread) are independent streams sent from different
    // backend threads via time.time_ns() msg_ids that are not guaranteed to arrive in
    // generation order relative to EACH OTHER (only within their own stream). A single
    // contestant-wide counter let a fast-arriving message of one type retroactively mark a
    // still-in-flight, legitimately newer message of another type as "out of order" and drop
    // it - most visible during a recalculation replay, which bursts many messages of both
    // kinds in quick succession, producing the flicker/stuck-wrong-value bug that only a full
    // reload (which re-fetches via REST instead of trusting this ordering heuristic) fixed.
    const latestMsgIdsRef = useRef<Record<string, number>>({});

    // Tracks the latest ACCEPTED track_version/score_version per contestant, updated
    // synchronously the instant a message is processed below. This is deliberately separate
    // from contestantsByIdRef, which only reflects committed React state and is synced by a
    // useEffect that runs after a render commits - one or more renders behind during a
    // recalculation burst (this hook can receive hundreds of position_data/score_log messages
    // back-to-back before React gets a chance to re-render). If the stale-message guard below
    // compared against contestantsByIdRef instead, every message in such a burst would be
    // checked against the SAME pre-burst snapshot, so a genuinely stale message (an old
    // track_version/score_version still in flight from before the recalculation) could slip
    // past the guard even after a newer message for the same contestant was already accepted
    // moments earlier in the same burst - and since updateContestant() merges track_version/
    // score_version unconditionally (it trusts the guard, not re-checking itself), that stale
    // message would then regress the contestant's version fields (and whatever score/track data
    // came with it) right after the correct, newer value had just been applied.
    const latestVersionsRef = useRef<Record<number, VersionState>>({});

    // Seeds/raises latestVersionsRef from authoritative REST data (initial load, or the
    // full re-fetch handleStaleConnection does before replaying buffered ws messages) so the
    // stale-message guard in processWsMessage has a correct baseline immediately, rather than
    // only learning a contestant's version from whatever the next ws message happens to say.
    const seedVersionsFromContestants = useCallback((contestants: Contestant[]) => {
        contestants.forEach((c) => {
            if (!c) return;
            const prev = latestVersionsRef.current[c.id];
            latestVersionsRef.current[c.id] = {
                track_version: takeHigherVersion(prev?.track_version, c.track_version),
                score_version: takeHigherVersion(prev?.score_version, c.score_version),
            };
        });
    }, []);

    const wsBufferRef = useRef<string[]>([]);
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimerRef = useRef<number | null>(null);
    const reconnectAttemptsRef = useRef(0);
    const lastMessageTimeRef = useRef<number>(Date.now());


    const updateContestant = useCallback((id: number, update: Partial<Contestant>) => {
        setContestantsById(prev => {
            const existing = prev[id];
            if (existing) {
                // Perform deep merge for team and its nested objects
                let newTeam = existing.team;
                if (update.team) {
                    const newAeroplane = (update.team.aeroplane && existing.team?.aeroplane)
                        ? { ...existing.team.aeroplane, ...update.team.aeroplane }
                        : (update.team.aeroplane || existing.team?.aeroplane);
                    
                    const newCrew = (update.team.crew && existing.team?.crew)
                        ? { ...existing.team.crew, ...update.team.crew }
                        : (update.team.crew || existing.team?.crew);

                    newTeam = { 
                        ...existing.team, 
                        ...update.team, 
                        aeroplane: newAeroplane,
                        crew: newCrew 
                    };
                }
                
                return { 
                    ...prev, 
                    [id]: { 
                        ...existing, 
                        ...update,
                        team: newTeam
                    } 
                };
            } else if (update.team) {
                return { ...prev, [id]: update as Contestant };
            }
            return prev;
        });
    }, []);

    const processWsMessage = useCallback((data: string) => {
        try {
            const msg = JSON.parse(data) as { type: string; data: string };
            const payload = JSON.parse(msg.data) as any;
            const contestantId = payload.contestant_id || payload.id;
            
            if (!contestantId) return;

            // Handle ordering and versioning. Use latestVersionsRef (synchronous, see its
            // declaration above), not contestantsByIdRef - the latter lags behind by however
            // many messages in this burst haven't triggered a React render yet. See
            // wsMessageOrdering.ts for why this can't just read post-render state.
            const msgId = payload.msg_id;
            const msgTypeKey = `${contestantId}:${msg.type}`;
            const versions = latestVersionsRef.current[contestantId];
            const latestMsgId = latestMsgIdsRef.current[msgTypeKey] || 0;

            const evaluation = evaluateIncomingMessage(versions, latestMsgId, {
                msgId,
                trackVersion: payload.track_version,
                scoreVersion: payload.score_version,
            });
            if (!evaluation.accept) {
                // console.debug(`WS: Rejecting out-of-order/stale message for ${contestantId}`);
                return;
            }
            latestMsgIdsRef.current[msgTypeKey] = evaluation.nextLatestMsgId;
            const mergedVersions = mergeAcceptedVersions(versions, payload.track_version, payload.score_version);
            if (mergedVersions) {
                latestVersionsRef.current[contestantId] = mergedVersions;
            }

            if (msg.type === 'contestant') {
                console.debug('WS: received contestant metadata', payload);
                updateContestant(contestantId, payload);
                return;
            }

            if (msg.type === 'contestant_delete') {
                delete latestVersionsRef.current[contestantId];
                setContestantsById(prev => {
                    const newContestants = { ...prev };
                    delete newContestants[contestantId];
                    return newContestants;
                });
                // Clear all associated data
                setPositionsByContestant(prev => { const next = { ...prev }; delete next[contestantId]; return next; });
                setAnnotationsByContestant(prev => { const next = { ...prev }; delete next[contestantId]; return next; });
                setScoreLogByContestant(prev => { const next = { ...prev }; delete next[contestantId]; return next; });
                setGateScoresByContestant(prev => { const next = { ...prev }; delete next[contestantId]; return next; });
                setDangerDataByContestant(prev => { const next = { ...prev }; delete next[contestantId]; return next; });
                setGateArrowDataByContestant(prev => { const next = { ...prev }; delete next[contestantId]; return next; });
                return;
            }

            if (msg.type === 'danger_level') {
                setDangerDataByContestant(prev => ({ ...prev, [contestantId]: payload.danger_level }));
                updateContestant(contestantId, {
                    track_version: payload.track_version,
                    score_version: payload.score_version
                });
                return;
            }
            if (msg.type === 'playing_cards') {
                const playingCardsPayload = JSON.parse(msg.data);
                const contestantId = playingCardsPayload.contestant_id;
                const playing_cards = playingCardsPayload.playing_cards;

                updateContestant(contestantId, { 
                    playing_cards,
                    track_version: payload.track_version,
                    score_version: payload.score_version
                });
                return;
            }
            if (msg.type === 'crossing_time') {
                const crossingPayload = JSON.parse(msg.data) as {
                    contestant_id: number;
                    track_version: number;
                    score_version: number;
                    gate_distance_and_estimate: {
                        seconds_to_planned_crossing: number;
                        estimated_crossing_offset: number;
                        estimated_score: number;
                        waypoint_name: string;
                        final: boolean;
                        missed: boolean;
                    };
                };
                const crossingContestantId = crossingPayload.contestant_id;
                const gateData = crossingPayload.gate_distance_and_estimate;

                // Update gateArrowDataByContestant with the gate_distance_and_estimate from the crossing_time message
                setGateArrowDataByContestant(prev => ({ ...prev, [crossingContestantId]: gateData }));
                updateContestant(crossingContestantId, {
                    track_version: payload.track_version,
                    score_version: payload.score_version
                });
                return;
            }

            if (payload.positions && payload.positions.length > 0) {
                setPositionsByContestantRef.current(prev => { // Use ref here
                    const newPositions = [...(prev[contestantId] || []), ...payload.positions];
                    newPositions.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
                    return { ...prev, [contestantId]: newPositions };
                });
                
                // Update contestant metadata with progress and last seen time from position data
                const update: any = { 
                    last_position_received_at: Date.now(),
                    track_version: payload.track_version,
                    score_version: payload.score_version
                };
                if (payload.progress !== undefined) {
                    update.progress = payload.progress;
                }
                updateContestant(contestantId, update);
            }
            if (msg.type === "annotations" && payload.annotations) {
                setAnnotationsByContestantRef.current(prev => {
                    const newAnnotations = [...payload.annotations];
                    newAnnotations.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
                    return { ...prev, [contestantId]: newAnnotations };
                });
                updateContestant(contestantId, {
                    track_version: payload.track_version,
                    score_version: payload.score_version
                });
            }
            if (msg.type === "score_log" && payload.score_log_entries) {
                setScoreLogByContestantRef.current(prev => {
                    const existingScoreLogs = prev[contestantId] ?? [];
                    const newEntries = payload.score_log_entries; // The score_log WebSocket message contains the FULL history for the contestant.

                    // Identify start and finish gates from navigation task data
                    const startGateName = staticNavTaskDataRef.current?.route?.waypoints.find((wp: Waypoint) => wp.type === 'sp')?.name;
                    const finishGateName = staticNavTaskDataRef.current?.route?.waypoints.find((wp: Waypoint) => wp.type === 'fp')?.name;

                    if (staticNavTaskDataRef.current && (startGateName || finishGateName)) {
                        const previousGateNames = new Set(existingScoreLogs.map(log => log.gate));

                        newEntries.forEach((newLogEntry: ScoreLogEntry) => {
                            if (!previousGateNames.has(newLogEntry.gate) && newLogEntry.planned!==null) {
                                // This is a new score log entry
                                if (newLogEntry.gate === startGateName || newLogEntry.gate === finishGateName) {
                                    const contestant = contestantsByIdRef.current[contestantId];
                                    if (contestant && contestant.team?.crew?.member1) {
                                        const gateType = newLogEntry.gate === startGateName ? 'STARTING POINT' : 'FINISH POINT';
                                        const scoreMessage = newLogEntry.points !== undefined ? `Score: ${newLogEntry.points.toFixed(1)}` : '';
                                        showToast(
                                            `#${contestant.contestant_number} ${contestant.team.crew.member1.first_name} ${contestant.team.crew.member1.last_name} crossed the ${gateType}! ${scoreMessage}`,
                                            'success'
                                        );
                                    }
                                }
                            }
                        });
                    }

                    // Replace the existing log rather than appending.
                    const allScoreLogs = [...newEntries];
                    allScoreLogs.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
                    return { ...prev, [contestantId]: allScoreLogs };
                });
                updateContestant(contestantId, {
                    track_version: payload.track_version,
                    score_version: payload.score_version
                });
            }
            if (msg.type === "gate_score" && payload.gate_scores) {
                setGateScoresByContestant(prev => ({ ...prev, [contestantId]: payload.gate_scores }));
                updateContestant(contestantId, {
                    track_version: payload.track_version,
                    score_version: payload.score_version
                });
            }
            if (payload.contestant_track) {
                updateContestant(contestantId, { 
                    contestanttrack: payload.contestant_track,
                    track_version: payload.track_version,
                    score_version: payload.score_version
                });
            }
        } catch (e) {
            console.error('WS parse error', e);
        }
    }, [showToast, updateContestant]);


    const fetchAllContestantData = useCallback(async (contestantsToFetch: Contestant[], onProgress: (p: { loaded: number, total: number, message?: string }) => void) => {
        const now = new Date();
        const chunkSize = 15;

        onProgress({ loaded: 0, total: 100, message: 'Planning track stitching...' });

        const getBestChunkSize = (minute: number, endMinute: number, now: Date) => {
            const remaining = endMinute - minute + 1;
            // Tiered chunking for CDN efficiency and reduced request count
            for (const size of [60, 15, 5]) {
                if (minute % size === 0 && remaining >= size) {
                    const chunkEndTime = (minute + size) * 60000;
                    // Only use chunks for data that is definitively in the past (150s grace period)
                    if (chunkEndTime < now.getTime() - 150000) {
                        return size;
                    }
                }
            }
            return 1;
        };

        // 1. Calculate total expected requests to provide a granular progress bar
        let totalRequests = 0;
        const contestantRequestPlans = contestantsToFetch.map(c => {
            const scheduledStartTime = new Date(c.tracker_start_time);
            const firstPosTime = c.first_position_time ? new Date(c.first_position_time) : null;

            // If we have actual positions, prioritize starting there. 
            // Only fall back to scheduled time if no positions exist.
            let startTime = firstPosTime || scheduledStartTime;

            // If the pilot started early, include that.
            if (firstPosTime && scheduledStartTime < firstPosTime) {
                // If it's just a few minutes early, include the scheduled start.
                // If it's hours earlier, we probably only care about the actual flight.
                if (firstPosTime.getTime() - scheduledStartTime.getTime() < 3600000) {
                    startTime = scheduledStartTime;
                }
            }

            const scheduledFinishTime = new Date(c.finished_by_time);
            const lastPosTime = c.last_position_time ? new Date(c.last_position_time) : null;

            // End at the later of scheduled finish or last known position
            let absoluteEndTime = (lastPosTime && lastPosTime > scheduledFinishTime) ? lastPosTime : scheduledFinishTime;

            // If we are currently in the scheduled window or data is recent, include "now"
            const endTime = absoluteEndTime < now ? absoluteEndTime : now;

            // Safety: Never request more than 24 hours of data.
            // If the range is larger, prefer the end of the window (the most recent data).
            let finalStartTime = startTime;
            if (endTime.getTime() - finalStartTime.getTime() > 24 * 3600000) {
                finalStartTime = new Date(endTime.getTime() - 24 * 3600000);
            }

            const startMinute = Math.floor(finalStartTime.getTime() / 60000);
            const endMinute = Math.ceil(endTime.getTime() / 60000);

            let requests = 1; // For score data
            let currentMinute = startMinute;
            while (currentMinute <= endMinute) {
                const size = getBestChunkSize(currentMinute, endMinute, now);
                currentMinute += size;
                requests++;
            }
            totalRequests += requests;
            return { startMinute, endMinute };
        });

        onProgress({ loaded: 0, total: 100, message: 'Initializing telemetry download...' });
        let loadedRequests = 0;

        const updateProgress = (msg?: string) => {
            loadedRequests++;
            // Use 99% as the max during individual request phase to keep bar visible during data processing
            const percentage = Math.min(99, Math.round((loadedRequests / totalRequests) * 100));
            onProgress({ 
                loaded: percentage, 
                total: 100, 
                message: msg || `Downloading data: ${percentage}%` 
            });
        };

        const contestantPromises = contestantsToFetch.map(async (c, idx) => {
            try {
                const { startMinute, endMinute } = contestantRequestPlans[idx];
                
                // Fetch score data first so it's included in the progress and available as soon as possible
                const scoreData = await fetchContestantScoreData(contestIdNum, navigationTaskIdNum, c.id, c.track_version, c.score_version).finally(() => {
                    updateProgress(`Downloading track for ${c.team.crew.member1.first_name}...`);
                });

                const sliceResults: any[][] = [];
                let currentMinute = startMinute;
                while (currentMinute <= endMinute) {
                    const size = getBestChunkSize(currentMinute, endMinute, now);
                    const p = await fetchContestantSlice(c.id, currentMinute, size).finally(() => updateProgress());
                    sliceResults.push(p);
                    currentMinute += size;
                }

                const allPositions: TrackPosition[] = sliceResults.flat();
                return {
                    contestant: { ...c, contestanttrack: scoreData.contestant_track, playing_cards: scoreData.playing_cards },
                    positions: allPositions.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()),
                    annotations: scoreData.annotations.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()),
                    scoreLogs: scoreData.score_log_entries.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()),
                    gateScores: scoreData.gate_scores,
                };
            } catch (e) {
                console.error('Failed to fetch data for contestant', c.id, e);
                return null;
            }
        });

        const allContestantData = await Promise.all(contestantPromises);
        onProgress({ loaded: 100, total: 100, message: 'Processing complete' });
        
        const positionUpdates: Record<number, TrackPosition[]> = {};
        const annotationUpdates: Record<number, ScoreAnnotation[]> = {};
        const scoreLogUpdates: Record<number, ScoreLogEntry[]> = {};
        const gateScoreUpdates: Record<number, any[]> = {};
        const contestantUpdates: Record<number, Contestant> = {};

        for (const data of allContestantData) {
            if (data) {
                positionUpdates[data.contestant.id] = data.positions;
                annotationUpdates[data.contestant.id] = data.annotations;
                scoreLogUpdates[data.contestant.id] = data.scoreLogs;
                gateScoreUpdates[data.contestant.id] = data.gateScores;
                contestantUpdates[data.contestant.id] = data.contestant;
            }
        }
        return { positionUpdates, annotationUpdates, scoreLogUpdates, gateScoreUpdates, contestantUpdates };
    }, [contestIdNum, navigationTaskIdNum]);


    const handleStaleConnection = useCallback(async () => {
        if (isReFetchingRef.current || !navTaskRef.current) {
            return;
        }

        setIsReFetching(true);
        wsBufferRef.current = [];

        const contestantsToRefetch = Object.values(contestantsByIdRef.current).filter(c => c && !c.contestanttrack?.calculator_finished);

        if (contestantsToRefetch.length > 0) {
            const { positionUpdates, annotationUpdates, scoreLogUpdates, gateScoreUpdates, contestantUpdates } = await fetchAllContestantData(contestantsToRefetch, setProgress);

            // Seed BEFORE replaying the buffer below, so any buffered message that's actually
            // stale relative to what we just fetched gets correctly rejected instead of being
            // judged against a baseline that doesn't know about this fetch yet.
            seedVersionsFromContestants(Object.values(contestantUpdates));

            setPositionsByContestant(prev => ({...prev, ...positionUpdates}));
            setAnnotationsByContestant(prev => ({...prev, ...annotationUpdates}));
            setScoreLogByContestant(prev => ({...prev, ...scoreLogUpdates}));
            setGateScoresByContestant(prev => ({...prev, ...gateScoreUpdates}));
            setContestantsById(prev => ({ ...prev, ...contestantUpdates }));
        }


        wsBufferRef.current.forEach(msg => processWsMessage(msg));
        wsBufferRef.current = [];

        setIsReFetching(false);
    }, [fetchAllContestantData, processWsMessage, seedVersionsFromContestants]);

    // Effect to handle mode change to 'realtime'
    useEffect(() => {
        if (mode === 'realtime') {
            handleStaleConnection();
        }
    }, [mode, handleStaleConnection]);

    // Fetch navigation task and initial data
    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const task = await fetchNavigationTask(contestIdNum, navigationTaskIdNum);
                if (!cancelled) {
                    // Set stable staticNavTaskData properties, exclude dynamic contestant_set
                    setStaticNavTaskData(task);

                    // Populate new contestantsById state
                    const initialContestantsMap = task.contestant_set.reduce((acc, c) => {
                        acc[c.id] = c;
                        return acc;
                    }, {} as Record<number, Contestant>);
                    setContestantsById(initialContestantsMap);
                    seedVersionsFromContestants(task.contestant_set);
                    setShouldConnectWs(true);

                    const { positionUpdates, annotationUpdates, scoreLogUpdates, gateScoreUpdates, contestantUpdates } = await fetchAllContestantData(task.contestant_set, setProgress);
                    if (!cancelled) {
                        seedVersionsFromContestants(Object.values(contestantUpdates));
                        setPositionsByContestant(positionUpdates);
                        setAnnotationsByContestant(annotationUpdates);
                        setScoreLogByContestant(scoreLogUpdates);
                        setGateScoresByContestant(gateScoreUpdates);
                        setContestantsById(prev => ({ ...prev, ...contestantUpdates }));
                    }
                }
            } catch (e: any) {
                if (!cancelled) {
                    console.error("useCompetitionData initial fetch error:", e);
                    setError({ status: e.status, message: e.message });
                }
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [contestIdNum, navigationTaskIdNum, fetchAllContestantData, seedVersionsFromContestants]);

    // WebSocket and Stale Connection Detector
    useEffect(() => {
        if (mode !== 'realtime' || !shouldConnectWs) {
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
            return;
        }

        const handleOnline = () => {
            handleStaleConnection();
        };

        const handleVisibilityChange = () => {
            if (document.visibilityState === 'visible') {
                handleStaleConnection();
            }
        };

        window.addEventListener('online', handleOnline);
        document.addEventListener('visibilitychange', handleVisibilityChange);

        const connect = () => {
            if (wsRef.current) {
                // Prevent onclose from firing during manual reconnection/cleanup
                wsRef.current.onclose = null;
                wsRef.current.close();
            }

            const ws = makeWebSocket(navigationTaskIdNum);
            wsRef.current = ws;

            let heartbeatTimeout: number | null = null;
            let pongTimeout: number | null = null;

            const heartbeat = () => {
                if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
                    return; // Don't ping if not open
                }

                // Schedule closing if pong is not received
                pongTimeout = window.setTimeout(() => {
                    console.log("WebSocket pong timeout. Closing connection.");
                    wsRef.current?.close(); // This will trigger onclose and reconnection
                }, 5000); // 5 seconds for pong response

                ws.send(JSON.stringify({ type: 'ping' }));
                
                // Determine next ping interval based on activity
                const timeSinceLastMessage = Date.now() - lastMessageTimeRef.current;
                const INACTIVE_THRESHOLD = 5 * 60 * 1000; // 5 minutes
                const NORMAL_PING_INTERVAL = 10000; // 10 seconds
                const INACTIVE_PING_INTERVAL = 60000; // 60 seconds
                const nextPingInterval = timeSinceLastMessage > INACTIVE_THRESHOLD ? INACTIVE_PING_INTERVAL : NORMAL_PING_INTERVAL;

                if (heartbeatTimeout) clearTimeout(heartbeatTimeout);
                heartbeatTimeout = window.setTimeout(heartbeat, nextPingInterval);
            };

            ws.onopen = () => {
                console.log("WebSocket connected");
                setWsStatus('connected');
                reconnectAttemptsRef.current = 0; // Reset on successful connection
                lastMessageTimeRef.current = Date.now();
                heartbeat(); // Start the heartbeat loop
            };

            ws.onmessage = (ev) => {
                lastMessageTimeRef.current = Date.now(); // Update activity timestamp

                try {
                    const msg = JSON.parse(ev.data);
                    if (msg.type === 'pong') {
                        if (pongTimeout) {
                            clearTimeout(pongTimeout);
                            pongTimeout = null;
                        }
                        return; // Pong handled, do nothing else.
                    }
                } catch (e) {
                    // Not a pong message or not valid JSON, proceed to normal processing.
                }

                if (isReFetchingRef.current) {
                    wsBufferRef.current.push(ev.data);
                } else {
                    processWsMessage(ev.data);
                }
            };

            ws.onclose = () => {
                console.log(`WebSocket closed. Attempting to reconnect... (Attempt: ${reconnectAttemptsRef.current + 1})`);
                setWsStatus('disconnected');
                
                // Clear intervals and timeouts
                if (heartbeatTimeout) clearTimeout(heartbeatTimeout);
                if (pongTimeout) clearTimeout(pongTimeout);

                reconnectAttemptsRef.current++;
                // Exponential backoff with a cap
                const delay = Math.min(30000, 1000 * (2 ** reconnectAttemptsRef.current));

                if (reconnectTimerRef.current) {
                    clearTimeout(reconnectTimerRef.current);
                }

                reconnectTimerRef.current = window.setTimeout(connect, delay);
            };

            ws.onerror = (err) => {
                console.error("ws.onerror: WebSocket error:", err);
                // The onclose event will be fired automatically by the browser,
                // which will trigger the reconnection logic.
                ws.close();
            };
        };

        connect();

        return () => {
            window.removeEventListener('online', handleOnline);
            document.removeEventListener('visibilitychange', handleVisibilityChange);
            
            if (reconnectTimerRef.current) {
                clearTimeout(reconnectTimerRef.current);
            }

            // The connect function now handles clearing its own timers,
            // but we still need to cleanly close the connection.
            if (wsRef.current) {
                // Prevent onclose from firing and attempting to reconnect
                wsRef.current.onclose = null;
                wsRef.current.close();
                wsRef.current = null;
            }
        };
    }, [mode, shouldConnectWs, navigationTaskIdNum, handleStaleConnection, processWsMessage]);


    return {
        staticNavTaskData, // This is now the stable task definition
        contestantsById, // This is the dynamic map of contestants
        positionsByContestant,
        annotationsByContestant,
        scoreLogByContestant,
        gateScoresByContestant,
        dangerDataByContestant,
        gateArrowDataByContestant,
        progress,
        wsStatus,
        error,
    };
    }