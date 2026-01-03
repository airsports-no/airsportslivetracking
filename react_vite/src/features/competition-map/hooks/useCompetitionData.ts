import { useState, useEffect, useRef } from 'react';
import { fetchNavigationTask, fetchContestantPaginatedTrack, fetchContestantScoreData, makeWebSocket } from '../api';
import type { NavigationTask, TrackPosition, ScoreAnnotation, ScoreLogEntry, DangerData, GateArrowData } from '../types';

export function useCompetitionData(contestIdNum: number, navigationTaskIdNum: number, mode: 'realtime' | 'playback') {
    const [navTask, setNavTask] = useState<NavigationTask | null>(null);
    const [positionsByContestant, setPositionsByContestant] = useState<Record<number, TrackPosition[]>>({});
    const [annotationsByContestant, setAnnotationsByContestant] = useState<Record<number, ScoreAnnotation[]>>({});
    const [scoreLogByContestant, setScoreLogByContestant] = useState<Record<number, ScoreLogEntry[]>>({});
    const [dangerDataByContestant, setDangerDataByContestant] = useState<Record<number, DangerData>>({});
    const [gateArrowDataByContestant, setGateArrowDataByContestant] = useState<Record<number, GateArrowData>>({});
    const [realtimeTime, setRealtimeTime] = useState<Date>(new Date());
    
    const wsRef = useRef<WebSocket | null>(null);

    // Fetch navigation task
    useEffect(() => {
        let cancelled = false;
        (async () => {
        const task = await fetchNavigationTask(contestIdNum, navigationTaskIdNum);
        if (!cancelled) setNavTask(task);
        })().catch(console.error);
        return () => { cancelled = true; };
    }, [contestIdNum, navigationTaskIdNum]);

    // Fetch initial data for all contestants
    useEffect(() => {
        if (!navTask) return;
        let cancelled = false;

        (async () => {
            const contestantPromises = navTask.contestant_set.map(async (c) => {
                try {
                    // Fetch paginated track
                    let cursor: string | null | undefined = undefined;
                    const allPositions: TrackPosition[] = [];
                    while (true) {
                        const page = await fetchContestantPaginatedTrack(contestIdNum, navigationTaskIdNum, c.id, cursor);
                        allPositions.push(...page.results);
                        if (!page.next) break;
                        cursor = page.next;
                    }

                    // Fetch score data
                    const scoreData = await fetchContestantScoreData(contestIdNum, navigationTaskIdNum, c.id);
                    
                    return {
                        contestantId: c.id,
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

            if (!cancelled) {
                const positionUpdates: Record<number, TrackPosition[]> = {};
                const annotationUpdates: Record<number, ScoreAnnotation[]> = {};
                const scoreLogUpdates: Record<number, ScoreLogEntry[]> = {};

                for (const data of allContestantData) {
                    if (data) {
                        positionUpdates[data.contestantId] = data.positions;
                        annotationUpdates[data.contestantId] = data.annotations;
                        scoreLogUpdates[data.contestantId] = data.scoreLogs;
                    }
                }

                setPositionsByContestant(positionUpdates);
                setAnnotationsByContestant(annotationUpdates);
                setScoreLogByContestant(scoreLogUpdates);
            }
        })();

        return () => { cancelled = true; };
    }, [navTask, contestIdNum, navigationTaskIdNum]);

    // WebSocket for realtime updates
    useEffect(() => {
        if (mode !== 'realtime' || !navTask) return;

        const ws = makeWebSocket(navigationTaskIdNum);
        wsRef.current = ws;

        ws.onmessage = (ev) => {
            try {
                const msg = JSON.parse(ev.data) as { type: string; data: string };

                if (msg.type === 'current_time') {
                    const iso = JSON.parse(msg.data);
                    setRealtimeTime(new Date(iso));
                    return;
                }
                
                if (msg.type === 'contestant') {
                    const c = JSON.parse(msg.data);
                    setNavTask(prev => prev ? { ...prev, contestant_set: [...prev.contestant_set.filter(x => x.id !== c.id), c] } : prev);
                    return;
                }
                
                if (msg.type === 'contestant_delete') {
                    const c = JSON.parse(msg.data);
                    setNavTask(prev => prev ? { ...prev, contestant_set: prev.contestant_set.filter(x => x.id !== c.id) } : prev);
                    return;
                }
                
                const payload = JSON.parse(msg.data) as any;
                const contestantId = payload.contestant_id;
                if (!contestantId) return;

                if (msg.type === 'danger_level') {
                    setDangerDataByContestant(prev => ({ ...prev, [contestantId]: payload }));
                    return;
                }
                if (msg.type === 'gate_distance_and_estimate') {
                    setGateArrowDataByContestant(prev => ({ ...prev, [contestantId]: payload }));
                    return;
                }

                if (payload.positions && payload.positions.length > 0) {
                    setPositionsByContestant(prev => {
                        const newPositions = [...(prev[contestantId] || []), ...payload.positions];
                        newPositions.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
                        return { ...prev, [contestantId]: newPositions };
                    });
                }
                if (payload.annotations && payload.annotations.length > 0) {
                    setAnnotationsByContestant(prev => {
                        const newAnnotations = [...(prev[contestantId] || []), ...payload.annotations];
                        newAnnotations.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
                        return { ...prev, [contestantId]: newAnnotations };
                    });
                }
                if (payload.score_log_entries && payload.score_log_entries.length > 0) {
                    setScoreLogByContestant(prev => {
                        const newEntries = [...(prev[contestantId] || []), ...payload.score_log_entries];
                        newEntries.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
                        return { ...prev, [contestantId]: newEntries };
                    });
                }
                if (payload.contestant_track) {
                    setNavTask(prev => {
                        if (!prev) return prev;
                        const newContestantSet = prev.contestant_set.map(c => {
                            if (c.id === contestantId) {
                                return { ...c, contestanttrack: payload.contestant_track };
                            }
                            return c;
                        });
                        return { ...prev, contestant_set: newContestantSet };
                    });
                }
            } catch (e) {
                console.error('WS parse error', e);
            }
        };

        ws.onclose = () => { /* auto-reconnect could be added */ };
        ws.onerror = () => { /* log */ };

        return () => {
            try { ws.close(); } catch { /* noop */ }
            wsRef.current = null;
        };
    }, [mode, navTask, navigationTaskIdNum]);

    return {
        navTask,
        positionsByContestant,
        annotationsByContestant,
        scoreLogByContestant,
        dangerDataByContestant,
        gateArrowDataByContestant,
        realtimeTime,
    };
}
