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
import { useFollowCamera } from './hooks/useFollowCamera';
import { useCrossingNotices } from './hooks/useCrossingNotices';
import { useDisplayRotation } from './hooks/useDisplayRotation';
import { useDisplayKeys } from './hooks/useDisplayKeys';
import { neighbourGaps } from './utils/neighbours';
import { stepThrough } from './utils/displayKeys';
import DisplayKeysHelp from './components/hud/DisplayKeysHelp';
import { fetchContestDetails, fetchPhotoObservations, fetchPhotos } from './api';

import ProhibitedRenderer from "./components/track-renderers/ProhibitedRenderer";
import RouteRenderer from "./components/track-renderers/RouteRenderer";
import Disclaimer from './components/Disclaimer';
import SidePanel, { PanelTab } from './components/hud/SidePanel';
import RankingList from './components/hud/RankingList';
import NavLog from './components/hud/NavLog';
import GatesTable from './components/hud/GatesTable';
import FlightTimeline from './components/hud/FlightTimeline';
import FollowBar from './components/hud/FollowBar';
import MapControls from './components/hud/MapControls';
import SettingToggle from './components/hud/SettingToggle';
import { guideUrl } from './utils/helpLink';
import ReplayBar, { ReplayEvent } from './components/hud/ReplayBar';
import TaskInfoModal from './TaskInfoModal';
import { Trophy, Info, Settings, Calendar, Sliders, Route, CircleHelp } from 'lucide-react';
import { generatePath } from '../../urls';
import './CompetitionMap.css';
import './components/hud/hud.css';
import { GateResult, NavigationTask, PhotoObservation, ScoreAnnotation, ScoreLogEntry } from './types';


/** The contestant a contestantIds parameter names when it names exactly one, otherwise null. */
function singleContestantId(param: string | null): number | null {
  const ids = (param ?? '').split(',').filter(s => s !== '').map(Number);
  return ids.length === 1 && Number.isFinite(ids[0]) ? ids[0] : null;
}

// Stable empty values: a fresh [] each render would make the photo layers redraw on every tick and close hover tooltips
const NO_PHOTOS: TargetPhoto[] = [];
const NO_OBSERVATIONS: PhotoObservation[] = [];




/** The scorecard's task types as a list: a list for some scorecards, a single string for older ones. */
function taskTypeList(taskType: string[] | string | undefined): string[] {
  return Array.isArray(taskType) ? taskType : taskType ? [taskType] : [];
}

export default function CompetitionMapPage() {
  const { contestId, navigationTaskId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const contestIdNum = Number(contestId ?? 632);
  const navigationTaskIdNum = Number(navigationTaskId ?? 2129);

  const initialMode = (searchParams.get('mode') as 'realtime' | 'playback') || 'realtime';
  // The map as a display (a link option): "broadcast", a clean picture to put on air (no site header, no panel or map
  // controls, the follow bar as a lower third), or "screen", an unattended screen at the airfield.
  const displayParam = searchParams.get('display');
  const display: 'broadcast' | 'screen' | null = displayParam === 'broadcast' || displayParam === 'screen' ? displayParam : null;
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
    if (display === 'screen') return false; // the standings are half of what a screen is for
    // A phone, upright or on its side, starts with the map in view.
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
    liveCrossings,
    progress,
    wsStatus,
    error: navTaskError,
  } = useCompetitionData(contestIdNum, navigationTaskIdNum, mode);

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
    // No scale bars on air.
    if (!map || display === 'broadcast') return;

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
  }, [mapRef, display]);

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
  // A second contestant compared with the selected one (the debrief's gates table); it belongs to that selection.
  const [compare, setCompare] = useState<{ forId: number; id: number } | null>(null);
  const compareId = compare && compare.forId === selectedContestantId ? compare.id : null;
  const ownFlightSpan = useMemo(() => {
    if (selectedContestantId === null) return null;
    const own = flightSpan(positionsByContestant[selectedContestantId]);
    const other = compareId !== null ? flightSpan(positionsByContestant[compareId]) : null;
    // Compared, the replay covers both flights.
    if (!own || !other) return own ?? other;
    return { start: own.start < other.start ? own.start : other.start, end: own.end > other.end ? own.end : other.end };
  }, [selectedContestantId, compareId, positionsByContestant]);
  const {
    playbackSpeed,
    setPlaybackSpeed,
    isPlaying,
    setIsPlaying,
    playbackTime,
    setPlaybackTime,
    moveClockKeepingPlay,
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

  // A replay time outside the span (another contestant, back from the whole day, or the clock before the replay has
  // started) goes to the span's start: the flight replays from takeoff.
  useEffect(() => {
    if (mode !== 'playback' || !playbackTimeInfo) return;
    const clamped = clampToSpan(playbackTime, playbackTimeInfo);
    // The link's own time goes to the nearest end of the span; otherwise the flight replays from its takeoff. The clock
    // moves without pausing, so an autoplaying link goes on playing.
    if (clamped !== playbackTime) moveClockKeepingPlay(initialTime ? clamped : playbackTimeInfo.start);
  }, [mode, playbackTimeInfo, playbackTime, moveClockKeepingPlay, initialTime]);

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
  };
  const handleContestantSelect = (id: number | null, showLog: boolean) => selectContestant(id, showLog);

  const { openAnnotation } = useMapLayers({
    compareContestantId: compareId,
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

  // The follow camera keeps the followed aircraft in view: live while following, and in a replay while it plays.
  // Live it also shows the next gate with the aircraft when the gate changes (the gate the arrow counts down to).
  const followedPosition = selectedContestantId !== null ? currentPositions[selectedContestantId]?.at(-1) : undefined;
  const followedGateName = mode === 'realtime' && selectedContestantId !== null
    ? gateArrowDataByContestant[selectedContestantId]?.waypoint_name ?? null : null;
  const followedGate = useMemo(() => {
    const wp = followedGateName ? staticNavTaskData?.route.waypoints.find(w => w.name === followedGateName) : undefined;
    return wp ? { name: wp.name, position: { lat: wp.latitude, lon: wp.longitude } } : null;
  }, [followedGateName, staticNavTaskData]);
  const camera = useFollowCamera({
    mapRef,
    // On air the camera always follows; elsewhere while following live, and in a replay while it plays.
    enabled: !!selectedContestant && (display === 'broadcast'
      ? mode === 'realtime' || isPlaying
      : (mode === 'realtime' && view === 'follow') || (mode === 'playback' && isPlaying)),
    followId: selectedContestantId,
    aircraft: followedPosition ? { lat: followedPosition.latitude, lon: followedPosition.longitude } : null,
    gate: followedGate,
  });

  // A notice at the gate whenever a contestant crosses a timed gate, live and in a replay.
  // The camera is on the followed contestant, so the notices are theirs (and the one compared with): the field's
  // are for the overview.
  const onlyFor = useMemo(
    () => selectedContestantId === null ? null : [selectedContestantId, ...(compareId !== null ? [compareId] : [])],
    [selectedContestantId, compareId],
  );
  useCrossingNotices({
    mapRef,
    mode,
    navTask: staticNavTaskData,
    contestants: sortedContestants,
    liveCrossings,
    currentTime,
    showSecrets: !!(staticNavTaskData?.display_secrets && userShowSecrets),
    playbackSpeed,
    onlyFor,
  });

  const overlayBarsRef = useRef<HTMLDivElement>(null);

  /** Switches the display (the link's ?display=...), keeping the rest of the link; standard has no option. */
  const changeDisplay = (next: 'standard' | 'screen' | 'broadcast') => {
    const params = new URLSearchParams(searchParams);
    if (next === 'standard') params.delete('display'); else params.set('display', next);
    setSearchParams(params, { replace: true });
    // The airfield screen is the standings and the map together: the panel opens.
    if (next === 'screen') setIsRankingCollapsed(false);
  };

  // The site's header is drawn by the server, which leaves it out of a broadcast link; switching display here hides or
  // shows it again.
  useEffect(() => {
    const header = document.querySelector<HTMLElement>('body > header');
    if (!header) return;
    header.style.display = display === 'broadcast' ? 'none' : '';
    return () => { header.style.display = ''; };
  }, [display]);
  /** The whole route in view; the follow camera waits until "Follow again". */
  const fitRoute = () => {
    const map = mapRef.current;
    const points = (staticNavTaskData?.route.waypoints ?? []).map(w => [w.latitude, w.longitude] as [number, number]);
    if (!map || points.length === 0) return;
    camera.pause();
    // On air the bars float over the map's foot: keep the route clear of them.
    const covered = display === 'broadcast' ? (overlayBarsRef.current?.offsetHeight ?? 0) : 0;
    map.fitBounds(L.latLngBounds(points), { paddingTopLeft: [48, 48], paddingBottomRight: [48, 48 + covered], animate: true });
  };

  // The displays' keys: follow by place or step through those in the air, the camera on or off, back to the field.
  const [keysHelpOpen, setKeysHelpOpen] = useState(false);
  const followFromKeys = (id: number | null) => {
    setActiveLogId(null);
    setPanelTab('ranking');
    setSelectedContestantId(id);
  };
  useDisplayKeys({
    enabled: display !== null,
    onAction: (action) => {
      if (action.kind === 'place') {
        const row = action.place <= startedCount ? standings[action.place - 1] : undefined;
        if (row) followFromKeys(row.id);
      } else if (action.kind === 'step') {
        const next = stepThrough(flyingIds, selectedContestantId, action.by);
        if (next !== null) followFromKeys(next);
      } else if (action.kind === 'camera') {
        if (camera.paused) camera.resume(); else camera.pause();
      } else if (action.kind === 'overview') {
        if (keysHelpOpen) return setKeysHelpOpen(false);
        followFromKeys(null);
        fitRoute();
      } else {
        setKeysHelpOpen(open => !open);
      }
    },
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
          // A gate counts as crossed once its actual crossing time (gate_results) has come; the map's log only has
          // entries with points, so it misses a crossing without a timing result (an adaptive start, no time check).
          const crossed = (gate?: string) => !!gate && (
            logsForTime.some(log => log.gate === gate)
            || !!c.gate_results?.some(r => r.gate === gate && r.actual !== null && new Date(r.actual) <= currentTime));
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

      const poker = taskTypeList(staticNavTaskData.scorecard.task_type).includes('poker');
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
            // The route's progress runs from the starting line to the finish line: past it the bar is gone, though the
            // calculator goes on until the finished-by time. A poker run counts cards instead, which end the flight.
            progress: c.contestanttrack?.passed_finish_gate && !poker ? undefined : (c.progress ?? c.contestanttrack?.progress),
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

  // An unattended screen (?display=screen) goes round by itself: the whole field, then each flying contestant in turn.
  const flyingIds: number[] = standings.filter(r => r.is_active_flight).map(r => r.id as number);
  useDisplayRotation({
    enabled: display === 'screen' && mode === 'realtime',
    flyingIds,
    onStep: (step) => {
      setActiveLogId(null);
      setPanelTab('ranking');
      if (step.kind === 'follow') {
        setSelectedContestantId(step.id);
      } else {
        setSelectedContestantId(null);
        fitRoute();
      }
    },
  });


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

  // A flight list under the ranking only where gates make the flight: not for a poker run (its gates deal cards, and
  // the follow bar shows them) or a landing task, whose crossings the gate results do not record.
  const taskTypes = taskTypeList(staticNavTaskData?.scorecard?.task_type);
  const hasFlightList = !taskTypes.some(t => t.includes('poker') || t.includes('landing'));

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

  /** A gate of the gates table: its timing result where it has one, else its crossing's note, else the gate itself. */
  const jumpToGate = (result: GateResult) => {
    const timing = visibleLogEntries.find(e => e.gate === result.gate && e.planned && e.actual);
    if (timing) return jumpToLogEntry(timing);
    const note = selectedContestantId !== null
      ? (annotationsByContestant[selectedContestantId] ?? []).find(a => a.gate === result.gate) : undefined;
    if (note) return jumpToAnnotation(note);
    const wp = staticNavTaskData?.route.waypoints.find(w => w.name === result.gate);
    if (wp) mapRef.current?.flyTo([wp.latitude, wp.longitude], Math.max(mapRef.current.getZoom(), 12), { duration: 0.6 });
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
  // The race around the followed contestant: who is just above and below, and by how many points.
  const gaps = neighbourGaps(standings, selectedStanding, startedCount);
  const lastName = (id: number) => contestantsById[id]?.team?.crew?.member1?.last_name ?? '';
  const neighbours = {
    above: gaps.above && { name: lastName(gaps.above.id), points: gaps.above.points },
    below: gaps.below && { name: lastName(gaps.below.id), points: gaps.below.points },
  };

  const toolbar = (
    <>
          {/* Settings Dropdown */}
          <div className="dropdown">
            <div tabIndex={0} role="button" className="hud-button" title="Map settings: appearance, display, and what is shown on the map" aria-label="Map settings">
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
                      title={value === 'device' ? "Follow this device's light or dark mode, as the rest of the site does" : value === 'light' ? 'Always light' : 'Always dark'}
                      onClick={() => setAppearance(value)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </li>
              <li className="menu-title px-2 pb-1 pt-0.5">
                <span className="text-xs font-normal opacity-70">Display</span>
              </li>
              <li className="pb-1">
                <div className="join w-full p-0 hover:bg-transparent" role="group" aria-label="Display">
                  {([['standard', 'Standard', 'The usual page'], ['screen', 'Screen', 'An airfield screen: larger type, goes round the contestants by itself'], ['broadcast', 'Broadcast', 'Only the map and the lower third, for a broadcast']] as ['standard' | 'screen' | 'broadcast', string, string][]).map(([value, label, hint]) => (
                    <button
                      key={value}
                      type="button"
                      className={`join-item btn btn-xs flex-1 ${(display ?? 'standard') === value ? 'btn-primary' : 'btn-ghost border-base-300'}`}
                      aria-pressed={(display ?? 'standard') === value}
                      title={hint}
                      onClick={() => changeDisplay(value)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </li>
              <div className="divider my-1"></div>
              <SettingToggle
                label="Background map"
                hint="Draw the route on top of a street and terrain map. Off gives a plain background."
                checked={userShowBackgroundMap}
                onChange={setUserShowBackgroundMap}
                disabledReason={staticNavTaskData?.display_background_map ? undefined : 'The organizer has turned the background map off for this task.'}
              />
              <SettingToggle
                label="Secret gates"
                hint="Show the secret gates, unknown legs and observation photos on the map and in the lists."
                checked={userShowSecrets}
                onChange={setUserShowSecrets}
                disabledReason={staticNavTaskData?.display_secrets ? undefined : 'The organizer keeps the secret gates hidden for this task.'}
              />
              <SettingToggle
                label="Penalties only"
                hint="For the followed contestant, label only the penalties on the map, not every gate passed."
                checked={showPenaltiesOnly}
                onChange={setShowPenaltiesOnly}
              />
              <SettingToggle
                label="Labels always open"
                hint="Keep every label of the followed contestant open on the map, instead of one at a time when clicked."
                checked={permanentAnnotations}
                onChange={setPermanentAnnotations}
              />
              <div className="divider my-1"></div>
              <div className="px-2 pb-1" title="Untick a contestant to leave them out of the map and the ranking.">
                  <div className="flex justify-between items-center">
                      <span className="text-xs">Contestants shown</span>
                      <div className="flex gap-2">
                          <button onClick={selectAllContestants} className="text-[10px] link" title="Show every contestant">All</button>
                          <button onClick={selectNoneContestants} className="text-[10px] link" title="Hide every contestant">None</button>
                      </div>
                  </div>
                  <p className="text-[10px] leading-snug opacity-70">Untick a contestant to leave them out of the map and the ranking.</p>
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
        title="Show the whole track of every contestant, not only the last minutes"
        aria-label="Full trails"
      >
        <Route size={16} />
      </button>
      <button onClick={() => setIsInfoModalOpen(true)} className="hud-button" title="About this task: the rules and what is scored" aria-label="Task information">
        <Info size={16} />
      </button>
      <Link to={generatePath('MISSION_DASHBOARD_DETAIL', { contestId: contestIdNum })} className="hud-button" title="The results of the whole contest" aria-label="Contest results">
        <Trophy size={16} />
      </Link>
      {/* Where in the guide depends on what is on screen. */}
      <a
        href={guideUrl(display === 'screen' ? 'screen' : view === 'debrief' ? 'debrief' : view === 'follow' ? 'following' : 'spectators')}
        target="_blank" rel="noreferrer" className="hud-button"
        title="How to use the map: following, replaying, displays (opens the guide)" aria-label="How to use the map"
      >
        <CircleHelp size={16} />
      </a>
      {(staticNavTaskData?.user_has_change_permission || document.configuration.is_superuser) && (
        <Link to={generatePath('NAVIGATION_TASK_DETAIL', { contestId: contestIdNum, navigationTaskId: navigationTaskIdNum })} className="hud-button" title="Manage this task: contestants, times, scores (organizers)" aria-label="Manage the task">
          <Settings size={16} />
        </Link>
      )}
      {staticNavTaskData?.allow_self_management && (
        <Link to={`/schedule-flight?contestId=${contestIdNum}&navigationTaskId=${navigationTaskIdNum}`} className="hud-button" title="Book a flight in this task" aria-label="Book a flight">
          <Calendar size={16} />
        </Link>
      )}
    </>
  );

  // The followed contestant's flight: under the ranking, or on a phone in its own tab.
  const flightTimeline = selectedContestant && staticNavTaskData ? (
    <FlightTimeline
      waypoints={staticNavTaskData.route.waypoints}
      gateResults={selectedContestant.gate_results ?? []}
      timesKnown={!selectedContestant.adaptive_start || selectedContestant.has_crossed_starting_line
        || !!selectedContestant.gate_results?.find(r => r.type === 'sp')?.actual}
      entries={visibleLogEntries.filter(e => mode !== 'playback' || new Date(e.time) <= currentTime)}
      annotations={(annotationsByContestant[selectedContestant.id] ?? []).filter(a =>
        (mode !== 'playback' || new Date(a.time) <= currentTime)
        && ((a.gate_type !== 'secret' && a.gate_type !== 'ul') || (staticNavTaskData.display_secrets && userShowSecrets)))}
      onSelectAnnotation={jumpToAnnotation}
      showSecrets={!!(staticNavTaskData.display_secrets && userShowSecrets)}
      now={currentTime}
      missesKnown={mode === 'realtime' || (!!playbackTimeInfo && currentTime >= playbackTimeInfo.end)}
      crossingOrder={staticNavTaskData.task_subtype === 'turnpoint_hunt'}
      timeZone={staticNavTaskData.time_zone}
      pointsArePenalties={pointsArePenalties}
      onSelectEntry={jumpToLogEntry}
      onSelectGate={(wp) => mapRef.current?.flyTo([wp.latitude, wp.longitude], Math.max(mapRef.current.getZoom(), 12), { duration: 0.6 })}
    />
  ) : null;

  return (
    // data-hud picks the panel's light or dark tokens (components/hud/hud.css) for everything inside, the map's labels too.
    <div className="flex flex-col sm:flex-row h-full overflow-hidden" data-hud={hudTheme} data-display={display ?? undefined}>
      <TaskInfoModal isOpen={isInfoModalOpen} onClose={() => setIsInfoModalOpen(false)} />

      {display !== 'broadcast' && (
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
        showFlightTab={hasFlightList}
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
          <>
            <GatesTable
              gateResults={(selectedContestant.gate_results ?? []).filter(r => !r.hidden || (staticNavTaskData?.display_secrets && userShowSecrets))}
              entries={visibleLogEntries}
              timeZone={staticNavTaskData?.time_zone}
              pointsArePenalties={pointsArePenalties}
              onSelect={jumpToGate}
              // Anyone who flew (has a track), whatever the replay's time.
              compareOptions={allSortedContestants
                .filter(c => c.id !== selectedContestant.id && (positionsByContestant[c.id]?.length ?? 0) > 0)
                .map(c => ({ id: c.id, name: `#${c.contestant_number} ${c.team?.crew?.member1?.first_name ?? ''} ${c.team?.crew?.member1?.last_name ?? ''}`.trim() }))}
              compare={compareId !== null && contestantsById[compareId] ? {
                id: compareId,
                name: contestantsById[compareId].team?.crew?.member1?.last_name ?? `#${contestantsById[compareId].contestant_number}`,
                results: (contestantsById[compareId].gate_results ?? []).filter(r => !r.hidden || (staticNavTaskData?.display_secrets && userShowSecrets)),
              } : null}
              onCompare={(id) => setCompare(id === null ? null : { forId: selectedContestant.id, id })}
            />
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
          </>
        ) : selectedContestant && panelTab === 'flight' && hasFlightList ? (
          flightTimeline
        ) : selectedContestant && staticNavTaskData && hasFlightList ? (
          // Following someone: the ranking (only as tall as its rows) with their flight under it, so the panel shows both
          // where they stand and how the flight is going. On a phone the panel is too small for both: ranking only.
          <div className="flex flex-col h-full">
            <div className="flex-none max-h-[45%] sm:max-h-[40%] overflow-y-auto hud-scroll">
              <RankingList
                rows={standings}
                selectedId={selectedContestantId}
                dividerIndex={firstWaitingIndex}
                compact
                keepTop={display === 'screen'}
                onSelect={(id) => selectContestant(id)}
              />
            </div>
            <div className="hidden sm:flex flex-col flex-1 min-h-0 border-t hud-divider">
              <h2 className="hud-label px-4 pt-2 pb-1">Flight of {selectedName}</h2>
              <div className="flex-1 min-h-0 overflow-y-auto hud-scroll">
                {flightTimeline}
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
      )}

      <div className="relative flex-1 min-w-0 min-h-0 flex flex-col">
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
          <MapControls display={display ?? 'standard'} onLeaveBroadcast={() => changeDisplay('standard')} onFitRoute={fitRoute} />
          {keysHelpOpen && <DisplayKeysHelp onClose={() => setKeysHelpOpen(false)} />}
          {camera.paused && (
            <button
              title="The map was moved by hand; this makes it follow the aircraft again"
              className={`hud hud-button absolute ${display === 'broadcast' ? 'top-3' : 'bottom-3'} left-1/2 -translate-x-1/2 z-[1100] px-4 h-10 rounded-full border hud-divider shadow-lg`}
              onClick={camera.resume}
            >
              Follow again
            </button>
          )}
          {mode === 'realtime' && wsStatus === 'disconnected' && (
            <div className="hud absolute top-3 left-1/2 -translate-x-1/2 z-[1100] rounded-lg px-3 py-2 text-center max-w-xs border hud-divider">
              <p className="font-semibold text-sm" style={{ color: 'var(--hud-red)' }}>Connection lost</p>
              <p className="hud-label">Reconnecting to the live data.</p>
            </div>
          )}
        </div>

        {/* On air the bars float over the map as a lower third; elsewhere they sit under it. */}
        <div ref={overlayBarsRef} className={display === 'broadcast' ? 'absolute inset-x-6 bottom-6 z-[1100] rounded-xl overflow-hidden shadow-2xl' : ''}>
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
                neighbours={neighbours}
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
            neighbours={neighbours}
            gateArrowData={gateArrowDataByContestant[selectedContestant.id]}
            dangerData={dangerDataByContestant[selectedContestant.id]}
            live={view === 'follow'}
          />
        ) : null}
        </div>
      </div>
    </div>
  );
}
