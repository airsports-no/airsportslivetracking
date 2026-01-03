import React, { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import useMapInit from '../route-editor/components/map/useMapInit';
import { fetchNavigationTask, fetchContestantScoreData, makeWebSocket, fetchContestantPaginatedTrack } from './api';
import type { NavigationTask, TrackPosition, ScoreAnnotation, ScoreLogEntry } from './types';
import { planeIcon } from './components/icons';
import ResultsTable from './components/ResultsTable';
import ScoreLogTable from './components/ScoreLogTable';
import { useParams, Link } from 'react-router-dom';
import ProhibitedRenderer from "./components/track-renderers/ProhibitedRenderer";
import RouteRenderer from "./components/track-renderers/RouteRenderer";
import TimelineControls from "./components/TimelineControls";

interface ContestantLayers {
  marker: L.Marker;
  recentTrail: L.Polyline;
  fullTrail: L.Polyline;
}

interface AnnotationLayers {
    [key: number]: L.Marker[];
}

function getAnnotationIcon(annotationType: string): L.DivIcon {
    let className = 'bg-gray-500'; // default
    if (annotationType === 'anomaly') {
        className = 'bg-red-500';
    } else if (annotationType === 'information') {
        className = 'bg-blue-500';
    }
    return L.divIcon({
        html: `<div class="w-3 h-3 rounded-full ${className} border-2 border-white"></div>`,
        className: 'bg-transparent',
        iconSize: [12, 12],
    });
}


function hslColor(index: number, total: number): string {
  const hue = Math.round((index / Math.max(1, total)) * 360);
  return `hsl(${hue}, 70%, 50%)`;
}

function lastMinutesPositions(all: TrackPosition[], minutes: number, currentTime: Date): TrackPosition[] {
  const cutoff = new Date(currentTime.getTime() - minutes * 60_000);
  return all.filter(p => new Date(p.time) >= cutoff);
}

export default function CompetitionMapPage() {
  const { contestId, navigationTaskId } = useParams();
  const contestIdNum = Number(contestId ?? 632);
  const navigationTaskIdNum = Number(navigationTaskId ?? 2129);

  const mapRef = useMapInit();
  const [navTask, setNavTask] = useState<NavigationTask | null>(null);
  
  // Full data from server
  const [positionsByContestant, setPositionsByContestant] = useState<Record<number, TrackPosition[]>>({});
  const [annotationsByContestant, setAnnotationsByContestant] = useState<Record<number, ScoreAnnotation[]>>({});
  const [scoreLogByContestant, setScoreLogByContestant] = useState<Record<number, ScoreLogEntry[]>>({});

  const [showFullTrails, setShowFullTrails] = useState(false);
  const [mode, setMode] = useState<'realtime' | 'playback'>('realtime');
  const [playbackSpeed, setPlaybackSpeed] = useState(1); // 1x, 2x, etc.
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState<Date>(new Date());
  const [playbackTimeInfo, setPlaybackTimeInfo] = useState<{start: Date, end: Date} | null>(null);
  const [selectedContestantId, setSelectedContestantId] = useState<number | null>(null);
  const [showScoreLog, setShowScoreLog] = useState(false);

  // Data filtered by currentTime for display
  const [currentPositions, setCurrentPositions] = useState<Record<number, TrackPosition[]>>({});
  const [currentScores, setCurrentScores] = useState<Record<number, number>>({});

  const wsRef = useRef<WebSocket | null>(null);
  const playbackTimerRef = useRef<number | null>(null);
  const layersRef = useRef<Record<number, ContestantLayers>>({});
  const annotationLayersRef = useRef<L.Marker[]>([]);


  // Fetch navigation task
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const task = await fetchNavigationTask(contestIdNum, navigationTaskIdNum);
      if (!cancelled) setNavTask(task);
    })().catch(console.error);
    return () => { cancelled = true; };
  }, [contestIdNum, navigationTaskIdNum]);

  // Fetch initial data
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
          setCurrentTime(new Date(iso));
        } else if (msg.type === 'contestant') {
          // New contestant might join mid-flight
          const c = JSON.parse(msg.data);
          setNavTask(prev => prev ? { ...prev, contestant_set: [...prev.contestant_set.filter(x => x.id !== c.id), c] } : prev);
        } else if (msg.type === 'contestant_delete') {
          const c = JSON.parse(msg.data);
          setNavTask(prev => prev ? { ...prev, contestant_set: prev.contestant_set.filter(x => x.id !== c.id) } : prev);
        } else {
            const payload = JSON.parse(msg.data) as any;
            const contestantId = payload.contestant_id;
            if (!contestantId) return;

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

  // Playback mode setup
  useEffect(() => {
    if (mode === 'playback') {
      setIsPlaying(false);
      // Clear layers
      Object.values(layersRef.current).forEach(l => {
        l.marker.remove();
        l.recentTrail.remove();
        l.fullTrail.remove();
      });
      layersRef.current = {};
      annotationLayersRef.current.forEach(m => m.remove());
      annotationLayersRef.current = [];

      // Determine time range
      const allPositions = Object.values(positionsByContestant).flat();
      if (allPositions.length > 0) {
        const start = new Date(Math.min(...allPositions.map(p => new Date(p.time).getTime())));
        const end = new Date(Math.max(...allPositions.map(p => new Date(p.time).getTime())));
        setPlaybackTimeInfo({start, end});
        setCurrentTime(start);
      }
    }
  }, [mode, positionsByContestant]);


  // Playback timer
  useEffect(() => {
    if (mode !== 'playback' || !playbackTimeInfo || !isPlaying) {
      if (playbackTimerRef.current) {
        window.clearInterval(playbackTimerRef.current);
        playbackTimerRef.current = null;
      }
      return;
    }

    const SCREEN_UPDATE_INTERVAL_MS = 50;
    const timeStepMs = playbackSpeed * SCREEN_UPDATE_INTERVAL_MS;

    playbackTimerRef.current = window.setInterval(() => {
      setCurrentTime(prevTime => {
        const newTime = new Date(prevTime.getTime() + timeStepMs);
        if (newTime >= playbackTimeInfo.end) {
            if(playbackTimerRef.current) clearInterval(playbackTimerRef.current);
            setIsPlaying(false);
            return playbackTimeInfo.end;
        }
        return newTime;
      });
    }, SCREEN_UPDATE_INTERVAL_MS);
    
    return () => {
      if (playbackTimerRef.current) {
        window.clearInterval(playbackTimerRef.current);
        playbackTimerRef.current = null;
      }
    };
  }, [mode, playbackSpeed, playbackTimeInfo, isPlaying]);


  // Process data for current time
  useEffect(() => {
    if (!navTask) return;

    if (mode !== 'playback') {
        setCurrentPositions(positionsByContestant);
        setCurrentScores({});
        return;
    };

    if (!currentTime) return;

    const pos: Record<number, TrackPosition[]> = {};
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


  // Create/update Leaflet layers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !navTask) return;
    
    const total = navTask.contestant_set.length;
    for (const [index, c] of navTask.contestant_set.entries()) {
      const color = hslColor(index, total);
      const positions = currentPositions[c.id] ?? [];
      
      const isSelected = selectedContestantId === c.id;
      const isAnySelected = selectedContestantId !== null;

      const visiblePositions = (isAnySelected && !isSelected) ? [] : (mode === 'playback' || isSelected)
        ? positions 
        : lastMinutesPositions(positions, 5, currentTime);

      if (!layersRef.current[c.id]) {
        // Initialize layers
        const marker = L.marker([positions[0]?.latitude ?? 0, positions[0]?.longitude ?? 0], {
          icon: planeIcon(c.contestant_number, color, positions[positions.length - 1]?.course ?? 0),
        }).addTo(map);
        marker.on('click', (e) => {
            L.DomEvent.stopPropagation(e);
            setSelectedContestantId(c.id);
            setShowScoreLog(false);
        });
        const recentTrail = L.polyline([], { color, weight: 3, opacity: 0.9 }).addTo(map);
        const fullTrail = L.polyline([], { color, weight: 2, opacity: 0.3 }).addTo(map);
        layersRef.current[c.id] = { marker, recentTrail, fullTrail };
      }
      const { marker, recentTrail, fullTrail } = layersRef.current[c.id];

      // Update marker position & orientation
      const latest = positions[positions.length - 1];
      if (latest && !(isAnySelected && !isSelected)) {
        marker.setLatLng([latest.latitude, latest.longitude]);
        marker.setIcon(planeIcon(c.contestant_number, color, latest.course ?? 0));
        marker.setOpacity(1);
      } else {
        marker.setOpacity(0);
      }

      // Update trails
      if (showFullTrails || isSelected) {
          const fullLatLngs = positions.map(p => [p.latitude, p.longitude] as [number, number]);
          fullTrail.setLatLngs(fullLatLngs);
          fullTrail.setStyle({opacity: 0.5});
          recentTrail.setStyle({opacity: 0}); // Hide recent trail
      } else {
          const recentPositions = lastMinutesPositions(positions, 5, currentTime);
          const recentLatLngs = recentPositions.map(p => [p.latitude, p.longitude] as [number, number]);
          recentTrail.setLatLngs(recentLatLngs);
          recentTrail.setStyle({opacity: 0.9});
          fullTrail.setStyle({opacity: 0}); // Hide full trail
      }
    }
    
    // Render annotations for selected contestant
    annotationLayersRef.current.forEach(m => m.remove());
    annotationLayersRef.current = [];
    if(selectedContestantId) {
        const allAnnotations = annotationsByContestant[selectedContestantId] ?? [];
        const allLogs = scoreLogByContestant[selectedContestantId] ?? [];
        
        const visibleAnnotations = allAnnotations.filter(ann => new Date(ann.time) <= currentTime);

        visibleAnnotations.forEach(ann => {
            const scoreLog = ann.score_log_entry ? allLogs.find(l => l.id === ann.score_log_entry) : null;
            const marker = L.marker([ann.latitude, ann.longitude], {icon: getAnnotationIcon(ann.type)})
                .bindTooltip(`
                    <b>${ann.gate} (${ann.type})</b><br/>
                    ${ann.message}<br/>
                    <small>${new Date(ann.time).toLocaleString()}</small>
                    ${scoreLog ? `<br/><b>Score: ${scoreLog.points}</b>` : ''}
                `)
                .addTo(map);
            annotationLayersRef.current.push(marker);
        });
    }

  }, [mapRef, navTask, currentPositions, showFullTrails, currentTime, mode, selectedContestantId, annotationsByContestant, scoreLogByContestant]);

  const standings = useMemo(() => {
    if (!navTask) return [] as { id: number; name: string; score: number }[];
    const dir = navTask.score_sorting_direction;

    if (mode === 'playback' && Object.keys(currentScores).length > 0) {
        return [...navTask.contestant_set]
          .map(c => ({ id: c.id, name: `#${c.contestant_number} ${c.team?.crew?.member1?.first_name ?? ''} ${c.team?.crew?.member1?.last_name ?? ''}`, score: currentScores[c.id] ?? navTask.scorecard.initial_score ?? 0 }))
          .sort((a, b) => dir === 'asc' ? a.score - b.score : b.score - a.score);
    }

    // Realtime mode
    return [...navTask.contestant_set]
      .map(c => ({ id: c.id, name: `#${c.contestant_number} ${c.team?.crew?.member1?.first_name ?? ''} ${c.team?.crew?.member1?.last_name ?? ''}`, score: c.contestanttrack?.score ?? 0 }))
      .sort((a, b) => dir === 'asc' ? a.score - b.score : b.score - a.score);
  }, [navTask, mode, currentScores]);

  const selectedContestant = useMemo(() => {
    if (!selectedContestantId || !navTask) return null;
    return navTask.contestant_set.find(c => c.id === selectedContestantId);
  }, [selectedContestantId, navTask]);

  return (
    <div className="flex flex-col h-screen">
      <div className="navbar bg-base-200 px-4">
        <div className="flex-1">
          <Link to="/" className="btn btn-ghost text-xl">Home</Link>
          <span className="mx-2">Competition Map</span>
          {navTask && <span className="opacity-60">{navTask.name}</span>}
        </div>
        <div className="flex items-center gap-4">
          { selectedContestantId && <button className="btn btn-sm btn-info" onClick={() => setShowScoreLog(true)}>View Score Log</button>}
          { selectedContestantId && <button className="btn btn-sm btn-warning" onClick={() => {setSelectedContestantId(null); setShowScoreLog(false);}}>Clear Selection</button>}
          <label className="label cursor-pointer">
            <span className="label-text">Show full trails</span>
            <input type="checkbox" className="toggle toggle-primary ml-2" checked={showFullTrails} onChange={e => setShowFullTrails(e.target.checked)} />
          </label>
          <div className="form-control">
            <label className="label cursor-pointer">
              <span className="label-text">Realtime</span>
              <input type="radio" name="mode" className="radio ml-2" checked={mode === 'realtime'} onChange={() => setMode('realtime')} />
            </label>
          </div>
          <div className="form-control">
            <label className="label cursor-pointer">
              <span className="label-text">Playback</span>
              <input type="radio" name="mode" className="radio ml-2" checked={mode === 'playback'} onChange={() => setMode('playback')} />
            </label>
          </div>
        </div>
      </div>
      <div className="flex-1 relative">
        <div id="map-container" className="h-full w-full" />
        <ProhibitedRenderer map={mapRef.current} navTask={navTask} />
        <RouteRenderer map={mapRef.current} navTask={navTask} />
        <div className="absolute top-4 left-4 z-[1000] bg-base-100/80 backdrop-blur-sm border border-base-300 rounded-lg shadow-lg w-96">
            {showScoreLog && selectedContestantId && scoreLogByContestant[selectedContestantId] ? (
                <ScoreLogTable
                    scoreLog={scoreLogByContestant[selectedContestantId]}
                    contestantName={`#${selectedContestant?.contestant_number} ${selectedContestant?.team?.crew?.member1?.first_name ?? ''}`}
                    onClose={() => setShowScoreLog(false)}
                />
            ) : (
                <ResultsTable
                    rows={standings}
                    onRowClick={(id) => {
                        setSelectedContestantId(id);
                        setShowScoreLog(false);
                    }}
                />
            )}
        </div>
        {mode === 'playback' && playbackTimeInfo && (
            <TimelineControls
                currentTime={currentTime}
                startTime={playbackTimeInfo.start}
                endTime={playbackTimeInfo.end}
                isPlaying={isPlaying}
                playbackSpeed={playbackSpeed}
                onPlayPause={() => setIsPlaying(p => !p)}
                onJumpToStart={() => setCurrentTime(playbackTimeInfo.start)}
                onTimeChange={(t) => {
                    setIsPlaying(false);
                    setCurrentTime(t);
                }}
                onSpeedChange={setPlaybackSpeed}
            />
        )}
      </div>
    </div>
  );
}
