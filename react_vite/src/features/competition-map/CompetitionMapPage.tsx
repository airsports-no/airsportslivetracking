import React, { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import { useParams, Link, useSearchParams } from 'react-router-dom';

import useMapInit from '../route-editor/components/map/useMapInit';
import { useCompetitionData } from './hooks/useCompetitionData';
import { usePlayback } from './hooks/usePlayback';
import { useMapLayers } from './hooks/useMapLayers';
import { usePhotoLayers, TargetPhoto } from './hooks/usePhotoLayers';
import { useMapAppearance, MapAppearance } from './hooks/useMapAppearance';
import { clampToSpan, flightSpan } from './utils/replaySpan';
import { useToast } from './hooks/useToast'; // Import useToast
import { fetchContestDetails, fetchPhotoObservations, fetchPhotos } from './api';

import ProhibitedRenderer from "./components/track-renderers/ProhibitedRenderer";
import RouteRenderer from "./components/track-renderers/RouteRenderer";
import Disclaimer from './components/Disclaimer';
import SidePanel, { PanelTab } from './components/hud/SidePanel';
import RankingList from './components/hud/RankingList';
import NavLog from './components/hud/NavLog';
import FlightTimeline from './components/hud/FlightTimeline';
import FollowBar from './components/hud/FollowBar';
import ReplayBar, { ReplayEvent } from './components/hud/ReplayBar';
import TaskInfoModal from './TaskInfoModal';
import { Trophy, Info, Settings, Calendar, Sliders, Route } from 'lucide-react';
import { generatePath } from '../../urls';
import './CompetitionMap.css';
import './components/hud/hud.css';
import { NavigationTask, PhotoObservation, ScoreAnnotation, ScoreLogEntry } from './types';

// From this width the page is treated as an event display: following someone folds the panel (FollowBar grows too).
const BIG_SCREEN_WIDTH = 1600;

/** The contestant a contestantIds parameter names when it names exactly one, otherwise null. */
function singleContestantId(param: string | null): number | null {
  const ids = (param ?? '').split(',').filter(s => s !== '').map(Number);
  return ids.length === 1 && Number.isFinite(ids[0]) ? ids[0] : null;
}

// Stable empty values: a fresh [] each render would make the photo layers redraw on every tick and close hover tooltips
const NO_PHOTOS: TargetPhoto[] = [];
const NO_OBSERVATIONS: PhotoObservation[] = [];




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
  // A link to one contestant's flight (contestantIds with a single id, as the apps' "View your flight" sends) opens
  // with that contestant selected, so their team panel and gate countdown show at once; so does a later change of the
  // link to another single contestant (the page is not reloaded when only the query changes).
  const contestantIdsParam = searchParams.get('contestantIds');
  const [selectedContestantId, setSelectedContestantId] = useState<number | null>(() => singleContestantId(contestantIdsParam));
  const [selectionParam, setSelectionParam] = useState(contestantIdsParam);
  if (contestantIdsParam !== selectionParam) {
    setSelectionParam(contestantIdsParam);
    const single = singleContestantId(contestantIdsParam);
    if (single !== null) setSelectedContestantId(single);
  }
  // What the side panel shows while a contestant is selected: the ranking, or their navigation log.
  // A replay link to one contestant opens on their log.
  const [panelTab, setPanelTab] = useState<PanelTab>(() => (selectedContestantId !== null && initialMode === 'playback' ? 'log' : 'ranking'));
  // The navigation log entry last jumped to, highlighted in the log.
  const [activeLogId, setActiveLogId] = useState<number | null>(null);
  const [userShowBackgroundMap, setUserShowBackgroundMap] = useState(true);
  const [userShowSecrets, setUserShowSecrets] = useState(true);
  const [showPenaltiesOnly, setShowPenaltiesOnly] = useState(false);
  const [hasMapBeenFitted, setHasMapBeenFitted] = useState(false); // New state for initial map fit
  const [isRankingCollapsed, setIsRankingCollapsed] = useState(() => {
    if (rankingExpandedParam === 'true') return false;
    if (rankingExpandedParam === 'false') return true;
    // A phone, upright or on its side, starts with the map in view; so does a big screen opened to follow one contestant.
    if (window.innerWidth >= BIG_SCREEN_WIDTH && selectedContestantId !== null && initialMode === 'realtime') return true;
    return window.innerWidth < 640 || window.innerHeight < 500;
  });
  const [isInfoModalOpen, setIsInfoModalOpen] = useState(false);
  const { appearance, setAppearance, resolved: hudTheme } = useMapAppearance();
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




    const { toasts, showToast, removeToast, ToastContainer } = useToast(); // Initialize toast hook


  const {
    staticNavTaskData, // Renamed from navTask
    contestantsById, // New, dynamic map of contestants
    positionsByContestant,
    annotationsByContestant,
    photoObservationsByContestant,
    setPhotoObservationsByContestant,
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

  // The three ways the map is used: an overview of everyone, following one contestant while they fly, and a debrief
  // of one contestant's flight (in replay, or live once their flight has been scored to the end).
  const view: 'overview' | 'follow' | 'debrief' = !selectedContestant
    ? 'overview'
    : mode === 'playback' || selectedContestant.contestanttrack?.calculator_finished ? 'debrief' : 'follow';


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

  
  // A replay of one contestant spans their own flight, unless the viewer asks for the whole day.
  const [replayWholeDay, setReplayWholeDay] = useState(false);
  const ownFlightSpan = useMemo(
    () => (selectedContestantId !== null ? flightSpan(positionsByContestant[selectedContestantId]) : null),
    [selectedContestantId, positionsByContestant],
  );
  const {
    playbackSpeed,
    setPlaybackSpeed,
    isPlaying,
    setIsPlaying,
    playbackTime,
    setPlaybackTime,
    playbackTimeInfo
  } = usePlayback(mode, positionsByContestant, initialTime, initialSpeed, autoPlay, replayWholeDay ? null : ownFlightSpan);

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

  // When the replay's span changes (another contestant, or back from the whole day), its time moves inside it.
  useEffect(() => {
    if (mode !== 'playback' || !playbackTimeInfo) return;
    const clamped = clampToSpan(playbackTime, playbackTimeInfo);
    if (clamped !== playbackTime) setPlaybackTime(clamped);
  }, [mode, playbackTimeInfo, playbackTime, setPlaybackTime]);

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

  /**
   * Selects a contestant (or clears the selection when they are selected already). A finished flight opens on its
   * navigation log, for the debrief; a flight in progress keeps the ranking in the panel while the follow bar shows them.
   */
  const selectContestant = (id: number | null, showLog = false) => {
    setActiveLogId(null);
    if (id === null || selectedContestantId === id) {
      setSelectedContestantId(null);
      setPanelTab('ranking');
      return;
    }
    setSelectedContestantId(id);
    const finished = !!contestantsById[id]?.contestanttrack?.calculator_finished;
    setPanelTab(showLog || mode === 'playback' || finished ? 'log' : 'ranking');
    // On a big screen (the event display), following someone live gives the map and the follow bar the whole width;
    // the panel folds to its rail and comes back with one click.
    if (!finished && mode === 'realtime' && window.innerWidth >= BIG_SCREEN_WIDTH) setIsRankingCollapsed(true);
  };
  const handleContestantSelect = (id: number | null, showLog: boolean) => selectContestant(id, showLog);

  const { openAnnotation } = useMapLayers({
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

  // Observation photo targets (task level, independent of any selected contestant) and the selected contestant's
  // registered observations. Both reveal where the targets are, so both follow the same rule as secret gates: the
  // task must display secrets and the viewer's own "show secrets" toggle must be on.
  const photosVisible = !!(staticNavTaskData?.display_secrets && userShowSecrets);
  const [fetchedPhotos, setFetchedPhotos] = useState<TargetPhoto[]>(NO_PHOTOS);
  useEffect(() => {
    if (!photosVisible) return;
    let cancelled = false;
    fetchPhotos(contestIdNum, navigationTaskIdNum, undefined, 'observation')
      .then((photos) => { if (!cancelled) setFetchedPhotos(photos); })
      .catch((e) => console.error('Failed to fetch observation photos', e));
    return () => { cancelled = true; };
  }, [photosVisible, contestIdNum, navigationTaskIdNum]);
  const targetPhotos = photosVisible ? fetchedPhotos : NO_PHOTOS;

  useEffect(() => {
    if (!photosVisible || !selectedContestantId) return;
    let cancelled = false;
    fetchPhotoObservations(selectedContestantId)
      .then((observations) => {
        if (!cancelled) setPhotoObservationsByContestant((prev) => ({ ...prev, [selectedContestantId]: observations }));
      })
      .catch((e) => console.error('Failed to fetch photo observations', e));
    return () => { cancelled = true; };
  }, [photosVisible, selectedContestantId, setPhotoObservationsByContestant]);

  const visibleObservations = useMemo(() => {
    if (!photosVisible || !selectedContestantId) return NO_OBSERVATIONS;
    return (photoObservationsByContestant[selectedContestantId] ?? NO_OBSERVATIONS).filter(
      (o) => mode === 'realtime' || new Date(o.time) <= currentTime,
    );
  }, [photosVisible, photoObservationsByContestant, selectedContestantId, mode, currentTime]);

  usePhotoLayers({ mapRef, photos: targetPhotos, observations: visibleObservations, visible: photosVisible });

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
          // The map's log only has entries with points, so a crossing without a timing result (an adaptive start, a
          // gate without a time check) is only in the annotations: either counts.
          const annotationsForTime = (annotationsByContestant[c.id] ?? []).filter(a => new Date(a.time) <= currentTime);
          const crossed = (gate?: string) => !!gate && (
            logsForTime.some(log => log.gate === gate)
            || annotationsForTime.some(a => a.gate === gate && /passing gate|adaptive start set/i.test(a.message)));
          const hasStarted = crossed(startGateName);
          const hasFinished = crossed(finishGateName);

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
  }, [staticNavTaskData, sortedContestants, mode, currentScores, currentTime, scoreLogByContestant, annotationsByContestant]);



  const firstWaitingIndex = standings.findIndex(s => s.state === 'Waiting...');

  // Collapse ranking on mobile when a contestant is selected to show the map/details
  useEffect(() => {
    if (selectedContestantId !== null && window.innerWidth < 640) {
      setIsRankingCollapsed(true);
    }
  }, [selectedContestantId]);

  // The selected contestant's log, without the gates the viewer may not see (secret and unknown-leg gates).
  const visibleLogEntries = useMemo<ScoreLogEntry[]>(() => {
    if (!selectedContestantId || !scoreLogByContestant[selectedContestantId]) return [];
    const showSecrets = !!(staticNavTaskData?.display_secrets && userShowSecrets);
    return scoreLogByContestant[selectedContestantId].filter(log => {
      // A 'ul' gate is scored normally and logged under its real name, but its position must stay hidden from the
      // contestant just like a secret gate until secrets are shown.
      if (!showSecrets && staticNavTaskData) {
        const waypoint = staticNavTaskData.route.waypoints.find(wp => wp.name === log.gate);
        if (waypoint && (waypoint.type === 'secret' || waypoint.type === 'ul')) return false;
      }
      return true;
    });
  }, [selectedContestantId, scoreLogByContestant, staticNavTaskData, userShowSecrets]);

  const pointsArePenalties = staticNavTaskData?.score_sorting_direction === 'asc';

  // Log entries with a place on the map (an annotation): those a click can show.
  const annotationByLogId = useMemo(() => {
    const byLog = new Map<number, { id: number; latitude: number; longitude: number }>();
    if (!selectedContestantId) return byLog;
    for (const ann of annotationsByContestant[selectedContestantId] ?? []) {
      if (ann.score_log_entry) byLog.set(ann.score_log_entry, ann);
    }
    return byLog;
  }, [selectedContestantId, annotationsByContestant]);
  const locatableLogIds = useMemo(() => new Set(annotationByLogId.keys()), [annotationByLogId]);

  const replayEvents = useMemo<ReplayEvent[]>(() => visibleLogEntries.map(log => ({
    id: log.id,
    time: new Date(log.time),
    label: `${log.gate}: ${log.message}`,
    penalty: pointsArePenalties ? log.points > 0 : log.points < 0,
  })), [visibleLogEntries, pointsArePenalties]);

  // A replay time to go to once the replay has started (switching to replay first sets it to the start).
  const pendingSeekRef = useRef<Date | null>(null);
  useEffect(() => {
    if (mode === 'playback' && playbackTimeInfo && pendingSeekRef.current) {
      const seek = pendingSeekRef.current;
      pendingSeekRef.current = null;
      setPlaybackTime(seek);
    }
  }, [mode, playbackTimeInfo, setPlaybackTime]);

  /**
   * Shows where a log entry happened: the map moves to its annotation and opens it. In a debrief the replay also goes
   * to that moment (switching to replay first if needed), so the flight can be played on from there.
   */
  const jumpToLogEntry = (entry: ScoreLogEntry) => {
    setActiveLogId(entry.id);
    showMoment(annotationByLogId.get(entry.id), entry.time);
  };

  /** The same for an annotation without a log entry the map has (a crossing without a time check, a miss). */
  const jumpToAnnotation = (ann: ScoreAnnotation) => {
    setActiveLogId(ann.score_log_entry);
    showMoment(ann, ann.time);
  };

  const showMoment = (ann: { id: number; latitude: number; longitude: number } | undefined, time: string) => {
    const map = mapRef.current;
    if (ann && map) {
      map.flyTo([ann.latitude, ann.longitude], Math.max(map.getZoom(), 12), { duration: 0.6 });
      openAnnotation(ann.id);
    }
    if (view !== 'debrief') return;
    // At the entry's own time: its annotation shows (annotations appear once their time has come) and opens.
    const target = new Date(time);
    if (mode === 'playback') {
      setPlaybackTime(target);
    } else {
      pendingSeekRef.current = target;
      setMode('playback');
    }
  };

  const changeMode = (next: 'realtime' | 'playback') => {
    if (next === mode) return;
    setMode(next);
    if (next === 'realtime') setPlaybackTime(new Date());
    // A replay of the selected contestant is a debrief: their log. Back to live, the log stays for a finished flight.
    if (selectedContestant) setPanelTab(next === 'playback' || selectedContestant.contestanttrack?.calculator_finished ? 'log' : 'ranking');
  };

  // The map fills what the panel and the bottom bar leave; Leaflet must be told when that changes.
  useEffect(() => {
    const map = mapRef.current;
    const element = document.getElementById('map-container');
    if (!map || !element) return;
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(element);
    return () => observer.disconnect();
  }, [mapRef]);

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
  const selectedName = selectedContestant
    ? `#${selectedContestant.contestant_number} ${selectedContestant.team?.crew?.member1?.first_name ?? ''}`.trim()
    : null;
  const selectedStanding = selectedContestant ? standings.findIndex(r => r.id === selectedContestant.id) : -1;
  const startedCount = firstWaitingIndex === -1 ? standings.length : firstWaitingIndex;

  const toolbar = (
    <>
          {/* Settings Dropdown */}
          <div className="dropdown">
            <div tabIndex={0} role="button" className="hud-button" title="Map settings" aria-label="Map settings">
              <Sliders size={16} />
            </div>
            <ul tabIndex={0} className="dropdown-content hud-theme z-[1200] menu p-2 shadow-xl border border-base-300 rounded-box w-64 max-h-[65vh] overflow-y-auto flex-nowrap">
              <li className="menu-title px-2 pb-1 pt-0.5">
                <span className="text-xs font-normal opacity-70">Appearance</span>
              </li>
              <li className="pb-1">
                <div className="join w-full p-0 hover:bg-transparent" role="group" aria-label="Appearance">
                  {([['device', 'Device'], ['light', 'Light'], ['dark', 'Dark']] as [MapAppearance, string][]).map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      className={`join-item btn btn-xs flex-1 ${appearance === value ? 'btn-primary' : 'btn-ghost border-base-300'}`}
                      aria-pressed={appearance === value}
                      title={value === 'device' ? "Follow this device's light or dark mode" : undefined}
                      onClick={() => setAppearance(value)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </li>
              <div className="divider my-1"></div>
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
        className="hud-button"
        aria-pressed={showFullTrails}
        onClick={() => {
          setShowFullTrails(!showFullTrails);
          hasAutoEnabledTrailsRef.current = true;
        }}
        title="Show the whole track of every contestant"
        aria-label="Full trails"
      >
        <Route size={16} />
      </button>
      <button onClick={() => setIsInfoModalOpen(true)} className="hud-button" title="Task information" aria-label="Task information">
        <Info size={16} />
      </button>
      <Link to={generatePath('MISSION_DASHBOARD_DETAIL', { contestId: contestIdNum })} className="hud-button" title="Contest results" aria-label="Contest results">
        <Trophy size={16} />
      </Link>
      {(staticNavTaskData?.user_has_change_permission || document.configuration.is_superuser) && (
        <Link to={generatePath('NAVIGATION_TASK_DETAIL', { contestId: contestIdNum, navigationTaskId: navigationTaskIdNum })} className="hud-button" title="Manage the task" aria-label="Manage the task">
          <Settings size={16} />
        </Link>
      )}
      {staticNavTaskData?.allow_self_management && (
        <Link to={`/schedule-flight?contestId=${contestIdNum}&navigationTaskId=${navigationTaskIdNum}`} className="hud-button" title="Book a flight" aria-label="Book a flight">
          <Calendar size={16} />
        </Link>
      )}
    </>
  );

  return (
    // data-hud picks the panel's light or dark tokens (components/hud/hud.css) for everything inside, the map's labels too.
    <div className="flex flex-col sm:flex-row h-full overflow-hidden" data-hud={hudTheme}>
      <TaskInfoModal isOpen={isInfoModalOpen} onClose={() => setIsInfoModalOpen(false)} />
      <ToastContainer toasts={toasts} removeToast={removeToast} />

      <SidePanel
        title={staticNavTaskData?.name ?? 'Loading the task'}
        time={currentTime}
        timeZone={staticNavTaskData?.time_zone}
        mode={mode}
        onModeChange={changeMode}
        collapsed={isRankingCollapsed}
        onToggleCollapsed={() => setIsRankingCollapsed(c => !c)}
        toolbar={toolbar}
        notice={mode === 'realtime' && (staticNavTaskData?.calculation_delay_minutes ?? 0) > 0 ? (
          <p className="text-xs rounded-md px-2 py-1" style={{ background: 'var(--hud-raised)', color: 'var(--hud-warn)' }}>
            Live data is {staticNavTaskData!.calculation_delay_minutes} min behind, as the organizer has set.
          </p>
        ) : undefined}
        selectedName={selectedName}
        tab={panelTab}
        onTabChange={setPanelTab}
        onClearSelection={() => selectContestant(null)}
        footer={
          <div className="flex items-end justify-between gap-3">
            {contestDetails?.logo ? (
              <img src={contestDetails.logo} alt={`${contestDetails.name} logo`} className="max-h-16 max-w-[11rem] object-contain" />
            ) : <span />}
            <Disclaimer className="hud-label hover:underline flex-none" />
          </div>
        }
      >
        {progress.total > 0 && progress.loaded < progress.total && (
          <div className="px-4 py-2">
            <div className="hud-label">{progress.message || 'Loading the contestants'}</div>
            <div className="h-1 mt-1 rounded-full overflow-hidden" style={{ background: 'var(--hud-raised)' }}>
              <div className="h-full" style={{ width: `${progress.loaded}%`, background: 'var(--hud-accent)' }} />
            </div>
          </div>
        )}
        {selectedContestant && panelTab === 'log' ? (
          <NavLog
            entries={visibleLogEntries}
            // A replay lists the whole flight, what is still ahead dimmed, so any entry can be jumped to.
            dimAfter={mode === 'playback' ? currentTime : undefined}
            timeZone={staticNavTaskData?.time_zone}
            pointsArePenalties={pointsArePenalties}
            activeId={activeLogId}
            locatableIds={locatableLogIds}
            onSelect={jumpToLogEntry}
          />
        ) : selectedContestant && staticNavTaskData ? (
          // Following someone: the ranking (only as tall as its rows) with their flight under it, so the panel shows both
          // where they stand and how the flight is going. On a phone the panel is too small for both: ranking only.
          <div className="flex flex-col h-full">
            <div className="flex-none max-h-[45%] sm:max-h-[40%] overflow-y-auto hud-scroll">
              <RankingList
                rows={standings}
                selectedId={selectedContestantId}
                dividerIndex={firstWaitingIndex}
                compact
                onSelect={(id) => selectContestant(id)}
              />
            </div>
            <div className="hidden sm:flex flex-col flex-1 min-h-0 border-t hud-divider">
              <h2 className="hud-label px-4 pt-2 pb-1">Flight of {selectedName}</h2>
              <div className="flex-1 min-h-0 overflow-y-auto hud-scroll">
                <FlightTimeline
                  waypoints={staticNavTaskData.route.waypoints}
                  gateTimes={selectedContestant.gate_times}
                  timesKnown={!selectedContestant.adaptive_start || selectedContestant.has_crossed_starting_line
                    || (annotationsByContestant[selectedContestant.id] ?? []).some(a => /adaptive start set/i.test(a.message))}
                  entries={visibleLogEntries.filter(e => mode !== 'playback' || new Date(e.time) <= currentTime)}
                  annotations={(annotationsByContestant[selectedContestant.id] ?? []).filter(a =>
                    (mode !== 'playback' || new Date(a.time) <= currentTime)
                    && ((a.gate_type !== 'secret' && a.gate_type !== 'ul') || (staticNavTaskData.display_secrets && userShowSecrets)))}
                  onSelectAnnotation={jumpToAnnotation}
                  showSecrets={!!(staticNavTaskData.display_secrets && userShowSecrets)}
                  now={currentTime}
                  timeZone={staticNavTaskData.time_zone}
                  pointsArePenalties={pointsArePenalties}
                  onSelectEntry={jumpToLogEntry}
                  onSelectGate={(wp) => mapRef.current?.flyTo([wp.latitude, wp.longitude], Math.max(mapRef.current.getZoom(), 12), { duration: 0.6 })}
                />
              </div>
            </div>
          </div>
        ) : (
          <RankingList
            rows={standings}
            selectedId={selectedContestantId}
            dividerIndex={firstWaitingIndex}
            onSelect={(id) => selectContestant(id)}
          />
        )}
      </SidePanel>

      <div className="flex-1 min-w-0 min-h-0 flex flex-col">
        <div className="relative flex-1 min-h-0">
          <div id="map-container" className="h-full w-full" />
          <ProhibitedRenderer map={mapRef.current} navTask={staticNavTaskData} />
          <RouteRenderer
            map={mapRef.current}
            route={staticNavTaskData?.route ?? null}
            taskCatalogueTargets={staticNavTaskData?.task_catalogue_targets ?? []}
            scorecard={staticNavTaskData?.scorecard}
            taskType={staticNavTaskData?.scorecard?.task_type ?? null}
            taskSubtype={staticNavTaskData?.task_subtype ?? null}
            navTaskDisplaySecrets={staticNavTaskData?.display_secrets ?? false}
            displaySecrets={userShowSecrets}
            contestants={contestantsById}
            selectedContestantId={selectedContestantId}
            isInitialLoad={!hasMapBeenFitted}
            onMapFit={setHasMapBeenFitted}
          />
          {mode === 'realtime' && wsStatus === 'disconnected' && (
            <div className="hud absolute top-3 left-1/2 -translate-x-1/2 z-[1100] rounded-lg px-3 py-2 text-center max-w-xs border hud-divider">
              <p className="font-semibold text-sm" style={{ color: 'var(--hud-red)' }}>Connection lost</p>
              <p className="hud-label">Reconnecting to the live data.</p>
            </div>
          )}
        </div>

        {mode === 'playback' && playbackTimeInfo ? (
          <>
            {selectedContestant && staticNavTaskData && (
              // Who is being replayed, with their score and place at the replay's time, in one slim row above the replay bar.
              <FollowBar
                key={selectedContestant.id}
                contestant={selectedContestant}
                navigationTask={staticNavTaskData}
                score={standings[selectedStanding]?.score ?? 0}
                rank={selectedStanding >= 0 && selectedStanding < startedCount ? selectedStanding + 1 : null}
                rankOf={startedCount}
                live={false}
                slim
              />
            )}
            <ReplayBar
              currentTime={currentTime}
              startTime={playbackTimeInfo.start}
              endTime={playbackTimeInfo.end}
              timeZone={staticNavTaskData?.time_zone}
              isPlaying={isPlaying}
              playbackSpeed={playbackSpeed}
              onPlayPause={() => setIsPlaying(p => !p)}
              onJumpToStart={() => setPlaybackTime(playbackTimeInfo.start)}
              onTimeChange={setPlaybackTime}
              onSpeedChange={setPlaybackSpeed}
              events={replayEvents}
            spanChoice={ownFlightSpan ? { wholeDay: replayWholeDay, onToggle: () => setReplayWholeDay(w => !w) } : undefined}
              onEventSelect={(id) => {
                const entry = visibleLogEntries.find(e => e.id === id);
                if (entry) { setPanelTab('log'); jumpToLogEntry(entry); }
              }}
            />
          </>
        ) : selectedContestant && staticNavTaskData ? (
          <FollowBar
            key={selectedContestant.id}
            contestant={selectedContestant}
            navigationTask={staticNavTaskData}
            score={standings[selectedStanding]?.score ?? 0}
            rank={selectedStanding >= 0 && selectedStanding < startedCount ? selectedStanding + 1 : null}
            rankOf={startedCount}
            gateArrowData={gateArrowDataByContestant[selectedContestant.id]}
            dangerData={dangerDataByContestant[selectedContestant.id]}
            live={view === 'follow'}
          />
        ) : null}
      </div>
    </div>
  );
}
