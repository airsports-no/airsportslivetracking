import { useState, useEffect, useRef, useCallback } from 'react';
import { fetchNavigationTask, fetchContestantPaginatedTrack, fetchContestantScoreData, makeWebSocket, fetchContestantSlice } from '../api';
import type { Contestant, NavigationTask, TrackPosition, ScoreAnnotation, ScoreLogEntry, DangerData, GateArrowData, Waypoint } from '../types';

export function useCompetitionData(contestIdNum: number, navigationTaskIdNum: number, mode: 'realtime' | 'playback', showToast: (message: string, type?: 'success' | 'error' | 'info' | 'warning') => void) {
    const [staticNavTaskData, setStaticNavTaskData] = useState<NavigationTask | null>(null);
    const [contestantsById, setContestantsById] = useState<Record<number, Contestant>>({});
    const [positionsByContestant, setPositionsByContestant] = useState<Record<number, TrackPosition[]>>({});
    const [annotationsByContestant, setAnnotationsByContestant] = useState<Record<number, ScoreAnnotation[]>>({});
    const [scoreLogByContestant, setScoreLogByContestant] = useState<Record<number, ScoreLogEntry[]>>({});
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

            if (msg.type === 'contestant') {
                const c = JSON.parse(msg.data) as Partial<Contestant> & { id: number };
                console.debug('WS: received contestant metadata', c);
                updateContestant(c.id, c);
                return;
            }

            if (msg.type === 'contestant_delete') {
                const c = JSON.parse(msg.data) as { contestant_id: number };
                setContestantsById(prev => {
                    const newContestants = { ...prev };
                    delete newContestants[c.contestant_id];
                    return newContestants;
                });
                return;
            }

            const payload = JSON.parse(msg.data) as any;
            const contestantId = payload.contestant_id;
            if (!contestantId) return;

            if (msg.type === 'danger_level') {
                setDangerDataByContestant(prev => ({ ...prev, [contestantId]: payload.danger_level }));
                return;
            }
            if (msg.type === 'playing_cards') {
                const playingCardsPayload = JSON.parse(msg.data);
                const contestantId = playingCardsPayload.contestant_id;
                const playing_cards = playingCardsPayload.playing_cards;

                updateContestant(contestantId, { playing_cards });
                return;
            }
            if (msg.type === 'crossing_time') {
                const crossingPayload = JSON.parse(msg.data) as {
                    contestant_id: number;
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
                return;
            }

            if (payload.positions && payload.positions.length > 0) {
                setPositionsByContestantRef.current(prev => { // Use ref here
                    const newPositions = [...(prev[contestantId] || []), ...payload.positions];
                    newPositions.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
                    return { ...prev, [contestantId]: newPositions };
                });
            }
            if (payload.annotations && payload.annotations.length > 0) {
                setAnnotationsByContestantRef.current(prev => { // Use ref here
                    const newAnnotations = [...(prev[contestantId] || []), ...payload.annotations];
                    newAnnotations.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
                    return { ...prev, [contestantId]: newAnnotations };
                });
            }
            if (msg.type === "score_log" && payload.score_log_entries && payload.score_log_entries.length > 0) {
                setScoreLogByContestantRef.current(prev => {
                    const existingScoreLogs = prev[contestantId] ?? [];
                    const newEntries = payload.score_log_entries; // These are the *newly arrived* entries, not all of them yet.

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

                    // The score_log WebSocket message contains the FULL history for the contestant,
                    // so we replace the existing log rather than appending.
                    const allScoreLogs = [...newEntries];
                    allScoreLogs.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
                    return { ...prev, [contestantId]: allScoreLogs };
                });
            }
            if (payload.contestant_track) {
                updateContestant(contestantId, { contestanttrack: payload.contestant_track });
            }
        } catch (e) {
            console.error('WS parse error', e);
        }
    }, [showToast, updateContestant]);


    const fetchAllContestantData = useCallback(async (contestantsToFetch: Contestant[], onProgress: (p: { loaded: number, total: number, message?: string }) => void) => {
        const now = new Date();
        const chunkSize = 15;

        onProgress({ loaded: 0, total: 100, message: 'Planning track stitching...' });

        // 1. Calculate total expected requests to provide a granular progress bar
        let totalRequests = 0;
        const contestantRequestPlans = contestantsToFetch.map(c => {
            const startTime = new Date(c.takeoff_time);
            const finishByTime = new Date(c.finished_by_time);
            const endTime = finishByTime < now ? finishByTime : now;
            
            const startMinute = Math.floor(startTime.getTime() / 60000) - 5;
            const endMinute = Math.ceil(endTime.getTime() / 60000);
            
            let requests = 1; // For score data
            let currentMinute = startMinute;
            while (currentMinute <= endMinute) {
                if (currentMinute % chunkSize === 0) {
                    const chunkEndTime = (currentMinute + chunkSize) * 60000;
                    if (chunkEndTime < now.getTime() - 60000 && currentMinute + chunkSize <= endMinute) {
                        currentMinute += chunkSize;
                    } else {
                        currentMinute++;
                    }
                } else {
                    currentMinute++;
                }
                requests++;
            }
            totalRequests += requests;
            return { startMinute, endMinute };
        });

        onProgress({ loaded: 0, total: 100, message: 'Initializing telemetry download...' });
        let loadedRequests = 0;

        const updateProgress = (msg?: string) => {
            loadedRequests++;
            const percentage = Math.round((loadedRequests / totalRequests) * 100);
            onProgress({ 
                loaded: percentage, 
                total: 100, 
                message: msg || `Downloading telemetry: ${percentage}%` 
            });
        };

        const contestantPromises = contestantsToFetch.map(async (c, idx) => {
            try {
                const { startMinute, endMinute } = contestantRequestPlans[idx];
                const slicePromises = [];
                
                let currentMinute = startMinute;
                while (currentMinute <= endMinute) {
                    const nextAligned = Math.ceil((currentMinute + 1) / chunkSize) * chunkSize;
                    
                    let p;
                    if (currentMinute % chunkSize !== 0) {
                        p = fetchContestantSlice(c.id, currentMinute).finally(() => updateProgress());
                        currentMinute++;
                    } else {
                        const chunkEndTime = (currentMinute + chunkSize) * 60000;
                        if (chunkEndTime < now.getTime() - 60000 && currentMinute + chunkSize <= endMinute) {
                            p = fetchContestantSlice(c.id, currentMinute, chunkSize).finally(() => updateProgress());
                            currentMinute += chunkSize;
                        } else {
                            p = fetchContestantSlice(c.id, currentMinute).finally(() => updateProgress());
                            currentMinute++;
                        }
                    }
                    slicePromises.push(p);
                }
                
                const sliceResults = await Promise.all(slicePromises);
                const allPositions: TrackPosition[] = sliceResults.flat();
                
                const scoreData = await fetchContestantScoreData(contestIdNum, navigationTaskIdNum, c.id).finally(() => {
                    updateProgress(`Processed scores for ${c.team.crew.member1.first_name}`);
                });

                return {
                    contestant: { ...c, contestanttrack: scoreData.contestant_track, playing_cards: scoreData.playing_cards },
                    positions: allPositions.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()),
                    annotations: scoreData.annotations.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()),
                    scoreLogs: scoreData.score_log_entries.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()),
                };
            } catch (e) {
                console.error('Failed to fetch data for contestant', c.id, e);
                return null;
            }
        });

        const allContestantData = await Promise.all(contestantPromises);
        const positionUpdates: Record<number, TrackPosition[]> = {};
        const annotationUpdates: Record<number, ScoreAnnotation[]> = {};
        const scoreLogUpdates: Record<number, ScoreLogEntry[]> = {};
        const contestantUpdates: Record<number, Contestant> = {};

        for (const data of allContestantData) {
            if (data) {
                positionUpdates[data.contestant.id] = data.positions;
                annotationUpdates[data.contestant.id] = data.annotations;
                scoreLogUpdates[data.contestant.id] = data.scoreLogs;
                contestantUpdates[data.contestant.id] = data.contestant;
            }
        }
        return { positionUpdates, annotationUpdates, scoreLogUpdates, contestantUpdates };
    }, [contestIdNum, navigationTaskIdNum]);


    const handleStaleConnection = useCallback(async () => {
        if (isReFetchingRef.current || !navTaskRef.current) {
            return;
        }

        setIsReFetching(true);
        wsBufferRef.current = [];

        const contestantsToRefetch = Object.values(contestantsByIdRef.current).filter(c => c && !c.contestanttrack?.calculator_finished);

        if (contestantsToRefetch.length > 0) {
            const { positionUpdates, annotationUpdates, scoreLogUpdates, contestantUpdates } = await fetchAllContestantData(contestantsToRefetch, setProgress);

            setPositionsByContestant(prev => ({...prev, ...positionUpdates}));
            setAnnotationsByContestant(prev => ({...prev, ...annotationUpdates}));
            setScoreLogByContestant(prev => ({...prev, ...scoreLogUpdates}));
            setContestantsById(prev => ({ ...prev, ...contestantUpdates }));
        }


        wsBufferRef.current.forEach(msg => processWsMessage(msg));
        wsBufferRef.current = [];

        setIsReFetching(false);
    }, [fetchAllContestantData, processWsMessage]);

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
                    setShouldConnectWs(true);

                    const { positionUpdates, annotationUpdates, scoreLogUpdates, contestantUpdates } = await fetchAllContestantData(task.contestant_set, setProgress);
                    if (!cancelled) {
                        setPositionsByContestant(positionUpdates);
                        setAnnotationsByContestant(annotationUpdates);
                        setScoreLogByContestant(scoreLogUpdates);
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
    }, [contestIdNum, navigationTaskIdNum, fetchAllContestantData]);

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
        dangerDataByContestant,
        gateArrowDataByContestant,
        progress,
        wsStatus,
        error,
    };
    }