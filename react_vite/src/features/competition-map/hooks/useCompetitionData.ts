import { useState, useEffect, useRef, useCallback } from 'react';
import { fetchNavigationTask, fetchContestantPaginatedTrack, fetchContestantScoreData, makeWebSocket } from '../api';
import type { Contestant, NavigationTask, TrackPosition, ScoreAnnotation, ScoreLogEntry, DangerData, GateArrowData } from '../types';

export function useCompetitionData(contestIdNum: number, navigationTaskIdNum: number, mode: 'realtime' | 'playback', showToast: (message: string, type?: 'success' | 'error' | 'info' | 'warning') => void) {
    const [staticNavTaskData, setStaticNavTaskData] = useState<NavigationTask | null>(null);
    const [contestantsById, setContestantsById] = useState<Record<number, Contestant>>({});
    const [positionsByContestant, setPositionsByContestant] = useState<Record<number, TrackPosition[]>>({});
    const [annotationsByContestant, setAnnotationsByContestant] = useState<Record<number, ScoreAnnotation[]>>({});
    const [scoreLogByContestant, setScoreLogByContestant] = useState<Record<number, ScoreLogEntry[]>>({});
    const [dangerDataByContestant, setDangerDataByContestant] = useState<Record<number, DangerData>>({});
    const [gateArrowDataByContestant, setGateArrowDataByContestant] = useState<Record<number, GateArrowData>>({});
    const [progress, setProgress] = useState({ loaded: 0, total: 0 });
    const [shouldConnectWs, setShouldConnectWs] = useState(false); // New state

    const navTaskRef = useRef(staticNavTaskData);
    useEffect(() => {
        navTaskRef.current = staticNavTaskData;
    }, [staticNavTaskData]);
    
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

    const processWsMessage = useCallback((data: string) => {
        try {
            const msg = JSON.parse(data) as { type: string; data: string };

            if (msg.type === 'contestant') {
                const c = JSON.parse(msg.data) as Contestant;
                setContestantsById(prev => ({ ...prev, [c.id]: c }));
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
            if (msg.type === 'gate_distance_and_estimate') {
                setGateArrowDataByContestant(prev => ({ ...prev, [contestantId]: payload }));
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

                if (gateData.final === true) {
                    const contestant = contestantsById[crossingContestantId];
                    const waypoint = staticNavTaskData?.route?.waypoints.find(wp => wp.name === gateData.waypoint_name);

                    if (contestant && waypoint && (waypoint.type === 'sp' || waypoint.type === 'fp')) {
                        const gateType = waypoint.type === 'sp' ? 'STARTING POINT' : 'FINISH POINT';
                        const scoreMessage = gateData.estimated_score !== undefined ? `Score: ${gateData.estimated_score.toFixed(1)}` : '';
                        showToast(
                            `#${contestant.contestant_number} ${contestant.team.crew.member1.first_name} ${contestant.team.crew.member1.last_name} crossed the ${gateType}! ${scoreMessage}`,
                            'success'
                        );
                    }
                }
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
            if (payload.score_log_entries && payload.score_log_entries.length > 0) {
                setScoreLogByContestantRef.current(prev => { // Use ref here
                    const newEntries = [...(prev[contestantId] || []), ...payload.score_log_entries];
                    newEntries.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
                    return { ...prev, [contestantId]: newEntries };
                });
            }
            if (payload.contestant_track) {
                setContestantsById(prev => {
                    const existingContestant = prev[contestantId];
                    if (existingContestant) {
                        return { ...prev, [contestantId]: { ...existingContestant, contestanttrack: payload.contestant_track } };
                    }
                    // If contestant doesn't exist, this means we received track data before contestant data.
                    // This is an edge case, but we should create a basic entry.
                    return { ...prev, [contestantId]: { id: contestantId, contestanttrack: payload.contestant_track } as Contestant };
                });
            }
        } catch (e) {
            console.error('WS parse error', e);
        }
    }, [showToast, staticNavTaskData, contestantsById]);


    const fetchAllContestantData = useCallback(async (currentNavTask: NavigationTask, onProgress: (p: {loaded: number, total: number}) => void) => {
        const total = currentNavTask.contestant_set.length;
        onProgress({ loaded: 0, total });
        let loaded = 0;

        const contestantPromises = currentNavTask.contestant_set.map(async (c) => {
            try {
                let cursor: string | null | undefined = undefined;
                const allPositions: TrackPosition[] = [];
                while (true) {
                    const page = await fetchContestantPaginatedTrack(contestIdNum, navigationTaskIdNum, c.id, cursor);
                    allPositions.push(...page.results);
                    if (!page.next) break;
                    cursor = page.next;
                }
                const scoreData = await fetchContestantScoreData(contestIdNum, navigationTaskIdNum, c.id);
                return {
                    contestant: { ...c, contestanttrack: scoreData.contestant_track }, // Return full contestant object
                    positions: allPositions.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()),
                    annotations: scoreData.annotations.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()),
                    scoreLogs: scoreData.score_log_entries.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()),
                };
            } catch (e) {
                console.error('Failed to fetch data for contestant', c.id, e);
                return null;
            } finally {
                loaded++;
                onProgress({ loaded, total });
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

        const { positionUpdates, annotationUpdates, scoreLogUpdates, contestantUpdates } = await fetchAllContestantData(navTaskRef.current, setProgress);
        
        setPositionsByContestant(positionUpdates);
        setAnnotationsByContestant(annotationUpdates);
        setScoreLogByContestant(scoreLogUpdates);
        setContestantsById(prev => ({ ...prev, ...contestantUpdates }));
        
        wsBufferRef.current.forEach(msg => processWsMessage(msg));
        wsBufferRef.current = [];

        setIsReFetching(false);
    }, [fetchAllContestantData, processWsMessage]);

    // Fetch navigation task and initial data
    useEffect(() => {
        let cancelled = false;
        (async () => {
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

                const { positionUpdates, annotationUpdates, scoreLogUpdates, contestantUpdates } = await fetchAllContestantData(task, setProgress);
                if (!cancelled) {
                    setPositionsByContestant(positionUpdates);
                    setAnnotationsByContestant(annotationUpdates);
                    setScoreLogByContestant(scoreLogUpdates);
                    setContestantsById(prev => ({ ...prev, ...contestantUpdates }));
                }
            }
        })().catch(console.error);
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
            const ws = makeWebSocket(navigationTaskIdNum);
            wsRef.current = ws;

            ws.onopen = () => {
            };

            ws.onmessage = (ev) => {
                if (isReFetchingRef.current) { // Use ref here
                    wsBufferRef.current.push(ev.data);
                } else {
                    processWsMessage(ev.data);
                }
            };

            ws.onclose = () => {
            };

            ws.onerror = (err) => {
                console.error("ws.onerror: WebSocket error:", err);
                ws.close();
            };
        };

        connect();

        return () => {
            window.removeEventListener('online', handleOnline);
            document.removeEventListener('visibilitychange', handleVisibilityChange);
            if (wsRef.current) {
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
    };
}