import React, { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import { useParams, Link, useSearchParams } from 'react-router-dom';

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
import { ChevronUp, ChevronDown, Trophy, Info, Settings, Calendar, Sliders, Activity, PlayCircle, Route } from 'lucide-react';
import { reverse, generatePath } from '../../urls';
import './CompetitionMap.css';
import { NavigationTask } from './types';




export default function CompetitionMapPage() {
  const { contestId, navigationTaskId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const contestIdNum = Number(contestId ?? 632);
  const navigationTaskIdNum = Number(navigationTaskId ?? 2129);

  const initialMode = (searchParams.get('mode') as 'realtime' | 'playback') || 'realtime';
  const initialTimeParam = searchParams.get('time');
  const initialSpeedParam = searchParams.get('speed');
  const autoPlay = searchParams.get('autoplay') === 'true';
  const rankingExpandedParam = searchParams.get('rankingExpanded');

  const initialTime = useMemo(() => {
    if (!initialTimeParam) return null;
    const date = new Date(initialTimeParam);
    return isNaN(date.getTime()) ? null : date;
  }, [initialTimeParam]);

  const initialSpeed = useMemo(() => {
    if (!initialSpeedParam) return 1;
    const speed = parseInt(initialSpeedParam, 10);
    return isNaN(speed) ? 1 : speed;
  }, [initialSpeedParam]);

  const [mode, setMode] = useState<'realtime' | 'playback'>(initialMode);
  const [showFullTrails, setShowFullTrails] = useState(false);
  const [selectedContestantId, setSelectedContestantId] = useState<number | null>(null);
  const [showScoreLog, setShowScoreLog] = useState(false);
  const [userShowBackgroundMap, setUserShowBackgroundMap] = useState(true);
  const [userShowSecrets, setUserShowSecrets] = useState(true);
  const [showPenaltiesOnly, setShowPenaltiesOnly] = useState(false);
  const [hasMapBeenFitted, setHasMapBeenFitted] = useState(false); // New state for initial map fit
  const [isRankingCollapsed, setIsRankingCollapsed] = useState(() => {
    if (rankingExpandedParam === 'true') return false;
    if (rankingExpandedParam === 'false') return true;
    return window.innerWidth < 640;
  });
  const [isInfoModalOpen, setIsInfoModalOpen] = useState(false);
  const [permanentAnnotations, setPermanentAnnotations] = useState(false);
  const [contestDetails, setContestDetails] = useState<any | null>(null);
  const hasAutoEnabledTrailsRef = useRef(false);

  useEffect(() => {
    // Reset auto-enable flag when switching tasks
    hasAutoEnabledTrailsRef.current = false;
  }, [navigationTaskIdNum]);

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
    gateScoresByContestant,
    dangerDataByContestant,
    gateArrowDataByContestant,
    progress,
    wsStatus,
    error: navTaskError,
  } = useCompetitionData(contestIdNum, navigationTaskIdNum, mode, showToast); // Pass showToast

  const selectedIds = useMemo(() => {
    const param = searchParams.get('contestantIds');
    if (param === null) return null;
    if (param === '') return new Set<number>();
    return new Set(param.split(',').filter(s => s !== '').map(Number));
  }, [searchParams]);

  const allSortedContestants = useMemo(() => {
    return Object.values(contestantsById).sort((a, b) => a.id - b.id);
  }, [contestantsById]);

  const sortedContestants = useMemo(() => {
    if (!selectedIds) return allSortedContestants;
    return allSortedContestants.filter(c => selectedIds.has(c.id));
  }, [allSortedContestants, selectedIds]);

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
        // On mobile (< 640px), the component stacks vertically, so the design width is smaller (~600px).
        // On desktop, it's side-by-side (~1000px).
        const isStacked = window.innerWidth < 640;
        const designWidth = isStacked ? 600 : 1000;
        
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

  const previousStaticNavTaskDataRef = useRef<NavigationTask | null>(null); // Add this ref

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

    // Standard scale control for Metric
    const scaleControl = L.control.scale({
        imperial: false,
        metric: true,
        position: 'bottomleft'
    }).addTo(map);

    // Custom Nautical Miles scale
    const NauticalScale = L.Control.extend({
        options: {
            position: 'bottomleft'
        },
        onAdd: function(map: L.Map) {
            const container = L.DomUtil.create('div', 'leaflet-control-scale');
            const inner = L.DomUtil.create('div', 'leaflet-control-scale-line', container);
            inner.style.borderTop = 'none'; // Only show bottom line for this one
            
            const updateScale = () => {
                const width = 100; // px
                const p1 = map.containerPointToLatLng([0, 0]);
                const p2 = map.containerPointToLatLng([width, 0]);
                const meters = p1.distanceTo(p2);
                const nm = meters / 1852;
                
                // Find a nice round number for NM
                let roundNM = 1;
                if (nm > 10) roundNM = 10;
                if (nm > 50) roundNM = 50;
                if (nm < 1) roundNM = 0.5;
                if (nm < 0.5) roundNM = 0.1;
                if (nm < 0.1) roundNM = 0.05;

                const pxPerNM = width / nm;
                const finalWidth = roundNM * pxPerNM;
                
                inner.style.width = Math.round(finalWidth) + 'px';
                inner.innerHTML = roundNM + ' NM';
            };

            map.on('move', updateScale);
            map.on('zoomend', updateScale);
            updateScale();

            return container;
        }
    });

    const nauticalScale = new NauticalScale().addTo(map);
    
    return () => {
        scaleControl.remove();
        nauticalScale.remove();
    };
  }, [mapRef]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (tileLayerRef.current) {
        tileLayerRef.current.remove();
    }

    if (staticNavTaskData?.display_background_map && userShowBackgroundMap) {
        const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            opacity: 0.6
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
  } = usePlayback(mode, positionsByContestant, initialTime, initialSpeed, autoPlay);

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
    if (!staticNavTaskData || hasAutoEnabledTrailsRef.current) return;

    const isAfterFinishTime = currentTime > new Date(staticNavTaskData.finish_time);
    const contestants = Object.values(contestantsById);
    const anyRunning = contestants.some(c => 
      c.contestanttrack?.calculator_started && !c.contestanttrack?.calculator_finished
    );

    if (isAfterFinishTime || (contestants.length > 0 && !anyRunning)) {
      setShowFullTrails(true);
      hasAutoEnabledTrailsRef.current = true;
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
    if (selectedContestantId === id && id !== null) {
        setSelectedContestantId(null);
        setShowScoreLog(false);
    } else {
        setSelectedContestantId(id);
        setShowScoreLog(showLog);
    }
  };

  useMapLayers({
    mapRef,
    navTask: staticNavTaskData,
    contestants: sortedContestants, // Pass the sorted dynamic contestants
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
    showPenaltiesOnly,
  });

  const toggleContestantFilter = (id: number) => {
    const currentIds = selectedIds ? Array.from(selectedIds) : allSortedContestants.map(c => c.id);
    let nextIds;
    if (currentIds.includes(id)) {
        nextIds = currentIds.filter(i => i !== id);
    } else {
        nextIds = [...currentIds, id];
    }
    
    // If all are selected, just remove the param
    if (nextIds.length === allSortedContestants.length) {
        searchParams.delete('contestantIds');
    } else {
        searchParams.set('contestantIds', nextIds.join(','));
    }
    setSearchParams(searchParams);
  };

  const selectAllContestants = () => {
    searchParams.delete('contestantIds');
    setSearchParams(searchParams);
  };

  const selectNoneContestants = () => {
    searchParams.set('contestantIds', ''); 
    setSearchParams(searchParams);
  };



  const standings = useMemo(() => {
    if (!staticNavTaskData) return [] as any[];
    const dir = staticNavTaskData.score_sorting_direction;
    const allContestantsData = sortedContestants;
    const total = allContestantsData.length;
    const startGateName = staticNavTaskData.route.waypoints.find(wp => wp.type === 'sp')?.name;

    const getContestantsWithState = () => {
      if (mode === 'playback') {
        const finishGateName = staticNavTaskData.route.waypoints.find(wp => wp.type === 'fp')?.name;

        return allContestantsData.map((c, index) => { // Updated
          const logsForTime = (scoreLogByContestant[c.id] ?? []).filter(log => new Date(log.time) <= currentTime);
          const hasStarted = startGateName && logsForTime.some(log => log.gate === startGateName);
          const hasFinished = finishGateName && logsForTime.some(log => log.gate === finishGateName);

          let state = 'Waiting...';
          if (hasFinished) {
            state = 'Finished';
          } else if (hasStarted) {
            state = 'Enroute';
          }

          let score: number | string = currentScores[c.id] ?? staticNavTaskData.scorecard.initial_score ?? 0;
          let isNotStarted = false;
          if (!hasStarted && c.finished_by_time) {
              const finishedBy = new Date(c.finished_by_time);
              if (currentTime.getTime() > finishedBy.getTime() && !c.contestanttrack?.calculator_started) {
                  score = 'Not started';
                  isNotStarted = true;
              }
          }

          let countdown = null;
          let expectedBy = null;
          const shouldShowCountdown = !c.adaptive_start || c.has_crossed_starting_line;
          
          if (!hasStarted && !isNotStarted) {
              if (shouldShowCountdown && startGateName && c.gate_times?.[startGateName]) {
                  const startTime = new Date(c.gate_times[startGateName]);
                  const diffSeconds = (startTime.getTime() - currentTime.getTime()) / 1000;
                  if (diffSeconds > 0) {
                      countdown = diffSeconds;
                  }
              } else if (c.adaptive_start && !c.has_crossed_starting_line && c.finished_by_time) {
                  const finishedBy = new Date(c.finished_by_time);
                  expectedBy = finishedBy.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
              }
          }

          // Calculate progress for playback mode
          let progress = undefined;
          const isPoker = staticNavTaskData.scorecard.task_type.includes('poker');
          const isLanding = staticNavTaskData.scorecard.task_type.includes('landing');

          if (isPoker) {
              const cardLogs = logsForTime.filter(l => l.message.includes('Received card'));
              progress = Math.min(100, (cardLogs.length / 5) * 100);
          } else if (isLanding) {
              progress = 0;
          } else if (hasStarted && !hasFinished && staticNavTaskData.route.waypoints.length > 0) {
              const firstWp = staticNavTaskData.route.waypoints[0].name;
              const lastWp = staticNavTaskData.route.waypoints[staticNavTaskData.route.waypoints.length - 1].name;
              const startTimeStr = c.gate_times?.[firstWp];
              const endTimeStr = c.gate_times?.[lastWp];
              
              if (startTimeStr && endTimeStr) {
                  const startTime = new Date(startTimeStr).getTime();
                  const endTime = new Date(endTimeStr).getTime();
                  const currentT = currentTime.getTime();
                  const totalRange = endTime - startTime;
                  if (totalRange > 0) {
                      progress = 100 * (currentT - startTime) / totalRange;
                  }
              }
          }

          const allPos = positionsByContestant[c.id] ?? [];
          const latestPosInTimeline = allPos.filter(p => new Date(p.time) <= currentTime).pop();
          const isReceivingData = (
              latestPosInTimeline && (currentTime.getTime() - new Date(latestPosInTimeline.time).getTime() < 30000)
          );

          return {
            id: c.id,
            name: `#${c.contestant_number} ${c.team?.crew?.member1?.first_name ?? ''} ${c.team?.crew?.member1?.last_name ?? ''}`,
            score: score,
            state: state,
            color: `hsl(${(index / total) * 360}, 70%, 50%)`,
            countdown: countdown,
            expectedBy: expectedBy,
            is_active_flight: hasStarted && !hasFinished,
            is_receiving_data: isReceivingData,
            progress: progress,
          };
        });
      }

      return allContestantsData.map((c, index) => {
        const state = c.contestanttrack?.current_state ?? 'Waiting...';
        const hasStarted = c.contestanttrack?.passed_starting_gate;
        const calculatorStarted = c.contestanttrack?.calculator_started;
        const calculatorFinished = c.contestanttrack?.calculator_finished;

        let score: number | string = c.contestanttrack?.score ?? 0;
        let isNotStarted = false;
        if (!hasStarted && c.finished_by_time) {
            const finishedBy = new Date(c.finished_by_time);
            if (currentTime.getTime() > finishedBy.getTime() && !c.contestanttrack?.calculator_started) {
                score = 'Not started';
                isNotStarted = true;
            }
        }

        let countdown = null;
        let expectedBy = null;
        const shouldShowCountdown = !c.adaptive_start || c.has_crossed_starting_line;

        if (!hasStarted && !isNotStarted) {
            if (shouldShowCountdown && startGateName && c.gate_times?.[startGateName]) {
                const startTime = new Date(c.gate_times[startGateName]);
                const diffSeconds = (startTime.getTime() - currentTime.getTime()) / 1000;
                if (diffSeconds > 0) {
                    countdown = diffSeconds;
                }
            } else if (c.adaptive_start && !c.has_crossed_starting_line && c.finished_by_time) {
                const finishedBy = new Date(c.finished_by_time);
                expectedBy = finishedBy.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
            }
        }

        // Active flight: Calculator running but not finished
        const isActiveFlight = calculatorStarted && !calculatorFinished;
        
        // Receiving data: Last position arrived in the last 30 seconds (local time)
        const lastSeen = c.last_position_received_at ?? c.contestanttrack?.last_position_received_at;
        const isReceivingData = lastSeen && (Date.now() - lastSeen < 30000);

        return {
            id: c.id,
            name: `#${c.contestant_number} ${c.team?.crew?.member1?.first_name ?? ''} ${c.team?.crew?.member1?.last_name ?? ''}`,
            score: score,
            state: state,
            color: `hsl(${(index / total) * 360}, 70%, 50%)`,
            countdown: countdown,
            expectedBy: expectedBy,
            is_active_flight: isActiveFlight,
            is_receiving_data: isReceivingData,
            progress: c.progress ?? c.contestanttrack?.progress,
        };
      });
    };

    const allContestants = getContestantsWithState();
    const active = allContestants.filter(c => c.state !== 'Waiting...');
    const waiting = allContestants.filter(c => c.state === 'Waiting...');
    const sortFn = (a: { score: number | string }, b: { score: number | string }) => {
        const scoreA = typeof a.score === 'number' ? a.score : (dir === 'asc' ? Infinity : -Infinity);
        const scoreB = typeof b.score === 'number' ? b.score : (dir === 'asc' ? Infinity : -Infinity);
        return dir === 'asc' ? scoreA - scoreB : scoreB - scoreA;
    };
    active.sort(sortFn);
    waiting.sort(sortFn);
    return [...active, ...waiting];
  }, [staticNavTaskData, sortedContestants, mode, currentScores, currentTime, scoreLogByContestant]);



  const firstWaitingIndex = standings.findIndex(s => s.state === 'Waiting...');

  // Collapse ranking on mobile when a contestant is selected to show the map/details
  useEffect(() => {
    if (selectedContestantId !== null && window.innerWidth < 640) {
      setIsRankingCollapsed(true);
    }
  }, [selectedContestantId]);

  const filteredScoreLog = useMemo(() => {
    if (!selectedContestantId || !scoreLogByContestant[selectedContestantId]) return [];
    
    const showSecrets = !!(staticNavTaskData?.display_secrets && userShowSecrets);
    const logEntries = scoreLogByContestant[selectedContestantId];

    return logEntries.filter(log => {
      // 1. Time filtering for playback
      if (mode === 'playback' && new Date(log.time) > currentTime) {
        return false;
      }

      // 2. Secret gate filtering
      if (!showSecrets && staticNavTaskData) {
        const waypoint = staticNavTaskData.route.waypoints.find(wp => wp.name === log.gate);
        if (waypoint && waypoint.type === 'secret') {
          return false;
        }
      }

      return true;
    });
  }, [selectedContestantId, scoreLogByContestant, mode, currentTime, staticNavTaskData, userShowSecrets]);

   if (navTaskError?.status === 404) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-base-200 p-4 text-center">
        <div className="max-w-md bg-base-100 p-8 rounded-xl shadow-2xl border border-base-300">
          <h1 className="text-6xl font-black text-error mb-4">404</h1>
          <h2 className="text-2xl font-bold mb-4">Navigation Task Not Found</h2>
          <p className="text-base-content/70 mb-8">
            The navigation task you are looking for doesn't exist or has been removed. Or maybe you just need to log in?
          </p>
          <div className="flex flex-col gap-2">
            <Link to="/" className="btn btn-primary">Go to Dashboard</Link>
            {contestId && (
              <Link to={`/mission-dashboard/${contestId}`} className="btn btn-ghost">Back to Contest</Link>
            )}
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="flex flex-col h-full overflow-hidden">
      <TaskInfoModal isOpen={isInfoModalOpen} onClose={() => setIsInfoModalOpen(false)} />
      <ToastContainer toasts={toasts} removeToast={removeToast} /> {/* Render ToastContainer */}
      <div className="flex-1 relative">
        <div id="map-container" className="h-full w-full" />
        <Disclaimer />
        <ProhibitedRenderer map={mapRef.current} navTask={staticNavTaskData} />
        <RouteRenderer
          map={mapRef.current}
          route={staticNavTaskData?.route ?? null}
          taskCatalogueTargets={staticNavTaskData?.task_catalogue_targets ?? []}
          taskType={staticNavTaskData?.scorecard?.task_type ?? null}
          navTaskDisplaySecrets={staticNavTaskData?.display_secrets ?? false}
          displaySecrets={userShowSecrets}
          contestants={contestantsById}
          selectedContestantId={selectedContestantId}
          isInitialLoad={!hasMapBeenFitted}
          onMapFit={setHasMapBeenFitted}
        />

        <div className="absolute top-2 right-2 sm:top-4 sm:right-4 z-[1100]">
          <ClockDisplay time={currentTime} timeZone={staticNavTaskData?.time_zone} />
        </div>
        
        {mode === 'realtime' && wsStatus === 'disconnected' && (
            <div className="absolute top-2 left-1/2 -translate-x-1/2 z-[1100] bg-error text-error-content p-2 rounded-lg shadow-md text-center max-w-xs">
                <h3 className="font-bold text-base">Offline</h3>
                <p className="text-sm">Connection lost. Attempting to reconnect...</p>
            </div>
        )}

        {/* The toast display will now be placed relative to this flex-1 relative container */}


        <div className="ranking-container absolute top-2 left-2 sm:top-4 sm:left-4 z-[1100] bg-base-100/80 backdrop-blur-sm border border-base-300 rounded-lg shadow-lg w-56 sm:w-80 md:w-96 max-w-[calc(100vw-2rem)]">
          <div className="p-1 sm:p-2 border-b border-base-300">
            <div className="flex justify-between items-center">
              <h2 className="font-bold text-sm sm:text-lg truncate" title={staticNavTaskData?.name}>{staticNavTaskData?.name ?? 'Loading...'}</h2>
              <button onClick={() => setIsRankingCollapsed(!isRankingCollapsed)} className="btn btn-ghost btn-xs sm:btn-sm btn-square">
                {isRankingCollapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
              </button>
            </div>


            <div className="flex items-center flex-wrap gap-0.5 sm:gap-2 mt-1 sm:mt-2">
                {/* Settings Dropdown */}
                <div className="dropdown">
                  <div tabIndex={0} role="button" className="btn btn-xs btn-outline px-1 sm:px-2 gap-1" title="Settings">
                    <Sliders size={12} />
                    <span className="hidden sm:inline">Settings</span>
                  </div>
                  <ul tabIndex={0} className="dropdown-content z-[50] menu p-2 shadow bg-base-100 rounded-box w-64 max-h-[65vh] overflow-y-auto flex-nowrap">
                    <li>
                      <label className="label cursor-pointer py-1">
                        <span className="label-text text-xs text-left">Show Background Map</span>
                        <input 
                          type="checkbox" 
                          className="toggle toggle-primary toggle-xs" 
                          checked={userShowBackgroundMap} 
                          onChange={(e) => setUserShowBackgroundMap(e.target.checked)}
                          disabled={!staticNavTaskData?.display_background_map}
                        />
                      </label>
                    </li>
                    <li>
                      <label className="label cursor-pointer py-1">
                        <span className="label-text text-xs text-left">Show Secret Gates</span>
                        <input 
                          type="checkbox" 
                          className="toggle toggle-primary toggle-xs" 
                          checked={userShowSecrets} 
                          onChange={(e) => setUserShowSecrets(e.target.checked)}
                          disabled={!staticNavTaskData?.display_secrets}
                        />
                      </label>
                    </li>
                    <li>
                      <label className="label cursor-pointer py-1">
                        <span className="label-text text-xs text-left">Show Penalties Only</span>
                        <input
                          type="checkbox"
                          className="toggle toggle-primary toggle-xs"
                          checked={showPenaltiesOnly}
                          onChange={(e) => setShowPenaltiesOnly(e.target.checked)}
                        />
                      </label>
                    </li>
                    <li>
                      <label className="label cursor-pointer py-1">
                        <span className="label-text text-xs text-left">Permanent Annotations</span>
                        <input
                          type="checkbox"
                          className="toggle toggle-primary toggle-xs"
                          checked={permanentAnnotations}
                          onChange={(e) => setPermanentAnnotations(e.target.checked)}
                        />
                      </label>
                    </li>
                    <div className="divider my-1"></div>
                    <div className="px-2 pb-1 flex justify-between items-center">
                        <span className="text-[10px] font-bold uppercase opacity-50">Filter Contestants</span>
                        <div className="flex gap-2">
                            <button onClick={selectAllContestants} className="text-[10px] link">All</button>
                            <button onClick={selectNoneContestants} className="text-[10px] link">None</button>
                        </div>
                    </div>
                    <div className="px-1">
                        {allSortedContestants.map(c => (
                            <li key={c.id}>
                                <label className="label cursor-pointer py-0.5 justify-start gap-2">
                                    <input 
                                        type="checkbox" 
                                        className="checkbox checkbox-primary checkbox-xs" 
                                        checked={!selectedIds || selectedIds.has(c.id)}
                                        onChange={() => toggleContestantFilter(c.id)}
                                    />
                                    <span className="label-text text-[10px] truncate">
                                        #{c.contestant_number} {c.team?.crew?.member1?.first_name} {c.team?.crew?.member1?.last_name}
                                    </span>
                                </label>
                            </li>
                        ))}
                    </div>
                  </ul>
                </div>

                <button 
                  className={`btn btn-xs ${mode === 'realtime' ? 'btn-primary' : 'btn-outline'} px-1 sm:px-2 gap-1`}
                  onClick={() => { if (mode !== 'realtime') { setMode('realtime'); setSelectedContestantId(null); setPlaybackTime(new Date()); } }}
                  title="Realtime"
                >
                  <Activity size={12} />
                  <span className="hidden sm:inline">Realtime</span>
                </button>
                <button 
                  className={`btn btn-xs ${mode === 'playback' ? 'btn-primary' : 'btn-outline'} px-1 sm:px-2 gap-1`}
                  onClick={() => { if (mode !== 'playback') { setMode('playback'); setSelectedContestantId(null); } }}
                  title="Playback"
                >
                  <PlayCircle size={12} />
                  <span className="hidden sm:inline">Playback</span>
                </button>

                <button 
                  className={`btn btn-xs ${showFullTrails ? 'btn-primary' : 'btn-outline'} px-1 sm:px-2 gap-1`}
                  onClick={() => {
                    setShowFullTrails(!showFullTrails);
                    hasAutoEnabledTrailsRef.current = true;
                  }}
                  title="Full Trails"
                >
                  <Route size={12} />
                  <span className="full-trails-text hidden sm:inline">Full Trails</span>
                </button>

                <button onClick={() => setIsInfoModalOpen(true)} className="btn btn-xs btn-outline px-1 sm:px-2 gap-1" title="Task Info">
                  <Info size={12} />
                  <span className="hidden sm:inline">Task Info</span>
                </button>
                <Link to={generatePath('MISSION_DASHBOARD_DETAIL', { contestId: contestIdNum })} className="btn btn-xs btn-outline px-1 sm:px-2 gap-1" title="Contest">
                  <Trophy size={12} />
                  <span className="hidden sm:inline">Contest</span>
                </Link>
                {(staticNavTaskData?.user_has_change_permission || document.configuration.is_superuser)&& (
                  <a href={reverse("navigationtask_detail", navigationTaskId)} className="btn btn-xs btn-outline px-1 sm:px-2 gap-1" title="Manage">
                    <Settings size={12} />
                    <span className="hidden sm:inline">Manage</span>
                  </a>
                )}
                {staticNavTaskData?.allow_self_management && (
                  <Link to={`/schedule-flight?contestId=${contestIdNum}&navigationTaskId=${navigationTaskIdNum}`} className="btn btn-xs btn-outline px-1 sm:px-2 gap-1" title="Schedule">
                    <Calendar size={12} />
                    <span className="hidden sm:inline">Schedule</span>
                  </Link>
                )}
            </div>

            {mode === 'realtime' && staticNavTaskData?.calculation_delay_minutes !== undefined && staticNavTaskData.calculation_delay_minutes > 0 && (
              <div className="text-xs text-warning-content bg-warning rounded-md px-2 py-1 mt-2 text-center">
                Live data is delayed by {staticNavTaskData.calculation_delay_minutes} minute(s).
              </div>
            )}

            {selectedContestant && (
              <div className="flex justify-between items-center mt-2 pt-2 border-t border-base-200 gap-2">
                <span className="text-xs font-bold truncate flex-1" title={`${selectedContestant?.team?.crew?.member1?.first_name ?? ''} ${selectedContestant?.team?.crew?.member1?.last_name ?? ''}`}>
                  Selected: #{selectedContestant?.contestant_number} {selectedContestant?.team?.crew?.member1?.first_name ?? ''}
                </span>
                <div className="flex-none">
                  <button className="btn btn-xs btn-info mr-1" onClick={() => { setShowScoreLog(!showScoreLog); setIsRankingCollapsed(false); }}>{showScoreLog ? 'Rank' : 'Log'}</button>
                  <button className="btn btn-xs btn-ghost" onClick={() => { setSelectedContestantId(null); setShowScoreLog(false); if (window.innerWidth < 640) setIsRankingCollapsed(false); }}>Clear</button>
                </div>
              </div>
            )}
          </div>

          {!isRankingCollapsed && (
            <>
              {progress.total > 0 && progress.loaded < progress.total && (
                <div className="p-2 border-b border-base-300">
                    <div className="text-xs font-bold">{progress.message || 'Loading Contestant Data...'}</div>
                    <progress 
                        className="progress progress-primary w-full" 
                        value={progress.loaded} 
                        max={progress.total}
                    ></progress>
                    <div className="text-xs text-right">{progress.loaded}%</div>
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
                  selectedId={selectedContestantId}
                  dividerIndex={firstWaitingIndex}
                  onRowClick={(id) => {
                    if (selectedContestantId === id) {
                        setSelectedContestantId(null);
                    } else {
                        setSelectedContestantId(id);
                    }
                    setShowScoreLog(false);
                  }}
                />
              )}
            </>
          )}
        </div>

        {selectedContestant ? (
          // Container for TeamPresentation and GateScoreArrowV2
          <div ref={teamPresentationContainerRef} className={`team-presentation-container absolute right-4 z-[1100] transition-all duration-300 ${(mode === 'playback' && playbackTimeInfo) ? 'bottom-24 sm:bottom-20' : 'bottom-2'} w-11/12 md:w-3/4 lg:w-2/3 max-w-5xl pointer-events-none`}> {/* Responsive container */}
            <div className="flex items-end gap-4 justify-end pointer-events-none">
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
            <div className={`absolute right-4 z-[1100] transition-all duration-300 ${(mode === 'playback' && playbackTimeInfo) ? 'bottom-28 sm:bottom-24' : 'bottom-5'} pointer-events-none`}>
                <div className="bg-base-100/80 backdrop-blur-sm p-1 sm:p-2 rounded-lg shadow-lg pointer-events-auto">
                    <img src={contestDetails.logo} alt={`${contestDetails.name} logo`} className="max-h-16 sm:max-h-32 max-w-[120px] sm:max-w-xs object-contain" />
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