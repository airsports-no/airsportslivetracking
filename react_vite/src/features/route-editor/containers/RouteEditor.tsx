import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import Toolbar from '../components/Toolbar';
import MapCanvas from '../components/MapCanvas';
import { fetchRoute, saveRoute } from '../api';
import { SavePayload } from '../types';
import { generatePath } from '../../../urls';
import {
  getDistance,
  getBearing,
  getDestinationPoint,
  isCollinear,
  getDistanceFromLine,
  toRad,
  getQuadraticBezierPoints
} from '../../../utils/geoUtils';
import { RoutePoint, Gate, ObservationMarker, Polygon, LatLng, SelectionType, Mode } from '../../../types';
import { Map } from 'leaflet';
import { getTaskTemplateById, getWizardRouteInsertLabel } from '../taskTemplates';
import { createStandalonePointTypeSet, parseRouteEditorFeatureCollection } from '../routeDataParsing';
import {
  deleteItemById,
  normalizeDeletedBackboneRoutePoints,
  renumberRoutePoints,
  reorderItemsById,
  reverseRoutePoints,
  updateItemById,
} from '../routeEditorMutations';
import { buildRouteEditorSavePayload, validateRouteEditorState } from '../routeEditorValidation';
import {
  createBackboneRoutePoint,
  createCatalogueTurnpoint,
  createInsertedRoutePoint,
  createObservationMarker,
  createStandaloneWizardPoint,
  createTakeoffLandingGate,
  getMinimumObservationDistance,
  normalizeRoutePointsBeforeAppend,
} from '../routeEditorMapClickHelpers';
import { getWizardStep, getWizardTransition } from '../routeEditorWizardTransitions';

const getFreeMapStepMaxCount = (
  selectedTaskTemplateId: string | null,
  wizardRouteInsertType: RoutePoint['type'] | null,
  wizardRouteInsertFeatureType: RoutePoint['featureType'] | undefined,
) => {
  if (!selectedTaskTemplateId || !wizardRouteInsertType) return null;
  const template = getTaskTemplateById(selectedTaskTemplateId);
  const step = template?.steps.find((item) => (
    item.pointType === wizardRouteInsertType
    && item.featureType === wizardRouteInsertFeatureType
    && item.placement === 'free_map'
  ));
  return step?.maxCount ?? null;
};

const getAngleDiff = (a: number, b: number) => {
  let diff = a - b;
  while (diff > 180) diff -= 360;
  while (diff < -180) diff += 360;
  return diff;
};

export default function RouteEditor() {
  const [routePoints, setRoutePoints] = useState<RoutePoint[]>([]);
  const [gates, setGates] = useState<Gate[]>([]);
  const [observationMarkers, setObservationMarkers] = useState<ObservationMarker[]>([]);
  const [polygons, setPolygons] = useState<Polygon[]>([]);
  const [standalonePoints, setStandalonePoints] = useState<RoutePoint[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectionType, setSelectionType] = useState<SelectionType | null>(null);
  const [routeId, setRouteId] = useState<string | null>(null);
  const { routeId: paramRouteId } = useParams<{ routeId: string }>();
  const navigate = useNavigate();
  const [routeName, setRouteName] = useState('');
  const [isDirty, setIsDirty] = useState(false);

  const [mode, setMode] = useState<Mode>('view');
  const [tempGatePoint, setTempGatePoint] = useState<LatLng | null>(null);
  const [tempPolygonPoints, setTempPolygonPoints] = useState<LatLng[]>([]);
  const [showCorridor, setShowCorridor] = useState(false);
  const [addCurveMode, setAddCurveMode] = useState(false);
  const [maxObsDist, setMaxObsDist] = useState(926);
  const [hideLabels, setHideLabels] = useState(false);
  const [selectedTaskTemplateId, setSelectedTaskTemplateId] = useState<string | null>(null);
  const [wizardRouteInsertType, setWizardRouteInsertType] = useState<RoutePoint['type'] | null>(null);
  const [wizardRouteInsertFeatureType, setWizardRouteInsertFeatureType] = useState<RoutePoint['featureType'] | undefined>(undefined);
  const [wizardPolygonType, setWizardPolygonType] = useState<Polygon['type'] | null>(null);
  const [currentWizardActionLabel, setCurrentWizardActionLabel] = useState<string | null>(null);
  const [pendingPointTypeSelection, setPendingPointTypeSelection] = useState<RoutePoint['type'] | null>(null);
  const [pendingPointFeatureTypeSelection, setPendingPointFeatureTypeSelection] = useState<RoutePoint['featureType'] | undefined>(undefined);
  const visibleTaskTypeGroups = useMemo(() => {
    const groups = document.configuration.visibleTaskTypeGroups;
    if (Array.isArray(groups) && groups.length > 0) {
      return groups;
    }
    return document.configuration.showCimaTaskTypes ? ['legacy', 'cima'] : ['legacy'];
  }, []);

  const isThreePointBackboneTask = useMemo(
    () => ['cima_a3'].includes(selectedTaskTemplateId || ''),
    [selectedTaskTemplateId],
  );

  const isCircleStandaloneTask = selectedTaskTemplateId === 'cima_a7';
  // 2.A6 and 2.B2 have no route backbone at all: the route is exactly three
  // free-map timed turnpoints (known_time_gate markers) plus any number of
  // untimed catalogue turnpoints, all as standalone points.
  const isTimedTurnpointStandaloneTask = selectedTaskTemplateId === 'cima_a6' || selectedTaskTemplateId === 'cima_b2';
  const isCurveRequiredTask = selectedTaskTemplateId === 'cima_a1';
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
  const [mapInstance, setMapInstance] = useState<Map | null>(null);
  const [pendingBounds, setPendingBounds] = useState<L.LatLngBoundsExpression | null>(null);

  const markDirty = useCallback(() => setIsDirty(true), []);

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

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
      if (parsed.bounds) {
        setPendingBounds(parsed.bounds);
      }
    } catch (err) {
      console.error('Error parsing route data', err);
    }
  }, [standalonePointTypes]);

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
      setRouteId(paramRouteId);
      fetchRoute(parseInt(paramRouteId))
        .then(data => {
          if (data.settings) {
            if (typeof data.settings.showCorridor !== 'undefined') setShowCorridor(data.settings.showCorridor);
            if (typeof data.settings.maxObsDist !== 'undefined') setMaxObsDist(data.settings.maxObsDist);
            if (typeof data.settings.hideLabels !== 'undefined') setHideLabels(data.settings.hideLabels);
            if (typeof data.settings.selectedTaskTemplateId !== 'undefined') setSelectedTaskTemplateId(data.settings.selectedTaskTemplateId);
          }

          if (data.name) setRouteName(data.name);
          loadRouteData(data.route);
        })
        .catch(err => console.error(err));
    }
  }, [paramRouteId, loadRouteData]);

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
      const maxCircleMarkerCount = getFreeMapStepMaxCount(selectedTaskTemplateId, wizardRouteInsertType, wizardRouteInsertFeatureType);
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
    if (isTimedTurnpointStandaloneTask && mode === 'add_point' && wizardRouteInsertType === 'timed_turnpoint') {
      const timedTurnpointCount = standalonePoints.filter((point) => point.type === 'timed_turnpoint').length;
      const maxTimedTurnpointCount = getFreeMapStepMaxCount(selectedTaskTemplateId, wizardRouteInsertType, wizardRouteInsertFeatureType);
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
        const selectedTrigger = routePoints.find((point) => point.id === selectedId && point.type === 'ul');
        if (!selectedTrigger) {
          alert('Select an unknown-leg trigger on the backbone before adding dummy-branch waypoints. Keep the trigger selected, then click Add again.');
          return;
        }
        const siblingBranchPoints = standalonePoints.filter(
          (point) => point.featureType === 'dummy_branch_waypoint' && point.triggerPointId === selectedTrigger.id
        );
        const branchSequence = siblingBranchPoints.length;
        const newPoint = createStandaloneWizardPoint(
          latlng,
          wizardRouteInsertType,
          wizardRouteInsertFeatureType,
          siblingBranchPoints.length === 0 ? `${selectedTrigger.name}-D1` : `${selectedTrigger.name}-D${siblingBranchPoints.length + 1}`,
          siblingBranchPoints.length + 1,
        );
        setStandalonePoints((prev) => [...prev, {
          ...newPoint,
          triggerPointId: selectedTrigger.id,
          branchSequence,
          isTiming: false,
          isPassing: true,
        }]);
        setIsDirty(true);
        setSelectionType('wizard');
        return;
      }
      if (wizardRouteInsertType && routePoints.length >= 2) {
        const count = routePoints.filter((point) => point.type === wizardRouteInsertType).length + 1;
        setRoutePoints(prev => {
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
        return;
      }

      setRoutePoints(prev => {
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
        setCurrentWizardActionLabel(null);
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

      setObservationMarkers(prev => [...prev, createObservationMarker(latlng, prev.length + 1)]);
      setIsDirty(true);
      setCurrentWizardActionLabel(null);
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
    isTimedTurnpointStandaloneTask,
    selectedTaskTemplateId,
    selectionType,
  ]);

  const updateSelectedPoint = (field: keyof RoutePoint, value: any) => {
    setIsDirty(true);
    setRoutePoints(points => {
      const index = points.findIndex(p => p.id === selectedId);
      if (index === -1) return points;

      const newPoints = [...points];
      newPoints[index] = { ...newPoints[index], [field]: value };

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
    setStandalonePoints((points) => updateItemById(points, selectedId, (point) => ({ ...point, [field]: value })));
  };

  const convertSelectedBackbonePointToType = (nextType: RoutePoint['type'], nextFeatureType: RoutePoint['featureType'] | undefined) => {
    if (!selectedId) return;
    markDirty();
    setRoutePoints((points) => updateItemById(points, selectedId, (point) => ({
      ...point,
      type: nextType,
      featureType: nextFeatureType || point.featureType || 'route_waypoint',
    })));
    setPendingPointTypeSelection(null);
    setPendingPointFeatureTypeSelection(undefined);
    setCurrentWizardActionLabel(null);
    setSelectionType('point');
  };

  const updateSelectedGate = (field: keyof Gate, value: any) => {
    markDirty();
    setGates((gatesState) => updateItemById(gatesState, selectedId, (gate) => ({ ...gate, [field]: value })));
  };

  const updateSelectedObservation = (field: keyof ObservationMarker, value: any) => {
    markDirty();
    setObservationMarkers((markers) => updateItemById(markers, selectedId, (marker) => ({ ...marker, [field]: value })));
  };

  const updateSelectedPolygon = (field: keyof Polygon, value: any) => {
    markDirty();
    setPolygons((polygonsState) => updateItemById(polygonsState, selectedId, (polygon) => ({ ...polygon, [field]: value })));
  };

  const toggleCurve = () => {
    setIsDirty(true);
    setRoutePoints(points => {
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
    setIsDirty(true);
    setRoutePoints(points => {
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
      setRoutePoints(normalizeDeletedBackboneRoutePoints(deleteItemById(routePoints, selectedId)));
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
    setRoutePoints(reorderItemsById(routePoints, selectedId, direction));
  };

  useEffect(() => {
    if (!pendingPointTypeSelection || selectionType !== 'point' || !selectedId) {
      return;
    }
    convertSelectedBackbonePointToType(pendingPointTypeSelection, pendingPointFeatureTypeSelection);
  }, [pendingPointFeatureTypeSelection, pendingPointTypeSelection, selectedId, selectionType]);

  const startWizardStep = useCallback((stepKey: string) => {
    const template = getTaskTemplateById(selectedTaskTemplateId);
    const step = getWizardStep(template, stepKey);
    if (!step) return;

    const transition = getWizardTransition(step, getWizardRouteInsertLabel);
    if (!transition.preserveSelectedPoint) {
      setSelectedId(null);
    }
    setPendingPointTypeSelection(null);
    setPendingPointFeatureTypeSelection(undefined);

    setCurrentWizardActionLabel(transition.currentWizardActionLabel);
    setWizardRouteInsertType(transition.wizardRouteInsertType as RoutePoint['type'] | null);
    setWizardRouteInsertFeatureType(transition.wizardRouteInsertFeatureType as RoutePoint['featureType'] | undefined);
    setWizardPolygonType(transition.wizardPolygonType as Polygon['type'] | null);
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
    if (transition.routeInsertPrompt) {
      alert(transition.routeInsertPrompt);
    }
    if (transition.mode) {
      setMode(transition.mode);
    }
  }, [selectedTaskTemplateId]);

  const validationErrors = useMemo(() => validateRouteEditorState(
    routePoints,
    isThreePointBackboneTask,
    isCircleStandaloneTask,
    isTimedTurnpointStandaloneTask,
    isCurveRequiredTask,
  ).concat(
    selectedTaskTemplateId === 'cima_a5'
      ? routePoints
          .filter((point) => point.type === 'ul')
          .flatMap((triggerPoint) => (
            standalonePoints.some((point) => point.featureType === 'dummy_branch_waypoint' && point.triggerPointId === triggerPoint.id)
              ? []
              : [`Unknown-leg trigger "${triggerPoint.name}" must have at least one dummy-branch waypoint.`]
          ))
      : []
  ), [routePoints, standalonePoints, isThreePointBackboneTask, isCircleStandaloneTask, isTimedTurnpointStandaloneTask, isCurveRequiredTask, selectedTaskTemplateId]);

  const stopWizardAction = useCallback(() => {
    setMode('view');
    setWizardRouteInsertType(null);
    setWizardRouteInsertFeatureType(undefined);
    setWizardPolygonType(null);
    setCurrentWizardActionLabel(null);
    setPendingPointTypeSelection(null);
    setPendingPointFeatureTypeSelection(undefined);
  }, []);

  const handleSave = async () => {
    if (!routeName || !routeName.trim()) {
      alert('Please enter a route name before saving.');
      return;
    }

    if (validationErrors.length > 0) {
      if (!confirm('Route has validation errors. Save anyway?')) return;
    }

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
    });

    try {
      const result = await saveRoute(routeId, payload);

      alert('Route saved successfully!');
      setIsDirty(false);
      if (!routeId && result.id) {
        setRouteId(result.id.toString());
        navigate(generatePath('ROUTE_EDITOR_EDIT', { routeId: result.id }), { replace: true });
      }
    } catch (e) {
      console.error(e);
      alert('Error saving route');
    }
  };

  const handleReverseRoute = useCallback(() => {
    markDirty();
    // Reverse/renumber keeps backbone semantics stable for 3-point tasks:
    // after reversal the authored backbone is still normalized back to SP/MP/FP
    // before persistence, rather than preserving literal pre-reverse labels.
    setRoutePoints((prevPoints) => reverseRoutePoints(prevPoints, isThreePointBackboneTask));
  }, [isThreePointBackboneTask, markDirty]);

  const handleRenumberWaypoints = useCallback(() => {
    markDirty();
    setRoutePoints((prev) => renumberRoutePoints(prev, isThreePointBackboneTask));
  }, [isThreePointBackboneTask, markDirty]);

  return (
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
          setSelectedTaskTemplateId={(id) => {
            setSelectedTaskTemplateId(id);
            setIsDirty(true);
          }}
          startWizardStep={startWizardStep}
          stopWizardAction={stopWizardAction}
          currentWizardActionLabel={currentWizardActionLabel}
          visibleTaskTypeGroups={visibleTaskTypeGroups}
        />
      </div>

      <div className="flex-1 flex flex-col relative">
        <Toolbar
          mode={mode}
          setMode={setMode}
          tempGatePoint={tempGatePoint}
          setTempGatePoint={setTempGatePoint}
          setTempPolygonPoints={setTempPolygonPoints}
          openWizard={() => { setSelectedId(null); setSelectionType('wizard'); }}
        />

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
          setRoutePoints={setRoutePoints}
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

          {selectedId && selectionType === 'point' && routePoints.findIndex(p => p.id === selectedId) > 0 && (
            <div className="bg-base-100 p-2 rounded shadow flex flex-col gap-2">
              <button onClick={toggleCurve} className="btn btn-sm btn-outline">
                {routePoints.find(p => p.id === selectedId)?.segmentType === 'curved' ? 'Make Straight' : 'Make Curved'}
              </button>
              {routePoints.find(p => p.id === selectedId)?.segmentType === 'curved' && (
                <button onClick={resetCurve} className="btn btn-xs btn-ghost">
                  Reset Curve Handle
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
