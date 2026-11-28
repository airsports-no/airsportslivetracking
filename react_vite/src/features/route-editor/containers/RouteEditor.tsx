import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import Toolbar from '../components/Toolbar';
import GateWidthModal from '../components/GateWidthModal';
import MapCanvas from '../components/MapCanvas';
import MapModeBanner from '../components/MapModeBanner';
import TaskChoiceModal from '../components/TaskChoiceModal';
import {
  fetchRoute,
  fetchTaskCompatibility,
  fetchTaskSubtypeCatalog,
  saveRoute,
  RouteRequirementTool,
  TaskCompatibilityResult,
  TaskCompatibilitySubtype,
} from '../api';
import { SavePayload } from '../types';
import { generatePath } from '../../../urls';
import {
  getDistance,
  getBearing,
  getDestinationPoint,
  toRad,
} from '../../../utils/geoUtils';
import { getQuadraticBezierPoints } from '../../../utils/bezierPoints';
import { RoutePoint, Gate, ObservationMarker, Polygon, LatLng, SelectionType, Mode } from '../../../types';
import { Map } from 'leaflet';
import { buildWizardChecklist, type CompatibilityStatus, getRouteEditorFlags } from '../taskRequirements';
import { getTaskTemplateById } from '../taskTemplates';
import { applyGuideChoice, applyManualTick, emptyIntent, RouteIntent } from '../routeIntent';
import { countForTool, getToolAction, getToolWizardStep } from '../guideTools';
import { autoAdvance, doneButtonLabel, findStep, nextUnmetRequiredStep, resolveStepEnd, shouldOfferTaskChoice, type StepEnd } from '../guideProgress';
import { createStandalonePointTypeSet, parseRouteEditorFeatureCollection } from '../routeDataParsing';
import {
  deleteItemById,
  normalizeDeletedBackboneRoutePoints,
  renumberRoutePoints,
  reorderItemsById,
  reverseRoutePoints,
  SECRET_GATE_CHECKS,
  setWidthOfPoints,
  updateItemById,
} from '../routeEditorMutations';
import { buildRouteEditorSavePayload, observationPhotoNameProblems, validateRouteEditorState } from '../routeEditorValidation';
import {
  createBackboneRoutePoint,
  createCatalogueTurnpoint,
  createInsertedRoutePoint,
  createObservationMarker,
  createStandaloneWizardPoint,
  createTakeoffLandingGate,
  getMinimumObservationDistance,
  legInsertTypeFor,
  normalizeRoutePointsBeforeAppend,
} from '../routeEditorMapClickHelpers';
import { getWizardTransition } from '../routeEditorWizardTransitions';
import { getModeBanner } from '../modeBanner';
import { editorKeyAction } from '../routeEditorKeys';
import { selectionAfterRestore, type RouteSnapshot } from '../routeHistory';
import { hasRemoval, planRouteChange, removalNotice } from '../routeIntegrity';
import RouteChangeNotice, { type RouteNotice } from '../components/RouteChangeNotice';
import useRouteHistory from '../useRouteHistory';
import { useToast } from '../../competition-map/hooks/useToast';
import {
  buildDummyBranchWaypoint,
  getDummyBranchPhase,
  getWizardBannerText,
  isUnknownLegTrigger,
  nameUnknownLegsRoutePoints,
  previousOnDummyBranch,
} from '../unknownLegWizard';

export default function RouteEditor() {
  const [routePoints, setRoutePoints] = useState<RoutePoint[]>([]);
  const [gates, setGates] = useState<Gate[]>([]);
  const [observationMarkers, setObservationMarkers] = useState<ObservationMarker[]>([]);
  const [polygons, setPolygons] = useState<Polygon[]>([]);
  const [standalonePoints, setStandalonePoints] = useState<RoutePoint[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectionType, setSelectionType] = useState<SelectionType | null>(null);
  const { routeId: paramRouteId } = useParams<{ routeId: string }>();
  // A new route has no id in the URL until its first save navigates to it
  const [createdRouteId, setCreatedRouteId] = useState<string | null>(null);
  const routeId = paramRouteId ?? createdRouteId;
  const navigate = useNavigate();
  const { showToast, ToastContainer, toasts, removeToast } = useToast();
  // Id of the route just saved, to offer creating a navigation task from it
  const [createTaskPromptRouteId, setCreateTaskPromptRouteId] = useState<number | null>(null);
  const [routeName, setRouteName] = useState('');
  const [isDirty, setIsDirty] = useState(false);

  const [mode, setMode] = useState<Mode>('view');
  const [tempGatePoint, setTempGatePoint] = useState<LatLng | null>(null);
  const [gateWidthsOpen, setGateWidthsOpen] = useState(false);
  const [tempPolygonPoints, setTempPolygonPoints] = useState<LatLng[]>([]);
  const [showCorridor, setShowCorridor] = useState(false);
  const [addCurveMode, setAddCurveMode] = useState(false);
  const [maxObsDist, setMaxObsDist] = useState(926);
  const [hideLabels, setHideLabels] = useState(false);
  const [selectedTaskTemplateId, setSelectedTaskTemplateId] = useState<string | null>(null);
  // The author's intent: the task chosen in the guide plus what they tick in the route settings (see routeIntent.ts).
  const [intent, setIntent] = useState<RouteIntent>(() => emptyIntent());
  const intendedTaskTypes = intent.types;
  const [taskCompatibility, setTaskCompatibility] = useState<TaskCompatibilityResult | null>(null);
  // Which route content the latest answer (or failure) was for; see compatibilityStatus.
  const [compatibilityAnswer, setCompatibilityAnswer] = useState<{ route: unknown; failed: boolean } | null>(null);
  const [wizardRouteInsertType, setWizardRouteInsertType] = useState<RoutePoint['type'] | null>(null);
  const [wizardRouteInsertFeatureType, setWizardRouteInsertFeatureType] = useState<RoutePoint['featureType'] | undefined>(undefined);
  const [wizardPolygonType, setWizardPolygonType] = useState<Polygon['type'] | null>(null);
  const [currentWizardActionLabel, setCurrentWizardActionLabel] = useState<string | null>(null);
  const [pendingPointTypeSelection, setPendingPointTypeSelection] = useState<RoutePoint['type'] | null>(null);
  const [pendingPointFeatureTypeSelection, setPendingPointFeatureTypeSelection] = useState<RoutePoint['featureType'] | undefined>(undefined);
  const [dummyBranchTriggerId, setDummyBranchTriggerId] = useState<string | null>(null);
  const [wizardPrompt, setWizardPrompt] = useState<string | null>(null);
  // The guide step that is active: the tool it started. Cleared when the step stops (stopWizardAction).
  const [activeGuideTool, setActiveGuideTool] = useState<RouteRequirementTool | null>(null);
  // A new route opens with the choice of task over the map. Answered or closed once, it does not come back; a saved
  // route has an id in the URL and never shows it.
  const [taskChoiceOpen, setTaskChoiceOpen] = useState(() => shouldOfferTaskChoice(paramRouteId));
  // A task was chosen: its first unmet required step starts as soon as the steps are known.
  const [startFirstStep, setStartFirstStep] = useState(false);
  const visibleTaskTypeGroups = useMemo(() => {
    const groups = document.configuration.visibleTaskTypeGroups;
    if (Array.isArray(groups) && groups.length > 0) {
      return groups;
    }
    return document.configuration.showCimaTaskTypes ? ['legacy', 'cima'] : ['legacy'];
  }, []);

  // What is special about the selected task type comes from the backend's registry (the flags of the template's
  // subtype), not from the template's id. The compatibility answer carries them; until it arrives the subtype catalog,
  // fetched once, does.
  const [subtypeCatalog, setSubtypeCatalog] = useState<TaskCompatibilitySubtype[] | null>(null);
  useEffect(() => {
    fetchTaskSubtypeCatalog()
      .then(setSubtypeCatalog)
      .catch((err) => console.error('Failed to fetch the task types', err));
  }, []);
  const routeEditorFlags = useMemo(
    () => getRouteEditorFlags(taskCompatibility?.subtypes ?? subtypeCatalog, getTaskTemplateById(selectedTaskTemplateId)?.subtype),
    [taskCompatibility, subtypeCatalog, selectedTaskTemplateId],
  );

  // 2.A3: the route is exactly SP, MP and FP.
  const isThreePointBackboneTask = routeEditorFlags.three_point_backbone;
  const isCircleStandaloneTask = routeEditorFlags.circle_markers;
  // 2.A6 and 2.B2 have no route backbone at all: the route is exactly three
  // free-map timed turnpoints (known_time_gate markers) plus any number of
  // untimed catalogue turnpoints, all as standalone points.
  const isTimedTurnpointStandaloneTask = routeEditorFlags.standalone_timed_turnpoints;
  const isCurveRequiredTask = routeEditorFlags.curve_required;
  // 2.A5: unknown-leg points are followed by extension waypoints.
  const hasExtensionWaypoints = routeEditorFlags.extension_waypoints;
  const standalonePointTypes = useMemo(() => {
    return createStandalonePointTypeSet(isCircleStandaloneTask);
  }, [isCircleStandaloneTask]);

  const totalLength = useMemo(() => {
    let dist = 0;
    for (let i = 0; i < routePoints.length - 1; i++) {
      const p1 = routePoints[i];
      const p2 = routePoints[i + 1];
      if (p2.segmentType === 'curved' && p2.controlLat && p2.controlLng) {
        const curvePoints = getQuadraticBezierPoints(p1, p2, { lat: p2.controlLat, lng: p2.controlLng });
        for (let j = 0; j < curvePoints.length - 1; j++) {
          dist += getDistance(curvePoints[j], curvePoints[j + 1]);
        }
      } else {
        dist += getDistance(p1, p2);
      }
    }
    return dist;
  }, [routePoints]);

  const modeRef = useRef(mode);
  const routePointsRef = useRef(routePoints);
  const [mapInstance, setMapInstance] = useState<Map | null>(null);
  const [pendingBounds, setPendingBounds] = useState<L.LatLngBoundsExpression | null>(null);

  const markDirty = useCallback(() => setIsDirty(true), []);

  // Undo and redo of the route content (not the selection, mode, map view or settings). Every change of the content is
  // a step; see useRouteHistory for how a drag, typing and placing are delimited.
  const content = useMemo<RouteSnapshot>(
    () => ({ routePoints, standalonePoints, gates, observationMarkers, polygons }),
    [routePoints, standalonePoints, gates, observationMarkers, polygons],
  );
  const restoreContent = useCallback((snapshot: RouteSnapshot) => {
    setRoutePoints(snapshot.routePoints);
    setStandalonePoints(snapshot.standalonePoints);
    setGates(snapshot.gates);
    setObservationMarkers(snapshot.observationMarkers);
    setPolygons(snapshot.polygons);
    // Undoing back to the saved route can leave it marked as changed; that is accepted
    setIsDirty(true);
    // A selected item that is not in the restored content is no longer selected
    const selection = selectionAfterRestore(selectedId, selectionType, snapshot);
    if (selection.selectedId !== selectedId) {
      setSelectedId(selection.selectedId);
      setSelectionType(selection.selectionType);
    }
  }, [selectedId, selectionType]);
  const history = useRouteHistory(content, restoreContent);
  const { reset: resetHistory, runUndoableStep } = history;

  // Every change the user makes to the route points goes through here (the loading and restoring of a route do not).
  // It removes what the change makes illegal (hidden gates on a leg that changed, photos now out of range, see
  // routeIntegrity.ts) in the same undoable step as the change, and tells the user, with a way to undo it.
  const livePointsRef = useRef(routePoints);
  const liveObservationsRef = useRef(observationMarkers);
  const maxObsDistRef = useRef(maxObsDist);
  const selectedIdRef = useRef(selectedId);
  useEffect(() => {
    livePointsRef.current = routePoints;
    liveObservationsRef.current = observationMarkers;
    maxObsDistRef.current = maxObsDist;
    selectedIdRef.current = selectedId;
  }, [routePoints, observationMarkers, maxObsDist, selectedId]);
  const showLegNotice = useCallback((message: string) => showToast(message, 'info', 5000), [showToast]);
  const [routeNotice, setRouteNotice] = useState<RouteNotice | null>(null);
  const noticeCounterRef = useRef(0);
  const dismissRouteNotice = useCallback(() => setRouteNotice(null), []);
  const changeRoutePoints = useCallback((update: React.SetStateAction<RoutePoint[]>) => {
    const plan = planRouteChange(livePointsRef.current, update, liveObservationsRef.current, maxObsDistRef.current);
    if (plan.points === livePointsRef.current) return;
    livePointsRef.current = plan.points;
    if (!hasRemoval(plan.removal)) {
      setRoutePoints(plan.points);
      return;
    }
    liveObservationsRef.current = plan.observationMarkers;
    const step = runUndoableStep(() => {
      setRoutePoints(plan.points);
      setObservationMarkers(plan.observationMarkers);
    });
    setIsDirty(true);
    const removedIds = new Set([...plan.removal.hiddenGates, ...plan.removal.photos].map((item) => item.id));
    if (selectedIdRef.current && removedIds.has(selectedIdRef.current)) {
      setSelectedId(null);
      setSelectionType(null);
    }
    noticeCounterRef.current += 1;
    setRouteNotice({
      id: noticeCounterRef.current,
      text: removalNotice(plan.removal, maxObsDistRef.current) ?? '',
      step,
    });
  }, [runUndoableStep]);

  // 2.A5: the generated map labels every shown point, so the points are numbered in the order the map shows them
  // (dummy legs included) instead of carrying generic names. Also renames an older route when it is opened. Done while
  // rendering, once per change of the points (https://react.dev/learn/you-might-not-need-an-effect), not in an effect.
  const [namedPoints, setNamedPoints] = useState<{ routePoints: RoutePoint[]; standalonePoints: RoutePoint[] } | null>(null);
  if (
    hasExtensionWaypoints
    && (namedPoints?.routePoints !== routePoints || namedPoints?.standalonePoints !== standalonePoints)
  ) {
    const named = nameUnknownLegsRoutePoints(routePoints, standalonePoints);
    setNamedPoints(named);
    if (named.routePoints !== routePoints || named.standalonePoints !== standalonePoints) {
      setRoutePoints(named.routePoints);
      setStandalonePoints(named.standalonePoints);
      setIsDirty(true);
    }
  }

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  useEffect(() => {
    routePointsRef.current = routePoints;
  }, [routePoints]);

  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isDirty]);

  const loadRouteData = useCallback((json: any) => {
    try {
      const parsed = parseRouteEditorFeatureCollection(json, standalonePointTypes);
      setRoutePoints(parsed.routePoints);
      setStandalonePoints(parsed.standalonePoints);
      setGates(parsed.gates);
      setObservationMarkers(parsed.observationMarkers);
      setPolygons(parsed.polygons);
      // A loaded route is where the history starts
      resetHistory();
      if (parsed.bounds) {
        setPendingBounds(parsed.bounds);
      }
    } catch (err) {
      console.error('Error parsing route data', err);
    }
  }, [standalonePointTypes, resetHistory]);

  useEffect(() => {
    if (mapInstance && pendingBounds) {
      const timer = setTimeout(() => {
        let map = mapInstance as any;
        if (map.current) map = map.current;
        if (map) map = map.map || map.leafletElement || (map.getMap ? map.getMap() : map);

        if (map && typeof map.fitBounds === 'function') {
          map.invalidateSize();
          map.fitBounds(pendingBounds, { padding: [0, 0], maxZoom: 16 });
          setPendingBounds(null);
        }
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [mapInstance, pendingBounds]);

  useEffect(() => {
    if (mapInstance && !paramRouteId) {
      (mapInstance as L.Map).locate({ setView: true, maxZoom: 11 });
    }
  }, [mapInstance, paramRouteId]);

  useEffect(() => {
    if (paramRouteId) {
      fetchRoute(parseInt(paramRouteId))
        .then(data => {
          if (data.settings) {
            if (typeof data.settings.showCorridor !== 'undefined') setShowCorridor(data.settings.showCorridor);
            if (typeof data.settings.maxObsDist !== 'undefined') setMaxObsDist(data.settings.maxObsDist);
            if (typeof data.settings.hideLabels !== 'undefined') setHideLabels(data.settings.hideLabels);
            if (typeof data.settings.selectedTaskTemplateId !== 'undefined') setSelectedTaskTemplateId(data.settings.selectedTaskTemplateId);
          }
          if (Array.isArray(data.intended_task_types)) {
            // What the author chose, as the backend reads it (an old pre-filled intent comes back empty).
            setIntent(emptyIntent(data.intended_task_types));
          }

          if (data.name) setRouteName(data.name);
          loadRouteData(data.route);
        })
        .catch(err => console.error(err));
    }
  }, [paramRouteId, loadRouteData]);

  // Live task-type compatibility, recomputed against the route's current in-memory content (not
  // yet saved) so the "Task types" settings panel can grey out unsupported types as the user
  // authors the route, without requiring a save first. display.services.route_compatibility on
  // the backend is the single source of truth for the ruleset.
  const compatibilityRoute = useMemo(() => buildRouteEditorSavePayload({
    routeName,
    routePoints,
    standalonePoints,
    gates,
    observationMarkers,
    polygons,
    showCorridor,
    maxObsDist,
    hideLabels,
    selectedTaskTemplateId,
    intendedTaskTypes,
  }).route, [
    routeName,
    routePoints,
    standalonePoints,
    gates,
    observationMarkers,
    polygons,
    showCorridor,
    maxObsDist,
    hideLabels,
    selectedTaskTemplateId,
    intendedTaskTypes,
  ]);

  useEffect(() => {
    const route = compatibilityRoute;
    let superseded = false;
    const timer = setTimeout(() => {
      fetchTaskCompatibility(route)
        .then((result) => {
          if (superseded) return;
          setTaskCompatibility(result);
          setCompatibilityAnswer({ route, failed: false });
        })
        .catch((err) => {
          console.error('Failed to check task type compatibility', err);
          if (!superseded) setCompatibilityAnswer({ route, failed: true });
        });
    }, 500);
    return () => {
      superseded = true;
      clearTimeout(timer);
    };
  }, [compatibilityRoute]);

  // The answer only counts for the route content it was computed for; any later edit makes it
  // 'pending' again until the debounced request returns.
  const compatibilityStatus: CompatibilityStatus = compatibilityAnswer && compatibilityAnswer.route === compatibilityRoute
    ? (compatibilityAnswer.failed ? 'failed' : 'ready')
    : 'pending';

  // The steps of the selected task: the backend's requirements with its verdict once it has answered for this route,
  // before that the catalogue's requirements with the editor's own counts.
  const selectedTemplate = getTaskTemplateById(selectedTaskTemplateId);
  const wizardChecklist = useMemo(() => (
    selectedTemplate
      ? buildWizardChecklist(
        selectedTemplate,
        taskCompatibility,
        subtypeCatalog,
        compatibilityStatus,
        (tool) => countForTool(tool, { routePoints, standalonePoints, gates, observationMarkers, polygons }),
      )
      : null
  ), [selectedTemplate, taskCompatibility, subtypeCatalog, compatibilityStatus, routePoints, standalonePoints, gates, observationMarkers, polygons]);

  // The most markers the active free-map step may place, from the backend's requirement for the step (null while the
  // requirements are not known: the backend still decides compatibility).
  const activeStepMaximum = findStep(wizardChecklist?.steps ?? [], activeGuideTool)?.maximum ?? null;

  const beginDummyBranchStep = useCallback((triggerId: string | null) => {
    const extension = findStep(wizardChecklist?.steps ?? [], 'extension_waypoint');
    const step = getToolWizardStep('extension_waypoint', extension?.label ?? 'Extension waypoints', extension?.help ?? getToolAction('extension_waypoint').prompt);
    if (!step) return;

    setActiveGuideTool('extension_waypoint');
    const transition = getWizardTransition(step, (item) => getToolAction(item.key as RouteRequirementTool).prompt);
    setPendingPointTypeSelection(null);
    setPendingPointFeatureTypeSelection(undefined);
    setCurrentWizardActionLabel(transition.currentWizardActionLabel);
    setWizardRouteInsertType(transition.wizardRouteInsertType as RoutePoint['type'] | null);
    setWizardRouteInsertFeatureType(transition.wizardRouteInsertFeatureType as RoutePoint['featureType'] | undefined);
    setWizardPolygonType(transition.wizardPolygonType as Polygon['type'] | null);
    setWizardPrompt(transition.routeInsertPrompt);
    setDummyBranchTriggerId(triggerId);
    setSelectionType('wizard');

    // A non-null triggerId is only ever handed in by a caller that already knows it names (or, for
    // the just-converted-to-'ul' case, is about to become) a valid trigger - checking it against
    // routePointsRef here would race the setRoutePoints() call convertSelectedBackbonePointToType
    // just made, since the ref only catches up after that render commits.
    setMode(triggerId ? 'add_point' : 'view');
  }, [wizardChecklist]);

  const handleMapClick = useCallback((latlng: LatLng) => {
    if (mode === 'view') {
      setSelectedId(null);
      setSelectionType(null);
      return;
    }

    if (mode === 'add_catalogue_turnpoint') {
      setStandalonePoints(prev => {
        const catalogueCount = prev.filter((point) => point.type === 'catalogue_turnpoint').length + 1;
        const newPoint = createCatalogueTurnpoint(latlng, catalogueCount);
        setSelectedId(null);
        if (selectionType !== 'wizard') {
          setSelectionType(null);
        }
        return [...prev, newPoint];
      });
      setIsDirty(true);
      return;
    }

    if (isCircleStandaloneTask && mode === 'add_point' && wizardRouteInsertType && standalonePointTypes.has(wizardRouteInsertType)) {
      const circleMarkerCount = standalonePoints.filter((point) => point.type === wizardRouteInsertType).length;
      const maxCircleMarkerCount = activeStepMaximum;
      if (maxCircleMarkerCount != null && circleMarkerCount >= maxCircleMarkerCount) {
        alert(`This circle task allows no more than ${maxCircleMarkerCount} ${wizardRouteInsertType.replace('circle_', '').replaceAll('_', ' ')} marker${maxCircleMarkerCount === 1 ? '' : 's'}.`);
        return;
      }
      const nextCircleMarkerCount = circleMarkerCount + 1;
      const wizardPointLabel = wizardRouteInsertType === 'circle_start'
        ? 'SP'
        : wizardRouteInsertType === 'circle_center'
          ? 'CM'
          : wizardRouteInsertType === 'circle_entry'
            ? 'X'
            : wizardRouteInsertType === 'circle_exit'
              ? 'WP'
              : currentWizardActionLabel;
      setStandalonePoints(prev => {
        const newPoint = createStandaloneWizardPoint(
          latlng,
          wizardRouteInsertType,
          wizardRouteInsertFeatureType,
          wizardPointLabel,
          nextCircleMarkerCount,
        );
        return [...prev, newPoint];
      });
      setIsDirty(true);
      return;
    }

    // 2.A6 / 2.B2: exactly three standalone timed turnpoints, no backbone.
    // Known time gates are free-map points whatever the task: the guide's tool places them so.
    if (mode === 'add_point' && wizardRouteInsertType === 'timed_turnpoint') {
      const timedTurnpointCount = standalonePoints.filter((point) => point.type === 'timed_turnpoint').length;
      const maxTimedTurnpointCount = activeStepMaximum;
      if (maxTimedTurnpointCount != null && timedTurnpointCount >= maxTimedTurnpointCount) {
        alert(`This task allows no more than ${maxTimedTurnpointCount} timed turnpoints.`);
        return;
      }
      const nextTimedTurnpointCount = timedTurnpointCount + 1;
      setStandalonePoints(prev => {
        const newPoint = createStandaloneWizardPoint(
          latlng,
          wizardRouteInsertType,
          wizardRouteInsertFeatureType,
          `CP${nextTimedTurnpointCount}`,
          nextTimedTurnpointCount,
        );
        return [...prev, newPoint];
      });
      setIsDirty(true);
      return;
    }

    if (mode === 'add_point') {
      if (wizardRouteInsertType && wizardRouteInsertFeatureType === 'dummy_branch_waypoint') {
        const selectedTrigger = routePoints.find((point) => point.id === dummyBranchTriggerId && isUnknownLegTrigger(point));
        if (!selectedTrigger) {
          return;
        }
        const siblingBranchPoints = standalonePoints.filter(
          (point) => point.featureType === 'dummy_branch_waypoint' && point.triggerPointId === selectedTrigger.id,
        );
        const newPoint = buildDummyBranchWaypoint(latlng, selectedTrigger, siblingBranchPoints);
        setStandalonePoints((prev) => [...prev, newPoint]);
        setIsDirty(true);
        return;
      }
      if (wizardRouteInsertType && routePoints.length >= 2) {
        const count = routePoints.filter((point) => point.type === wizardRouteInsertType).length + 1;
        changeRoutePoints(prev => {
          const newPoints = [...prev];
          const lastRoutePointIndex = newPoints.length - 1;
          const insertIndex = lastRoutePointIndex == null ? newPoints.length : lastRoutePointIndex;
          const newPoint = createInsertedRoutePoint(
            latlng,
            wizardRouteInsertType,
            wizardRouteInsertFeatureType,
            currentWizardActionLabel,
            count,
          );
          newPoints.splice(insertIndex, 0, newPoint);
          setSelectedId(newPoint.id);
          setSelectionType('point');
          return newPoints;
        });
        setIsDirty(true);
        setMode('view');
        setWizardRouteInsertType(null);
        setWizardRouteInsertFeatureType(undefined);
        setCurrentWizardActionLabel(null);
        setWizardPrompt(null);
        setActiveGuideTool(null);
        return;
      }

      changeRoutePoints(prev => {
        if (isThreePointBackboneTask && prev.length >= 3) {
          alert('This task template uses exactly three route backbone points: SP, MP, and FP. Add extra targets as standalone points instead.');
          return prev;
        }

        const newPoints = normalizeRoutePointsBeforeAppend(prev, isThreePointBackboneTask);
        const newPoint = createBackboneRoutePoint(latlng, newPoints, isThreePointBackboneTask, addCurveMode);
        return [...newPoints, newPoint];
      });
      setIsDirty(true);
      return;
    }

    if (mode.startsWith('add_landing') || mode.startsWith('add_takeoff')) {
      const gateType = mode.includes('landing') ? 'landing' : 'takeoff';

      if (!tempGatePoint) {
        setTempGatePoint(latlng);
      } else {
        const newGate = createTakeoffLandingGate(latlng, tempGatePoint, gateType, gates.length + 1);
        setGates(prev => [...prev, newGate]);
        setTempGatePoint(null);
        setMode('view');
        setIsDirty(true);
        // An active guide step ends itself now that the mode is back to select (see the effect on autoAdvance).
        if (!activeGuideTool) {
          setCurrentWizardActionLabel(null);
          setWizardPrompt(null);
        }
      }
      return;
    }

    if (mode === 'add_observation') {
      if (routePoints.length < 2) {
        alert('Route backbone must have at least 2 points to define lines.');
        return;
      }

      const minDist = getMinimumObservationDistance(latlng, routePoints);

      if (minDist > maxObsDist) {
        alert(`Observation markers must be within ${(maxObsDist / 1852).toFixed(2)} NM of the route line.`);
        return;
      }

      setObservationMarkers(prev => [...prev, createObservationMarker(latlng, prev.map(marker => marker.name))]);
      setIsDirty(true);
      return;
    }

    if (mode === 'add_polygon') {
      setTempPolygonPoints(prev => [...prev, latlng]);
      return;
    }
  }, [
    mode,
    routePoints,
    standalonePoints,
    gates.length,
    tempGatePoint,
    maxObsDist,
    addCurveMode,
    wizardRouteInsertType,
    wizardRouteInsertFeatureType,
    currentWizardActionLabel,
    isThreePointBackboneTask,
    isCircleStandaloneTask,
    activeStepMaximum,
    activeGuideTool,
    selectionType,
    dummyBranchTriggerId,
    standalonePointTypes,
    changeRoutePoints,
  ]);

  const updateSelectedPoint = (field: keyof RoutePoint, value: any) => {
    setIsDirty(true);
    history.noteEdit(`${selectedId}:${field}`);
    changeRoutePoints(points => {
      const index = points.findIndex(p => p.id === selectedId);
      if (index === -1) return points;

      const newPoints = [...points];
      newPoints[index] = { ...newPoints[index], [field]: value };
      // A point made a secret gate is checked and timed, as a new secret gate is
      if (field === 'type' && value === 'secret') {
        newPoints[index] = { ...newPoints[index], ...SECRET_GATE_CHECKS };
      }

      if (field === 'type' && value === 'secret' && index > 0 && index < newPoints.length - 1) {
        const prev = newPoints[index - 1];
        const current = newPoints[index];
        const next = newPoints[index + 1];

        if (current.segmentType === 'curved' || next.segmentType === 'curved') {
          return newPoints;
        }

        const bearingTotal = getBearing(prev, next);
        const distTotal = getDistance(prev, next);
        const distToCur = getDistance(prev, current);
        const bearingToCur = getBearing(prev, current);

        let angleDiff = bearingToCur - bearingTotal;
        while (angleDiff > 180) angleDiff -= 360;
        while (angleDiff < -180) angleDiff += 360;

        let projDist = distToCur * Math.cos(toRad(angleDiff));
        projDist = Math.max(0, Math.min(projDist, distTotal));

        const newLoc = getDestinationPoint(prev, projDist, bearingTotal);
        newPoints[index] = { ...current, lat: newLoc.lat, lng: newLoc.lng };
      }

      return newPoints;
    });
  };

  const updateSelectedStandalonePoint = (field: keyof RoutePoint, value: any) => {
    markDirty();
    history.noteEdit(`${selectedId}:${field}`);
    setStandalonePoints((points) => updateItemById(points, selectedId, (point) => ({ ...point, [field]: value })));
  };

  const updateSelectedGate = (field: keyof Gate, value: any) => {
    markDirty();
    history.noteEdit(`${selectedId}:${field}`);
    setGates((gatesState) => updateItemById(gatesState, selectedId, (gate) => ({ ...gate, [field]: value })));
  };

  const updateSelectedObservation = (field: keyof ObservationMarker, value: any) => {
    markDirty();
    history.noteEdit(`${selectedId}:${field}`);
    setObservationMarkers((markers) => updateItemById(markers, selectedId, (marker) => ({ ...marker, [field]: value })));
  };

  const updateSelectedPolygon = (field: keyof Polygon, value: any) => {
    markDirty();
    history.noteEdit(`${selectedId}:${field}`);
    setPolygons((polygonsState) => updateItemById(polygonsState, selectedId, (polygon) => ({ ...polygon, [field]: value })));
  };

  // A selected dummy-branch waypoint and the point its leg starts from (null when no dummy waypoint is selected)
  const selectedDummyPoint = selectionType === 'standalone_point'
    ? standalonePoints.find((point) => point.id === selectedId && point.featureType === 'dummy_branch_waypoint')
    : undefined;
  const selectedDummyPrevious = selectedDummyPoint
    ? previousOnDummyBranch(selectedDummyPoint, routePoints, standalonePoints)
    : undefined;
  // The point whose incoming leg Make Curved changes: a route point after the first, or a dummy-branch waypoint
  const curvablePoint = selectionType === 'point'
    ? routePoints.find((point, index) => point.id === selectedId && index > 0)
    : selectedDummyPrevious ? selectedDummyPoint : undefined;

  const curveDummyPoint = (update: (point: RoutePoint, previous: RoutePoint) => RoutePoint) => {
    if (!selectedDummyPoint || !selectedDummyPrevious) return;
    setIsDirty(true);
    setStandalonePoints((points) => points.map((point) => (
      point.id === selectedDummyPoint.id ? update(point, selectedDummyPrevious) : point
    )));
  };

  const toggleCurve = () => {
    if (selectedDummyPoint) {
      curveDummyPoint((point, previous) => (point.segmentType === 'curved'
        ? { ...point, segmentType: 'straight' }
        : { ...point, segmentType: 'curved', controlLat: (previous.lat + point.lat) / 2, controlLng: (previous.lng + point.lng) / 2 }));
      return;
    }
    setIsDirty(true);
    changeRoutePoints(points => {
      const index = points.findIndex(p => p.id === selectedId);
      if (index <= 0) return points;

      const newPoints = [...points];
      const p = newPoints[index];
      if (p.segmentType === 'curved') {
        newPoints[index] = { ...p, segmentType: 'straight' };
      } else {
        const prev = newPoints[index - 1];
        newPoints[index] = { ...p, segmentType: 'curved', controlLat: (prev.lat + p.lat) / 2, controlLng: (prev.lng + p.lng) / 2 };
      }
      return newPoints;
    });
  };

  const resetCurve = () => {
    if (selectedDummyPoint) {
      curveDummyPoint((point, previous) => ({
        ...point,
        controlLat: (previous.lat + point.lat) / 2 + (point.lng - previous.lng) * 0.2,
        controlLng: (previous.lng + point.lng) / 2 - (point.lat - previous.lat) * 0.2,
      }));
      return;
    }
    setIsDirty(true);
    changeRoutePoints(points => {
      const index = points.findIndex(p => p.id === selectedId);
      if (index <= 0) return points;

      const newPoints = [...points];
      const p = newPoints[index];
      const prev = newPoints[index - 1];
      const midLat = (prev.lat + p.lat) / 2;
      const midLng = (prev.lng + p.lng) / 2;
      const controlLat = midLat + (p.lng - prev.lng) * 0.2;
      const controlLng = midLng - (p.lat - prev.lat) * 0.2;

      newPoints[index] = { ...p, controlLat, controlLng };
      return newPoints;
    });
  };

  const deleteSelected = () => {
    markDirty();
    if (selectionType === 'point') {
      changeRoutePoints(normalizeDeletedBackboneRoutePoints(deleteItemById(routePoints, selectedId)));
    } else if (selectionType === 'standalone_point') {
      setStandalonePoints(deleteItemById(standalonePoints, selectedId));
    } else if (selectionType === 'gate') {
      setGates(deleteItemById(gates, selectedId));
    } else if (selectionType === 'observation') {
      setObservationMarkers(deleteItemById(observationMarkers, selectedId));
    } else if (selectionType === 'polygon') {
      setPolygons(deleteItemById(polygons, selectedId));
    }
    setSelectedId(null);
    setSelectionType(null);
  };

  const movePointOrder = (direction: 'up' | 'down') => {
    markDirty();
    if (selectionType === 'standalone_point') {
      setStandalonePoints(reorderItemsById(standalonePoints, selectedId, direction));
      return;
    }

    if (selectionType !== 'point') return;
    changeRoutePoints(reorderItemsById(routePoints, selectedId, direction));
  };

  const convertSelectedBackbonePointToType = useCallback((nextType: RoutePoint['type'], nextFeatureType: RoutePoint['featureType'] | undefined) => {
    if (!selectedId) return;
    markDirty();
    // Not through changeRoutePoints: this runs while rendering (see below), and the wizard only turns a point into an
    // unknown-leg point, which no hidden gate depends on
    setRoutePoints((points) => updateItemById(points, selectedId, (point) => ({
      ...point,
      type: nextType,
      featureType: nextFeatureType || point.featureType || 'route_waypoint',
    })));
    setPendingPointTypeSelection(null);
    setPendingPointFeatureTypeSelection(undefined);
    setSelectionType('point');
    if (nextType === 'ul') {
      beginDummyBranchStep(selectedId);
      return;
    }
    setCurrentWizardActionLabel(null);
    setWizardPrompt(null);
    setActiveGuideTool(null);
  }, [beginDummyBranchStep, markDirty, selectedId]);

  // A wizard step waiting for a backbone point to convert does so as soon as one is selected. Done while rendering
  // rather than in an effect; the conversion clears the pending selection, so it runs once.
  if (pendingPointTypeSelection && selectionType === 'point' && selectedId) {
    convertSelectedBackbonePointToType(pendingPointTypeSelection, pendingPointFeatureTypeSelection);
  }

  // Stops the active guide step and the tool it started. The route is not changed.
  const stopWizardAction = useCallback(() => {
    setMode('view');
    setWizardRouteInsertType(null);
    setWizardRouteInsertFeatureType(undefined);
    setWizardPolygonType(null);
    setCurrentWizardActionLabel(null);
    setPendingPointTypeSelection(null);
    setPendingPointFeatureTypeSelection(undefined);
    setDummyBranchTriggerId(null);
    setWizardPrompt(null);
    setActiveGuideTool(null);
  }, []);

  // Back to select mode from anywhere: stops the tool and the guide step, clears a half-drawn gate line or zone. The
  // route is not changed. Esc and the banner's and toolbar's select/stop buttons.
  const stopPlacing = useCallback(() => {
    stopWizardAction();
    setTempGatePoint(null);
    setTempPolygonPoints([]);
  }, [stopWizardAction]);

  // Starts the tool of a guide step: the toolbar mode or wizard action it stands for (see TOOL_ACTIONS).
  const startWizardStep = useCallback((tool: RouteRequirementTool) => {
    const state = findStep(wizardChecklist?.steps ?? [], tool);
    const action = getToolAction(tool);
    const label = state?.label ?? action.shortLabel;
    const help = state?.help || action.prompt;

    if (tool === 'extension_waypoint') {
      const selectedPoint = routePoints.find((point) => point.id === selectedId) ?? null;
      beginDummyBranchStep(selectedPoint && isUnknownLegTrigger(selectedPoint) ? selectedPoint.id : null);
      return;
    }

    const step = getToolWizardStep(tool, label, help);
    if (!step) {
      // No placing tool (curved_leg): nothing is selected and no mode starts; the banner shows how it is done.
      stopWizardAction();
      setActiveGuideTool(tool);
      setCurrentWizardActionLabel(help);
      setWizardPrompt(action.prompt);
      return;
    }

    const transition = getWizardTransition(step, () => action.prompt);
    if (!transition.preserveSelectedPoint) {
      setSelectedId(null);
    }
    setPendingPointTypeSelection(null);
    setPendingPointFeatureTypeSelection(undefined);
    setDummyBranchTriggerId(null);

    setActiveGuideTool(tool);
    setCurrentWizardActionLabel(transition.currentWizardActionLabel);
    setWizardRouteInsertType(transition.wizardRouteInsertType as RoutePoint['type'] | null);
    setWizardRouteInsertFeatureType(transition.wizardRouteInsertFeatureType as RoutePoint['featureType'] | undefined);
    setWizardPolygonType(transition.wizardPolygonType as Polygon['type'] | null);
    setWizardPrompt(transition.routeInsertPrompt ?? action.prompt);
    if (transition.selectExistingRouteType) {
      setPendingPointTypeSelection(transition.selectExistingRouteType);
      setPendingPointFeatureTypeSelection(transition.selectExistingRouteFeatureType as RoutePoint['featureType'] | undefined);
    }
    if (transition.nextSelectionType) {
      setSelectionType(transition.nextSelectionType);
    }
    if (transition.clearSelectionType && !transition.nextSelectionType) {
      setSelectionType(null);
    }
    if (transition.resetTempPolygonPoints) {
      setTempPolygonPoints([]);
    }
    if (transition.mode) {
      setMode(transition.mode);
    }
  }, [beginDummyBranchStep, routePoints, selectedId, stopWizardAction, wizardChecklist]);

  // The step ended (by the user or by itself): start the next unmet required step, or stop. All required steps met is
  // said in the panel and, for a guide that is closed, in a toast.
  const applyStepEnd = useCallback((end: StepEnd, announce: boolean) => {
    if (end.kind === 'start') {
      startWizardStep(end.tool);
      return;
    }
    stopWizardAction();
    if (end.kind === 'all_done' && announce) showToast('All required steps are done.', 'success');
  }, [showToast, startWizardStep, stopWizardAction]);

  // "Done, next step" in the panel and the banner.
  const finishWizardStep = useCallback(() => {
    if (!wizardChecklist) {
      stopWizardAction();
      return;
    }
    applyStepEnd(resolveStepEnd(wizardChecklist, activeGuideTool), true);
  }, [activeGuideTool, applyStepEnd, stopWizardAction, wizardChecklist]);

  // A step with a fixed count ends when its last one is placed; a single-shot tool (a polygon, a gate) when the mode
  // is back to select.
  // Done while rendering rather than in an effect; ending the step makes the condition false, so it runs once.
  const stepEnd = wizardChecklist ? autoAdvance(wizardChecklist, activeGuideTool, mode) : null;
  if (stepEnd) {
    applyStepEnd(stepEnd, false);
  }

  // A task was chosen (in the task choice or the guide's own list): the guide opens on it with its first unmet
  // required step active, as soon as the steps are known (the catalogue or the compatibility answer).
  const chooseTask = useCallback((id: string) => {
    stopWizardAction();
    setSelectedTaskTemplateId(id);
    // The chosen task is part of the route's intent, even while the route does not meet it yet.
    setIntent((previous) => applyGuideChoice(previous, getTaskTemplateById(id)?.subtype));
    setIsDirty(true);
    setTaskChoiceOpen(false);
    setSelectedId(null);
    setSelectionType('wizard');
    setStartFirstStep(true);
  }, [stopWizardAction]);

  const leaveTask = useCallback(() => {
    stopWizardAction();
    setSelectedTaskTemplateId(null);
    setIntent((previous) => applyGuideChoice(previous, null));
    setIsDirty(true);
    setStartFirstStep(false);
  }, [stopWizardAction]);

  // Closing the guide never changes the route; it only stops the active step.
  const closeWizard = useCallback(() => {
    stopWizardAction();
    setSelectedId(null);
    setSelectionType(null);
  }, [stopWizardAction]);

  // Also while rendering; starting clears the flag.
  if (startFirstStep && wizardChecklist && wizardChecklist.steps.length > 0) {
    setStartFirstStep(false);
    const first = nextUnmetRequiredStep(wizardChecklist.steps);
    if (first) startWizardStep(first.key);
  }

  useEffect(() => {
    if (wizardRouteInsertFeatureType !== 'dummy_branch_waypoint') {
      return;
    }
    if (selectionType !== 'point' || !selectedId) {
      return;
    }

    const selectedPoint = routePointsRef.current.find((point) => point.id === selectedId) ?? null;
    if (!selectedPoint || !isUnknownLegTrigger(selectedPoint)) {
      return;
    }

    setDummyBranchTriggerId(selectedPoint.id);
    setMode('add_point');
  }, [selectedId, selectionType, wizardRouteInsertFeatureType]);

  // The trigger being given dummy waypoints stopped being an unknown-leg trigger (deleted or converted): stop placing
  // them. Done while rendering rather than in an effect; clearing the trigger makes it run once.
  if (dummyBranchTriggerId && !isUnknownLegTrigger(routePoints.find((point) => point.id === dummyBranchTriggerId) ?? null)) {
    setDummyBranchTriggerId(null);
    if (wizardRouteInsertFeatureType === 'dummy_branch_waypoint') {
      setMode('view');
    }
  }

  // Esc, Ctrl/Cmd+Z, Ctrl/Cmd+Shift+Z and Ctrl+Y; not while typing in a field or with a modal open (editorKeyAction).
  const modalOpen = taskChoiceOpen || gateWidthsOpen;
  const somethingToStop = mode !== 'view' || !!activeGuideTool || !!currentWizardActionLabel || !!tempGatePoint || tempPolygonPoints.length > 0;
  const { undo: undoContent, redo: redoContent } = history;
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const action = editorKeyAction(event, modalOpen);
      if (!action) return;
      if (action === 'stop') {
        if (!somethingToStop) return;
        event.preventDefault();
        stopPlacing();
        return;
      }
      event.preventDefault();
      if (action === 'undo') undoContent();
      else redoContent();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [modalOpen, somethingToStop, stopPlacing, undoContent, redoContent]);

  const validationErrors = useMemo(() => validateRouteEditorState(
    routePoints,
    isThreePointBackboneTask,
    isCircleStandaloneTask,
    isTimedTurnpointStandaloneTask,
    isCurveRequiredTask,
  ).concat(
    observationPhotoNameProblems(routePoints, standalonePoints, observationMarkers),
  ).concat(
    hasExtensionWaypoints
      ? routePoints
          .filter((point) => point.type === 'ul')
          .flatMap((triggerPoint) => (
            standalonePoints.some((point) => point.featureType === 'dummy_branch_waypoint' && point.triggerPointId === triggerPoint.id)
              ? []
              : [`Unknown-leg trigger "${triggerPoint.name}" must have at least one dummy-branch waypoint.`]
          ))
      : []
  ), [routePoints, standalonePoints, observationMarkers, isThreePointBackboneTask, isCircleStandaloneTask, isTimedTurnpointStandaloneTask, isCurveRequiredTask, hasExtensionWaypoints]);

  const handleSave = async () => {
    if (!routeName || !routeName.trim()) {
      alert('Please enter a route name before saving.');
      return;
    }

    // Not to be saved anyway: the server refuses such a route
    const photoNameProblems = observationPhotoNameProblems(routePoints, standalonePoints, observationMarkers);
    if (photoNameProblems.length > 0) {
      alert(`The route cannot be saved:\n\n${photoNameProblems.join('\n')}`);
      return;
    }

    if (validationErrors.length > 0) {
      if (!confirm('Route has validation errors. Save anyway?')) return;
    }

    showToast('Remember to review the supported task types for this route before saving.', 'info');

    const payload: SavePayload = buildRouteEditorSavePayload({
      routeName,
      routePoints,
      standalonePoints,
      gates,
      observationMarkers,
      polygons,
      showCorridor,
      maxObsDist,
      hideLabels,
      selectedTaskTemplateId,
      intendedTaskTypes,
    });

    try {
      const result = await saveRoute(routeId, payload);

      showToast('Route saved.', 'success');
      setIsDirty(false);
      const savedRouteId = result.id ?? (routeId ? parseInt(routeId, 10) : null);
      if (savedRouteId) setCreateTaskPromptRouteId(savedRouteId);
      if (!routeId && result.id) {
        setCreatedRouteId(result.id.toString());
        navigate(generatePath('ROUTE_EDITOR_EDIT', { routeId: result.id }), { replace: true });
      }
    } catch (e) {
      console.error(e);
      showToast(`${e instanceof Error && e.message ? e.message : 'Error saving route.'} Your changes are still here.`, 'error');
    }
  };

  const handleReverseRoute = useCallback(() => {
    markDirty();
    // Reverse/renumber keeps backbone semantics stable for 3-point tasks:
    // after reversal the authored backbone is still normalized back to SP/MP/FP
    // before persistence, rather than preserving literal pre-reverse labels.
    changeRoutePoints((prevPoints) => reverseRoutePoints(prevPoints, isThreePointBackboneTask));
  }, [isThreePointBackboneTask, markDirty, changeRoutePoints]);

  const handleRenumberWaypoints = useCallback(() => {
    markDirty();
    changeRoutePoints((prev) => renumberRoutePoints(prev, isThreePointBackboneTask));
  }, [isThreePointBackboneTask, markDirty, changeRoutePoints]);

  const activeStepState = findStep(wizardChecklist?.steps ?? [], activeGuideTool);
  const dummyBranchPhase = getDummyBranchPhase(
    wizardRouteInsertFeatureType === 'dummy_branch_waypoint',
    dummyBranchTriggerId,
    routePoints,
  );
  const activeDummyTrigger = dummyBranchTriggerId
    ? routePoints.find((point) => point.id === dummyBranchTriggerId) ?? null
    : null;
  const bannerText = dummyBranchPhase !== 'idle'
    ? getWizardBannerText(dummyBranchPhase, activeDummyTrigger?.name)
    : null;
  const modeBanner = getModeBanner({
    mode,
    tempGatePoint,
    activeGuideTool,
    guidePrompt: bannerText?.instruction || wizardPrompt,
    legInsertType: wizardRouteInsertType,
  });
  const awaitingNonTriggerSelection = dummyBranchPhase === 'awaiting_trigger'
    && selectionType === 'point'
    && !!selectedId
    && !isUnknownLegTrigger(routePoints.find((point) => point.id === selectedId));

  return (
    <>
      <ToastContainer toasts={toasts} removeToast={removeToast} />
      {taskChoiceOpen && (
        <TaskChoiceModal
          visibleTaskTypeGroups={visibleTaskTypeGroups}
          onChoose={chooseTask}
          onClose={() => setTaskChoiceOpen(false)}
        />
      )}
      {createTaskPromptRouteId !== null && (
        <div className="toast toast-bottom toast-center z-[9998]">
          <div className="alert alert-info shadow-lg">
            <span>Next step: turn this route into a navigation task.</span>
            <Link
              to={`${generatePath('ROUTE_EDITOR_LIST', {})}?createTask=${createTaskPromptRouteId}`}
              className="btn btn-sm btn-primary"
            >
              Create navigation task
            </Link>
            <button className="btn btn-sm btn-ghost" onClick={() => setCreateTaskPromptRouteId(null)}>Later</button>
          </div>
        </div>
      )}
      <div className="flex w-full h-[calc(100vh-66px)] bg-base-200 font-sans text-base-content overflow-hidden">
      <div className="h-full overflow-y-auto shrink-0 max-w-xs">
        <Sidebar
          routePoints={routePoints}
          standalonePoints={standalonePoints}
          gates={gates}
          observationMarkers={observationMarkers}
          polygons={polygons}
          selectedId={selectedId}
          selectionType={selectionType}
          validationErrors={validationErrors}
          showCorridor={showCorridor}
          setShowCorridor={(val) => {
            setShowCorridor(val);
            setIsDirty(true);
          }}
          hideLabels={hideLabels}
          setHideLabels={(val) => {
            setHideLabels(val);
            setIsDirty(true);
          }}
          intendedTaskTypes={intendedTaskTypes}
          setIntendedTaskType={(key: string, checked: boolean) => {
            setIntent((previous) => applyManualTick(previous, key, checked));
            setIsDirty(true);
          }}
          taskCompatibility={taskCompatibility}
          compatibilityStatus={compatibilityStatus}
          setSelectedId={setSelectedId}
          setSelectionType={setSelectionType}
          updateSelectedPoint={selectionType === 'standalone_point' ? updateSelectedStandalonePoint : updateSelectedPoint}
          updateSelectedGate={updateSelectedGate}
          updateSelectedObservation={updateSelectedObservation}
          updateSelectedPolygon={updateSelectedPolygon}
          deleteSelected={deleteSelected}
          movePointOrder={movePointOrder}
          handleSave={handleSave}
          handleReverseRoute={handleReverseRoute}
          handleRenumberWaypoints={handleRenumberWaypoints}
          maxObsDist={maxObsDist}
          setMaxObsDist={(val) => {
            setMaxObsDist(val);
            setIsDirty(true);
          }}
          routeName={routeName}
          setRouteName={(name) => {
            setRouteName(name);
            setIsDirty(true);
          }}
          isAuthenticated={document.configuration.isAuthenticated}
          isDirty={isDirty}
          totalLength={totalLength}
          selectedTaskTemplateId={selectedTaskTemplateId}
          chooseTask={chooseTask}
          leaveTask={leaveTask}
          wizardChecklist={wizardChecklist}
          activeGuideTool={activeGuideTool}
          startWizardStep={startWizardStep}
          finishWizardStep={finishWizardStep}
          closeWizard={closeWizard}
          visibleTaskTypeGroups={visibleTaskTypeGroups}
        />
      </div>

      <div className="flex-1 flex flex-col relative">
        <Toolbar
          mode={mode}
          setMode={setMode}
          setTempGatePoint={setTempGatePoint}
          setTempPolygonPoints={setTempPolygonPoints}
          onSelect={stopPlacing}
          canUndo={history.canUndo}
          canRedo={history.canRedo}
          onUndo={undoContent}
          onRedo={redoContent}
          openWizard={() => { setSelectedId(null); setSelectionType('wizard'); }}
          openGateWidths={() => setGateWidthsOpen(true)}
        />
        <GateWidthModal
          isOpen={gateWidthsOpen}
          points={routePoints}
          onApply={(ids, widthMetres) => {
            setIsDirty(true);
            changeRoutePoints((points) => setWidthOfPoints(points, ids, widthMetres));
          }}
          onClose={() => setGateWidthsOpen(false)}
        />

        {modeBanner && (
          <MapModeBanner
            banner={modeBanner}
            title={bannerText?.title}
            onStop={stopPlacing}
            guideAction={activeGuideTool
              ? {
                label: activeStepState ? doneButtonLabel(activeStepState) : 'Done, next step',
                onDone: finishWizardStep,
                description: currentWizardActionLabel ?? undefined,
              }
              : null}
            dummyBranchPhase={dummyBranchPhase}
            awaitingNonTriggerSelection={awaitingNonTriggerSelection}
          />
        )}

        <MapCanvas
          ref={setMapInstance}
          routeId={routeId ? parseInt(routeId, 10) : null}
          routePoints={routePoints}
          standalonePoints={standalonePoints}
          gates={gates}
          observationMarkers={observationMarkers}
          polygons={polygons}
          selectedId={selectedId}
          selectionType={selectionType}
          mode={mode}
          tempGatePoint={tempGatePoint}
          tempPolygonPoints={tempPolygonPoints}
          showCorridor={showCorridor}
          hideLabels={hideLabels}
          wizardPolygonType={wizardPolygonType}
          legInsertType={legInsertTypeFor(mode, wizardRouteInsertType)}
          onNotice={showLegNotice}
          onEdit={markDirty}
          onDragGestureStart={history.beginGesture}
          onDragGestureEnd={history.endGesture}
          activeTriggerId={dummyBranchPhase === 'placing' ? dummyBranchTriggerId : null}
          emphasizeUnknownLegTriggers={dummyBranchPhase === 'awaiting_trigger'}
          setRoutePoints={changeRoutePoints}
          setStandalonePoints={setStandalonePoints}
          setGates={setGates}
          setObservationMarkers={setObservationMarkers}
          setPolygons={setPolygons}
          setSelectedId={setSelectedId}
          setSelectionType={setSelectionType}
          setMode={setMode}
          setTempPolygonPoints={setTempPolygonPoints}
          onMapClick={handleMapClick}
          maxObsDist={maxObsDist}
        />

        {routeNotice && (
          <RouteChangeNotice
            key={routeNotice.id}
            notice={routeNotice}
            onDismiss={dismissRouteNotice}
          />
        )}

        <div className="absolute bottom-4 left-4 z-[1000] flex flex-col gap-2">
          {mode === 'add_point' && (
            <div className="bg-base-100 p-2 rounded shadow flex items-center gap-2">
              <input
                type="checkbox"
                id="curveMode"
                className="checkbox checkbox-sm"
                checked={addCurveMode}
                onChange={(e) => setAddCurveMode(e.target.checked)}
                disabled={wizardRouteInsertType != null || isThreePointBackboneTask || isCircleStandaloneTask}
              />
              <label htmlFor="curveMode" className="text-sm font-bold">Add Curved Leg</label>
            </div>
          )}

          {curvablePoint && (
            <div className="bg-base-100 p-2 rounded shadow flex flex-col gap-2">
              <button onClick={toggleCurve} className="btn btn-sm btn-outline">
                {curvablePoint.segmentType === 'curved' ? 'Make Straight' : 'Make Curved'}
              </button>
              {curvablePoint.segmentType === 'curved' && (
                <button onClick={resetCurve} className="btn btn-xs btn-ghost">
                  Reset Curve Handle
                </button>
              )}
            </div>
          )}
        </div>
      </div>
      </div>
    </>
  );
}
