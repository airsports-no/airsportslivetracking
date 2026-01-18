import React, { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import { useParams, Link } from 'react-router-dom';

import useMapInit from '../route-editor/components/map/useMapInit';
import { useCompetitionData } from './hooks/useCompetitionData';
import { usePlayback } from './hooks/usePlayback';
import { useMapLayers } from './hooks/useMapLayers';
import { useToast } from './hooks/useToast'; // Import useToast
import { fetchContestDetails } from './api';

import ResultsTable from './components/ResultsTable';
import ScoreLogTable from './components/ScoreLogTable';
import ProhibitedRenderer from "./components/track-renderers/ProhibitedRenderer";
import RouteRenderer from "./components/track-renderers/RouteRenderer";
import TimelineControls from "./components/TimelineControls";
import TeamPresentation from './components/TeamPresentation';
import ClockDisplay from './components/ClockDisplay';
import Disclaimer from './components/Disclaimer';
import TaskInfoModal from './TaskInfoModal';
import { ChevronUp, ChevronDown } from 'lucide-react';
import { reverse } from '../../urls';




export default function CompetitionMapPage() {
  const { contestId, navigationTaskId } = useParams();
  const contestIdNum = Number(contestId ?? 632);
  const navigationTaskIdNum = Number(navigationTaskId ?? 2129);

  const [mode, setMode] = useState<'realtime' | 'playback'>('realtime');
  const [showFullTrails, setShowFullTrails] = useState(false);
  const [selectedContestantId, setSelectedContestantId] = useState<number | null>(null);
  const [showScoreLog, setShowScoreLog] = useState(false);
  const [userShowBackgroundMap, setUserShowBackgroundMap] = useState(true);
  const [userShowSecrets, setUserShowSecrets] = useState(true);
  const [hasMapBeenFitted, setHasMapBeenFitted] = useState(false); // New state for initial map fit
  const [isRankingCollapsed, setIsRankingCollapsed] = useState(false);
  const [isInfoModalOpen, setIsInfoModalOpen] = useState(false);
  const [permanentAnnotations, setPermanentAnnotations] = useState(false);
  const [contestDetails, setContestDetails] = useState<any | null>(null);

  useEffect(() => {
    if (contestIdNum) {
        fetchContestDetails(contestIdNum)
            .then(setContestDetails)
            .catch(err => {
                console.error("Error fetching contest details for contest ID", contestIdNum, ":", err);
                setContestDetails(null); // Ensure state is reset on error
            });
    } else {
        console.log("contestIdNum is falsy, not fetching contest details.");
    }
  }, [contestIdNum]);



  const teamPresentationContainerRef = useRef<HTMLDivElement>(null);
  const [teamPresentationScale, setTeamPresentationScale] = useState(1);

    const { toasts, showToast, removeToast, ToastContainer } = useToast(); // Initialize toast hook


  const {
    staticNavTaskData, // Renamed from navTask
    contestantsById, // New, dynamic map of contestants
    positionsByContestant,
    annotationsByContestant,
    scoreLogByContestant,
    dangerDataByContestant,
    gateArrowDataByContestant,
    progress,
    wsStatus,
  } = useCompetitionData(contestIdNum, navigationTaskIdNum, mode, showToast); // Pass showToast

  const selectedContestant = useMemo(() => {
    if (!selectedContestantId || !staticNavTaskData) return null; // Still needs staticNavTaskData for general check
    return contestantsById[selectedContestantId]; // Updated
  }, [selectedContestantId, staticNavTaskData, contestantsById]);

  useEffect(() => {
    const element = teamPresentationContainerRef.current;
    if (!element) return;

    const observer = new ResizeObserver(entries => {
      if (entries[0]) {
        const width = entries[0].contentRect.width;
        // This is the ideal width of the TeamPresentation component at scale=1.
        // It's used as a baseline to calculate the scale factor.
        const designWidth = 800;
        if (width > 0) {
          setTeamPresentationScale(width / designWidth);
        }
      }
    });

    observer.observe(element);
    return () => observer.disconnect();
  }, [selectedContestant]);


  const mapRef = useMapInit();
  const tileLayerRef = useRef<L.TileLayer | null>(null);

  const previousStaticNavTaskDataRef = useRef(); // Add this ref

  useEffect(() => {
    console.log("CompetitionMapPage: staticNavTaskData change detection.");
    if (previousStaticNavTaskDataRef.current && previousStaticNavTaskDataRef.current !== staticNavTaskData) {
      console.log("CompetitionMapPage: staticNavTaskData reference CHANGED!");
      console.log("  Old ref:", previousStaticNavTaskDataRef.current);
      console.log("  New ref:", staticNavTaskData);
    }
    previousStaticNavTaskDataRef.current = staticNavTaskData;
  }, [staticNavTaskData]); // Trigger on staticNavTaskData changes

  useEffect(() => {
    if (staticNavTaskData) {
        setUserShowBackgroundMap(staticNavTaskData.display_background_map);
        setUserShowSecrets(staticNavTaskData.display_secrets);
    }
  }, [staticNavTaskData]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (tileLayerRef.current) {
        tileLayerRef.current.remove();
    }

    if (staticNavTaskData?.display_background_map && userShowBackgroundMap) {
        const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors'
        }).addTo(map);
        tileLayerRef.current = osm;
    }
  }, [staticNavTaskData, mapRef, userShowBackgroundMap]);

  
  const {
    playbackSpeed,
    setPlaybackSpeed,
    isPlaying,
    setIsPlaying,
    playbackTime,
    setPlaybackTime,
    playbackTimeInfo
  } = usePlayback(mode, positionsByContestant);

  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const realtimeTime = useMemo(() => {
    if (!staticNavTaskData?.calculation_delay_minutes) {
        return now;
    }
    const delayMs = staticNavTaskData.calculation_delay_minutes * 60 * 1000;
    return new Date(now.getTime() - delayMs);
  }, [now, staticNavTaskData]);

  const currentTime = mode === 'playback' ? playbackTime : realtimeTime;

  // Default to full trails if task is over or no one is running
  useEffect(() => {
    if (!staticNavTaskData) return;

    const isAfterFinishTime = currentTime > new Date(staticNavTaskData.finish_time);
    const contestants = Object.values(contestantsById);
    const anyRunning = contestants.some(c => 
      c.contestanttrack?.calculator_started && !c.contestanttrack?.calculator_finished
    );

    if (isAfterFinishTime || (contestants.length > 0 && !anyRunning)) {
      setShowFullTrails(true);
    }
  }, [staticNavTaskData, contestantsById, currentTime]);

  const [currentPositions, setCurrentPositions] = useState<Record<number, any[]>>({});
  const [currentScores, setCurrentScores] = useState<Record<number, number>>({});

  useEffect(() => {
    if (!staticNavTaskData) return; // Still needs staticNavTaskData for scorecard

    if (mode !== 'playback') {
      setCurrentPositions(positionsByContestant);
      setCurrentScores({});
      return;
    };

    if (!currentTime) return;

    const pos: Record<number, any[]> = {};
    const scores: Record<number, number> = {};

    for (const c of Object.values(contestantsById)) { // <--- Changed
      const contestantId = c.id;
      const allPos = positionsByContestant[contestantId] ?? [];
      pos[contestantId] = allPos.filter(p => new Date(p.time) <= currentTime);

      const allLogs = scoreLogByContestant[contestantId] ?? [];
      const initialScore = staticNavTaskData.scorecard.initial_score ?? 0;
      scores[contestantId] = allLogs
        .filter(l => new Date(l.time) <= currentTime)
        .reduce((total, log) => total + log.points, initialScore);
    }
    setCurrentPositions(pos);
    setCurrentScores(scores);
  }, [mode, currentTime, positionsByContestant, scoreLogByContestant, staticNavTaskData, contestantsById]);

  const handleContestantSelect = (id: number | null, showLog: boolean) => {
    setSelectedContestantId(id);
    setShowScoreLog(showLog);
  };

  useMapLayers({
    mapRef,
    navTask: staticNavTaskData,
    contestants: Object.values(contestantsById), // Pass the dynamic contestants
    currentPositions,
    showFullTrails,
    currentTime,
    mode,
    selectedContestantId,
    onContestantSelect: handleContestantSelect,
    annotationsByContestant,
    scoreLogByContestant,
    userShowSecrets,
    permanentAnnotations,
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
    if (!staticNavTaskData) return [] as any[];
    const dir = staticNavTaskData.score_sorting_direction;
    const allContestantsData = Object.values(contestantsById);
    const total = allContestantsData.length;
    const startGateName = staticNavTaskData.route.waypoints.find(wp => wp.type === 'sp')?.name;

    const getContestantsWithState = () => {
      if (mode === 'playback') {
        const finishGateName = staticNavTaskData.route.waypoints.find(wp => wp.type === 'fp')?.name;

        return allContestantsData.map((c, index) => { // Updated
          let state = 'Waiting...';
          const logsForTime = (scoreLogByContestant[c.id] ?? []).filter(log => new Date(log.time) <= currentTime);

          if (finishGateName && logsForTime.some(log => log.gate === finishGateName)) {
            state = 'Finished';
          } else if (startGateName && logsForTime.some(log => log.gate === startGateName)) {
            state = 'Enroute';
          }

          let countdown = null;
          if (state === 'Waiting...' && !c.adaptive_start && startGateName && c.gate_times?.[startGateName]) {
              const startTime = new Date(c.gate_times[startGateName]);
              const diffSeconds = (startTime.getTime() - currentTime.getTime()) / 1000;
              if (diffSeconds > 0) {
                  countdown = diffSeconds;
              }
          }

          return {
            id: c.id,
            name: `#${c.contestant_number} ${c.team?.crew?.member1?.first_name ?? ''} ${c.team?.crew?.member1?.last_name ?? ''}`,
            score: currentScores[c.id] ?? staticNavTaskData.scorecard.initial_score ?? 0,
            state: state,
            color: `hsl(${(index / total) * 360}, 70%, 50%)`,
            countdown: countdown,
          };
        });
      }

      return allContestantsData.map((c, index) => {
        let countdown = null;
        if (c.contestanttrack?.current_state === 'Waiting...' && !c.adaptive_start && startGateName && c.gate_times?.[startGateName]) {
            const startTime = new Date(c.gate_times[startGateName]);
            const diffSeconds = (startTime.getTime() - currentTime.getTime()) / 1000;
            if (diffSeconds > 0) {
                countdown = diffSeconds;
            }
        }
        return {
            id: c.id,
            name: `#${c.contestant_number} ${c.team?.crew?.member1?.first_name ?? ''} ${c.team?.crew?.member1?.last_name ?? ''}`,
            score: c.contestanttrack?.score ?? 0,
            state: c.contestanttrack?.current_state ?? 'Waiting...',
            color: `hsl(${(index / total) * 360}, 70%, 50%)`,
            countdown: countdown,
        };
      });
    };

    const allContestants = getContestantsWithState();
    const active = allContestants.filter(c => c.state !== 'Waiting...');
    const waiting = allContestants.filter(c => c.state === 'Waiting...');
    const sortFn = (a: { score: number }, b: { score: number }) => dir === 'asc' ? a.score - b.score : b.score - a.score;
    active.sort(sortFn);
    waiting.sort(sortFn);
    return [...active, ...waiting];
  }, [staticNavTaskData, contestantsById, mode, currentScores, currentTime, scoreLogByContestant]);



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
    <div className="flex flex-col h-[calc(100vh-66px)]">
      <TaskInfoModal isOpen={isInfoModalOpen} onClose={() => setIsInfoModalOpen(false)} />
      <ToastContainer toasts={toasts} removeToast={removeToast} /> {/* Render ToastContainer */}
      <div className="flex-1 relative">
        <div id="map-container" className="h-full w-full" />
        <Disclaimer />
        <ProhibitedRenderer map={mapRef.current} navTask={staticNavTaskData} />
        <RouteRenderer
          map={mapRef.current}
          route={staticNavTaskData?.route ?? null}
          taskType={staticNavTaskData?.scorecard?.task_type ?? null}
          navTaskDisplaySecrets={staticNavTaskData?.display_secrets ?? false}
          displaySecrets={userShowSecrets}
          contestants={contestantsById}
          selectedContestantId={selectedContestantId}
          isInitialLoad={!hasMapBeenFitted}
          onMapFit={setHasMapBeenFitted}
        />

        <div className="absolute top-4 right-4 z-[1000]">
          <ClockDisplay time={currentTime} timeZone={staticNavTaskData?.time_zone} />
        </div>
        
        {mode === 'realtime' && wsStatus === 'disconnected' && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[1000] bg-error text-error-content p-2 rounded-lg shadow-md text-center max-w-sm">
                <h3 className="font-bold text-base">Offline</h3>
                <p className="text-sm">Connection lost. Attempting to reconnect...</p>
            </div>
        )}

        {/* The toast display will now be placed relative to this flex-1 relative container */}


        <div className="absolute top-4 left-4 z-[1000] bg-base-100/80 backdrop-blur-sm border border-base-300 rounded-lg shadow-lg w-96 max-w-[calc(100vw-2rem)]">
          <div className="p-2 border-b border-base-300">
            <div className="flex justify-between items-center">
              <h2 className="font-bold text-lg truncate" title={staticNavTaskData?.name}>{staticNavTaskData?.name ?? 'Loading...'}</h2>
              <button onClick={() => setIsRankingCollapsed(!isRankingCollapsed)} className="btn btn-ghost btn-sm btn-square">
                {isRankingCollapsed ? <ChevronDown size={20} /> : <ChevronUp size={20} />}
              </button>
            </div>


            <div className="flex justify-between items-center mt-2 flex-wrap gap-2">
              <div className="join">
                <button className={`btn btn-xs join-item ${mode === 'realtime' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => { if (mode !== 'realtime') { setMode('realtime'); setSelectedContestantId(null); setPlaybackTime(new Date()); } }}>Realtime</button>
                <button className={`btn btn-xs join-item ${mode === 'playback' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => { if (mode !== 'playback') { setMode('playback'); setSelectedContestantId(null); } }}>Playback</button>
              </div>

              <label className="label cursor-pointer text-xs p-0">
                <span className="label-text mr-1">Full Trails</span>
                <input type="checkbox" className="toggle toggle-xs" checked={showFullTrails} onChange={e => setShowFullTrails(e.target.checked)} />
              </label>

              <button onClick={() => setIsInfoModalOpen(true)} className="btn btn-xs btn-outline">Task Info</button>
              {staticNavTaskData?.user_has_change_permission && (
                <a href={reverse("navigationtask_detail", navigationTaskId)} className="btn btn-xs btn-outline ml-2">Manage Task</a>
              )}
              {staticNavTaskData?.allow_self_management && (
                <Link to={`/schedule-flight?contestId=${contestIdNum}&navigationTaskId=${navigationTaskIdNum}`} className="btn btn-xs btn-outline ml-2">Schedule Flight</Link>
              )}
              {/* Settings Dropdown */}
              <div className="dropdown dropdown-end">
                <div tabIndex={0} role="button" className="btn btn-xs btn-outline ml-2">Settings</div>
                <ul tabIndex={0} className="dropdown-content z-[11] menu p-2 shadow bg-base-100 rounded-box w-52">
                  <li>
                    <label className="label cursor-pointer">
                      <span className="label-text">Show Background Map</span>
                      <input 
                        type="checkbox" 
                        className="toggle toggle-primary" 
                        checked={userShowBackgroundMap} 
                        onChange={(e) => setUserShowBackgroundMap(e.target.checked)}
                        disabled={!staticNavTaskData?.display_background_map}
                      />
                    </label>
                  </li>
                  <li>
                    <label className="label cursor-pointer">
                      <span className="label-text">Show Secret Gates</span>
                      <input 
                        type="checkbox" 
                        className="toggle toggle-primary" 
                        checked={userShowSecrets} 
                        onChange={(e) => setUserShowSecrets(e.target.checked)}
                        disabled={!staticNavTaskData?.display_secrets}
                      />
                    </label>
                  </li>
                  <li>
                    <label className="label cursor-pointer">
                      <span className="label-text">Permanent Annotations</span>
                      <input
                        type="checkbox"
                        className="toggle toggle-primary"
                        checked={permanentAnnotations}
                        onChange={(e) => setPermanentAnnotations(e.target.checked)}
                      />
                    </label>
                  </li>
                </ul>
              </div>
            </div>

            {mode === 'realtime' && staticNavTaskData?.calculation_delay_minutes > 0 && (
              <div className="text-xs text-warning-content bg-warning rounded-md px-2 py-1 mt-2 text-center">
                Live data is delayed by {staticNavTaskData?.calculation_delay_minutes} minute(s).
              </div>
            )}

            {selectedContestant && (
              <div className="flex justify-between items-center mt-2 pt-2 border-t border-base-200 gap-2">
                <span className="text-xs font-bold truncate flex-1" title={`${selectedContestant.team.crew.member1.first_name} ${selectedContestant.team.crew.member1.last_name}`}>
                  Selected: #{selectedContestant.contestant_number} {selectedContestant.team.crew.member1.first_name}                                                    </span>
                <div className="flex-none">
                  <button className="btn btn-xs btn-info mr-1" onClick={() => setShowScoreLog(true)}>Log</button>
                  <button className="btn btn-xs btn-ghost" onClick={() => { setSelectedContestantId(null); setShowScoreLog(false); }}>Clear</button>
                </div>
              </div>
            )}
          </div>

          {!isRankingCollapsed && (
            <>
              {progress.total > 0 && progress.loaded < progress.total && (
                <div className="p-2 border-b border-base-300">
                    <div className="text-xs font-bold">Loading Contestant Data...</div>
                    <progress 
                        className="progress progress-primary w-full" 
                        value={progress.loaded} 
                        max={progress.total}
                    ></progress>
                    <div className="text-xs text-right">{progress.loaded} / {progress.total}</div>
                </div>
              )}

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
            </>
          )}
        </div>

        {selectedContestant ? (
          // Container for TeamPresentation and GateScoreArrowV2
          <div ref={teamPresentationContainerRef} className={`absolute right-4 z-[1000] transition-all duration-300 ${(mode === 'playback' && playbackTimeInfo) ? 'bottom-12' : 'bottom-2'} w-11/12 md:w-3/4 lg:w-1/2 max-w-screen-md`}> {/* Responsive container */}
            <div className="flex items-end gap-4 justify-end">
              <TeamPresentation
                key={selectedContestant.id}
                scale={teamPresentationScale}
                contestant={selectedContestant}
                dangerData={dangerDataByContestant[selectedContestant.id]}
                gateArrowData={gateArrowDataByContestant[selectedContestant.id]}
                score={standings.find(s => s.id === selectedContestant.id)?.score ?? 0}
                navigationTask={staticNavTaskData}
              />
            </div>
          </div>
        ) : (
          contestDetails?.logo && (
            <div className={`absolute right-4 z-[1000] transition-all duration-300 ${(mode === 'playback' && playbackTimeInfo) ? 'bottom-12' : 'bottom-2'}`}>
                <div className="bg-base-100/80 backdrop-blur-sm p-2 rounded-lg shadow-lg">
                    <img src={contestDetails.logo} alt={`${contestDetails.name} logo`} className="max-h-32 max-w-xs" />
                </div>
            </div>
          )
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
  );
}