import React, { useEffect, useMemo, useState } from 'react';
import L from 'leaflet';
import { useParams, Link } from 'react-router-dom';

import useMapInit from '../route-editor/components/map/useMapInit';
import { useCompetitionData } from './hooks/useCompetitionData';
import { usePlayback } from './hooks/usePlayback';
import { useMapLayers } from './hooks/useMapLayers';

import ResultsTable from './components/ResultsTable';
import ScoreLogTable from './components/ScoreLogTable';
import ProhibitedRenderer from "./components/track-renderers/ProhibitedRenderer";
import RouteRenderer from "./components/track-renderers/RouteRenderer";
import TimelineControls from "./components/TimelineControls";
import TeamPresentation from './components/TeamPresentation';
import ClockDisplay from './components/ClockDisplay';


export default function CompetitionMapPage() {
    const { contestId, navigationTaskId } = useParams();
    const contestIdNum = Number(contestId ?? 632);
    const navigationTaskIdNum = Number(navigationTaskId ?? 2129);

    const [mode, setMode] = useState<'realtime' | 'playback'>('realtime');
    const [showFullTrails, setShowFullTrails] = useState(false);
    const [selectedContestantId, setSelectedContestantId] = useState<number | null>(null);
    const [showScoreLog, setShowScoreLog] = useState(false);

    const mapRef = useMapInit();
    
    const {
        navTask,
        positionsByContestant,
        annotationsByContestant,
        scoreLogByContestant,
        dangerDataByContestant,
        gateArrowDataByContestant,
        realtimeTime,
    } = useCompetitionData(contestIdNum, navigationTaskIdNum, mode);
    
    const {
        playbackSpeed,
        setPlaybackSpeed,
        isPlaying,
        setIsPlaying,
        playbackTime,
        setPlaybackTime,
        playbackTimeInfo
    } = usePlayback(mode, positionsByContestant);

    const currentTime = mode === 'playback' ? playbackTime : realtimeTime;

    const [currentPositions, setCurrentPositions] = useState<Record<number, any[]>>({});
    const [currentScores, setCurrentScores] = useState<Record<number, number>>({});

    useEffect(() => {
        if (!navTask) return;

        if (mode !== 'playback') {
            setCurrentPositions(positionsByContestant);
            setCurrentScores({});
            return;
        };

        if (!currentTime) return;

        const pos: Record<number, any[]> = {};
        const scores: Record<number, number> = {};

        for (const c of navTask.contestant_set) {
            const contestantId = c.id;
            const allPos = positionsByContestant[contestantId] ?? [];
            pos[contestantId] = allPos.filter(p => new Date(p.time) <= currentTime);

            const allLogs = scoreLogByContestant[contestantId] ?? [];
            const initialScore = navTask.scorecard.initial_score ?? 0;
            scores[contestantId] = allLogs
                .filter(l => new Date(l.time) <= currentTime)
                .reduce((total, log) => total + log.points, initialScore);
        }
        setCurrentPositions(pos);
        setCurrentScores(scores);
    }, [mode, currentTime, positionsByContestant, scoreLogByContestant, navTask]);

    const handleContestantSelect = (id: number | null, showLog: boolean) => {
        setSelectedContestantId(id);
        setShowScoreLog(showLog);
    };
    
    useMapLayers({
        mapRef,
        navTask,
        currentPositions,
        showFullTrails,
        currentTime,
        mode,
        selectedContestantId,
        onContestantSelect: handleContestantSelect,
        annotationsByContestant,
        scoreLogByContestant,
    });
    
    // Deselection handler
    useEffect(() => {
        const map = mapRef.current;
        if (!map) return;
        const handler = () => {
            setSelectedContestantId(null);
            setShowScoreLog(false);
        };
        map.on('click', handler);
        return () => {
        map.off('click', handler);
        }
    }, [mapRef]);

    const standings = useMemo(() => {
        if (!navTask) return [] as any[];
        const dir = navTask.score_sorting_direction;
        const total = navTask.contestant_set.length;
    
        const getContestantsWithState = () => {
            if (mode === 'playback') {
                const startGateName = navTask.route.waypoints.find(wp => wp.type === 'sp')?.name;
                const finishGateName = navTask.route.waypoints.find(wp => wp.type === 'fp')?.name;
    
                return navTask.contestant_set.map((c, index) => {
                    let state = 'Waiting...';
                    const logsForTime = (scoreLogByContestant[c.id] ?? []).filter(log => new Date(log.time) <= currentTime);
                    
                    if (finishGateName && logsForTime.some(log => log.gate === finishGateName)) {
                        state = 'Finished';
                    } else if (startGateName && logsForTime.some(log => log.gate === startGateName)) {
                        state = 'Enroute';
                    }
                    
                    return {
                        id: c.id,
                        name: `#${c.contestant_number} ${c.team?.crew?.member1?.first_name ?? ''} ${c.team?.crew?.member1?.last_name ?? ''}`,
                        score: currentScores[c.id] ?? navTask.scorecard.initial_score ?? 0,
                        state: state,
                        color: `hsl(${(index / total) * 360}, 70%, 50%)`
                    };
                });
            }
    
            return navTask.contestant_set.map((c, index) => ({
                id: c.id,
                name: `#${c.contestant_number} ${c.team?.crew?.member1?.first_name ?? ''} ${c.team?.crew?.member1?.last_name ?? ''}`,
                score: c.contestanttrack?.score ?? 0,
                state: c.contestanttrack?.current_state ?? 'Waiting...',
                color: `hsl(${(index / total) * 360}, 70%, 50%)`
            }));
        };
    
        const allContestants = getContestantsWithState();
        const active = allContestants.filter(c => c.state !== 'Waiting...');
        const waiting = allContestants.filter(c => c.state === 'Waiting...');
        const sortFn = (a: {score: number}, b: {score:number}) => dir === 'asc' ? a.score - b.score : b.score - a.score;
        active.sort(sortFn);
        waiting.sort(sortFn);
        return [...active, ...waiting];
    }, [navTask, mode, currentScores, currentTime, scoreLogByContestant]);
    
    const selectedContestant = useMemo(() => {
        if (!selectedContestantId || !navTask) return null;
        return navTask.contestant_set.find(c => c.id === selectedContestantId);
    }, [selectedContestantId, navTask]);

    const firstWaitingIndex = standings.findIndex(s => s.state === 'Waiting...');

    const filteredScoreLog = useMemo(() => {
        if (!selectedContestantId || !scoreLogByContestant[selectedContestantId]) return [];
        if (mode === 'realtime') {
            return scoreLogByContestant[selectedContestantId];
        } else {
            return scoreLogByContestant[selectedContestantId].filter(log => new Date(log.time) <= currentTime);
        }
    }, [selectedContestantId, scoreLogByContestant, mode, currentTime]);

        return (
            <div className="flex flex-col h-screen">
                <div className="flex-1 relative">
                    <div id="map-container" className="h-full w-full" />
                    <ProhibitedRenderer map={mapRef.current} navTask={navTask} />
                                    <RouteRenderer map={mapRef.current} navTask={navTask} />
                                    
                                    <div className="absolute top-4 right-4 z-[1000]">
                                        <ClockDisplay time={currentTime} />
                                    </div>
                    
                                    <div className="absolute top-4 left-4 z-[1000] bg-base-100/80 backdrop-blur-sm border border-base-300 rounded-lg shadow-lg w-96">
                                        <div className="p-2 border-b border-base-300">
                                            <h2 className="font-bold text-lg truncate" title={navTask?.name}>{navTask?.name ?? 'Loading...'}</h2>
                                            
                                            <div className="flex justify-between items-center mt-2">
                                                <div className="join">
                                                    <button className={`btn btn-xs join-item ${mode === 'realtime' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => { if (mode !== 'realtime') { setMode('realtime'); setSelectedContestantId(null); setPlaybackTime(new Date()); } }}>Realtime</button>
                                                    <button className={`btn btn-xs join-item ${mode === 'playback' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => { if (mode !== 'playback') { setMode('playback'); setSelectedContestantId(null); } }}>Playback</button>
                                                </div>
                                                
                                                <label className="label cursor-pointer text-xs p-0">
                                                    <span className="label-text mr-1">Full Trails</span>
                                                    <input type="checkbox" className="toggle toggle-xs" checked={showFullTrails} onChange={e => setShowFullTrails(e.target.checked)} />
                                                </label>
                    
                                                                            <Link to={`/competition-map/${contestIdNum}/${navigationTaskIdNum}/info`} className="btn btn-xs btn-outline">Task Info</Link>
                                                                            {document.configuration.canChangeNavigationTask && (
                                                                                <a href={document.configuration.navigationTaskManagementLink} className="btn btn-xs btn-outline ml-2">Manage Task</a>
                                                                            )}
                                                                        </div>
                                                
                                                                        {mode === 'realtime' && navTask?.calculation_delay_minutes > 0 && (
                                                                            <div className="text-xs text-warning-content bg-warning rounded-md px-2 py-1 mt-2 text-center">
                                                                                Live data is delayed by {navTask.calculation_delay_minutes} minute(s).
                                                                            </div>
                                                                        )}
                                                                        
                                                                        {selectedContestant && (
                                                                            <div className="flex justify-between items-center mt-2 pt-2 border-t border-base-200 gap-2">
                                                                                <span className="text-xs font-bold truncate flex-1" title={`${selectedContestant.team.crew.member1.first_name} ${selectedContestant.team.crew.member1.last_name}`}>
                                                                                    Selected: #{selectedContestant.contestant_number} {selectedContestant.team.crew.member1.first_name}                                                    </span>
                                                    <div className="flex-none">
                                                        <button className="btn btn-xs btn-info mr-1" onClick={() => setShowScoreLog(true)}>Log</button>
                                                        <button className="btn btn-xs btn-ghost" onClick={() => {setSelectedContestantId(null); setShowScoreLog(false);}}>Clear</button>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                    
                                        {showScoreLog && selectedContestantId ? (
                                            <ScoreLogTable
                                                scoreLog={filteredScoreLog}
                                                contestantName={`#${selectedContestant?.contestant_number} ${selectedContestant?.team?.crew?.member1?.first_name ?? ''}`}
                                                onClose={() => setShowScoreLog(false)}
                                            />
                                        ) : (
                                            <ResultsTable
                                                rows={standings}
                                                dividerIndex={firstWaitingIndex}
                                                onRowClick={(id) => {
                                                    setSelectedContestantId(id);
                                                    setShowScoreLog(false);
                                                }}
                                            />
                                        )}
                                    </div>
                    
                                    {selectedContestant && (
                                        <div className={`absolute right-4 z-[1000] transition-all duration-300 ${(mode === 'playback' && playbackTimeInfo) ? 'bottom-24' : 'bottom-4'}`}>
                                            <TeamPresentation 
                                                contestant={selectedContestant} 
                                                dangerData={dangerDataByContestant[selectedContestant.id]}
                                                gateArrowData={gateArrowDataByContestant[selectedContestant.id]}
                                                score={standings.find(s => s.id === selectedContestant.id)?.score ?? 0}
                                            />
                                        </div>
                                    )}
                                    {mode === 'playback' && playbackTimeInfo && (
                                        <TimelineControls
                                            currentTime={currentTime}
                                            startTime={playbackTimeInfo.start}
                                            endTime={playbackTimeInfo.end}
                                            isPlaying={isPlaying}
                                            playbackSpeed={playbackSpeed}
                                            onPlayPause={() => setIsPlaying(p => !p)}
                                            onJumpToStart={() => setPlaybackTime(playbackTimeInfo.start)}
                                            onTimeChange={setPlaybackTime}
                                            onSpeedChange={setPlaybackSpeed}
                                        />
                                    )}
                                </div>
                            </div>
                        );}