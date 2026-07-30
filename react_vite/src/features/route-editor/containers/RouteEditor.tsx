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

const getAngleDiff = (a: number, b: number) => {
  let diff = a - b;
  while (diff > 180) diff -= 360;
  while (diff < -180) diff += 360;
  return diff;
};

const THREE_POINT_BACKBONE_TEMPLATE: Array<Pick<RoutePoint, 'name' | 'type' | 'featureType'>> = [
  { name: 'SP', type: 'sp', featureType: 'route_waypoint' },
  { name: 'MP', type: 'tp', featureType: 'route_waypoint' },
  { name: 'FP', type: 'fp', featureType: 'route_waypoint' },
];

const CIRCLE_STANDALONE_TYPES = new Set<RoutePoint['type']>([
  'circle_center',
  'circle_start',
  'circle_entry',
  'circle_exit',
]);

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

  const isThreePointBackboneTask = useMemo(
    () => ['cima_a3', 'cima_a6', 'cima_b2'].includes(selectedTaskTemplateId || ''),
    [selectedTaskTemplateId],
  );

  const isCircleStandaloneTask = selectedTaskTemplateId === 'cima_a7';
  const standalonePointTypes = useMemo(() => {
    const types = new Set<RoutePoint['type']>(['catalogue_turnpoint']);
    if (isCircleStandaloneTask) {
      CIRCLE_STANDALONE_TYPES.forEach((type) => types.add(type));
    }
    return types;
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
      const newPoints: RoutePoint[] = [];
      const newStandalone: RoutePoint[] = [];
      const newGates: Gate[] = [];
      const newObs: ObservationMarker[] = [];
      const newPolys: Polygon[] = [];

      if (json.type === 'FeatureCollection') {
        const features = json.features;

        const pointFeatures = features.filter((f: any) => (
          f.geometry.type === 'Point' && [
            'route_waypoint',
            'catalogue_turnpoint',
            'circle_center_marker',
            'circle_start_marker',
            'circle_entry_marker',
            'circle_exit_marker',
            'known_time_gate',
            'hidden_gate'
          ].includes(f.properties.featureType)
        )).sort((a: any, b: any) => (a.properties.sequence ?? 999999) - (b.properties.sequence ?? 999999));

        pointFeatures.forEach((f: any) => {
          const parsedPoint = {
            id: f.properties.id || crypto.randomUUID(),
            lat: f.geometry.coordinates[1],
            lng: f.geometry.coordinates[0],
            name: f.properties.name || 'Unnamed',
            type: f.properties.pointType || 'tp',
            featureType: f.properties.featureType || 'route_waypoint',
            segmentType: f.properties.segmentType || 'straight',
            controlLat: f.properties.controlLat,
            controlLng: f.properties.controlLng,
            width: f.properties.width || 1852,
            isTiming: typeof f.properties.isTiming === 'boolean' ? f.properties.isTiming : true,
            isPassing: typeof f.properties.isPassing === 'boolean' ? f.properties.isPassing : true,
            scoreValue: f.properties.scoreValue ?? null,
          } as RoutePoint;
          if (standalonePointTypes.has(parsedPoint.type)) {
            newStandalone.push(parsedPoint);
          } else {
            newPoints.push(parsedPoint);
          }
        });

        const gateFeatures = features.filter((f: any) => f.geometry.type === 'LineString' && f.properties.gateType);
        gateFeatures.forEach((f: any) => {
          newGates.push({
            id: f.properties.id || crypto.randomUUID(),
            name: f.properties.name || 'Gate',
            type: f.properties.gateType,
            p1: { lng: f.geometry.coordinates[0][0], lat: f.geometry.coordinates[0][1] },
            p2: { lng: f.geometry.coordinates[1][0], lat: f.geometry.coordinates[1][1] },
            width: f.properties.width || 50
          });
        });

        const obsFeatures = features.filter((f: any) => f.geometry.type === 'Point' && f.properties.featureType === 'observation_photo');
        obsFeatures.forEach((f: any) => {
          newObs.push({
            id: f.properties.id || crypto.randomUUID(),
            lat: f.geometry.coordinates[1],
            lng: f.geometry.coordinates[0],
            name: f.properties.name || 'Obs',
            targetName: f.properties.targetName || ''
          });
        });

        const polyFeatures = features.filter((f: any) => f.geometry.type === 'Polygon' && (f.properties.featureType === 'zone' || f.properties.featureType === 'waypoint_polygon'));
        polyFeatures.forEach((f: any) => {
          const coords = f.geometry.coordinates[0];
          if (coords.length > 0 && coords[0][0] === coords[coords.length - 1][0] && coords[0][1] === coords[coords.length - 1][1]) {
            coords.pop();
          }
          const polygonType = f.properties.polygonType || 'prohibited';
          if (polygonType !== 'waypoint') {
            newPolys.push({
              id: f.properties.id || crypto.randomUUID(),
              name: f.properties.name || 'Zone',
              type: polygonType as Polygon['type'],
              points: coords.map((c: any) => ({ lng: c[0], lat: c[1] }))
            });
          }
        });

        setRoutePoints(newPoints);
        setStandalonePoints(newStandalone);
        setGates(newGates);
        setObservationMarkers(newObs);
        setPolygons(newPolys);

        let minLat = Infinity;
        let maxLat = -Infinity;
        let minLng = Infinity;
        let maxLng = -Infinity;
        let hasPoints = false;

        const extend = (lat: number, lng: number) => {
          if (lat < minLat) minLat = lat;
          if (lat > maxLat) maxLat = lat;
          if (lng < minLng) minLng = lng;
          if (lng > maxLng) maxLng = lng;
          hasPoints = true;
        };

        newPoints.forEach(p => extend(p.lat, p.lng));
        newStandalone.forEach(p => extend(p.lat, p.lng));
        newGates.forEach(g => {
          extend(g.p1.lat, g.p1.lng);
          extend(g.p2.lat, g.p2.lng);
        });
        newObs.forEach(o => extend(o.lat, o.lng));
        newPolys.forEach(p => p.points.forEach(pt => extend(pt.lat, pt.lng)));

        if (hasPoints) {
          setPendingBounds([[minLat, minLng], [maxLat, maxLng]]);
        }
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
        const newPoint: RoutePoint = {
          id: crypto.randomUUID(),
          lat: latlng.lat,
          lng: latlng.lng,
          name: `TP ${catalogueCount}`,
          type: 'catalogue_turnpoint',
          featureType: 'catalogue_turnpoint',
          width: 1852,
          isTiming: false,
          isPassing: true,
          isSecret: false,
          segmentType: 'straight',
          scoreValue: null,
        };
        setSelectedId(null);
        setSelectionType(null);
        return [...prev, newPoint];
      });
      setIsDirty(true);
      return;
    }

    if (isCircleStandaloneTask && mode === 'add_point' && wizardRouteInsertType && CIRCLE_STANDALONE_TYPES.has(wizardRouteInsertType)) {
      setStandalonePoints(prev => {
        const newPoint: RoutePoint = {
          id: crypto.randomUUID(),
          lat: latlng.lat,
          lng: latlng.lng,
          name: currentWizardActionLabel || `${wizardRouteInsertType}`,
          type: wizardRouteInsertType,
          featureType: wizardRouteInsertFeatureType,
          width: 1852,
          isTiming: false,
          isPassing: true,
          isSecret: false,
          segmentType: 'straight',
        };
        setSelectedId(newPoint.id);
        setSelectionType('standalone_point');
        return [...prev, newPoint];
      });
      setIsDirty(true);
      setMode('view');
      setWizardRouteInsertType(null);
      setWizardRouteInsertFeatureType(undefined);
      setCurrentWizardActionLabel(null);
      return;
    }

    if (mode === 'add_point') {
      if (wizardRouteInsertType && routePoints.length >= 2) {
        const count = routePoints.filter((point) => point.type === wizardRouteInsertType).length + 1;
        setRoutePoints(prev => {
          const newPoints = [...prev];
          const lastRoutePointIndex = newPoints.length - 1;
          const insertIndex = lastRoutePointIndex == null ? newPoints.length : lastRoutePointIndex;
          const newPoint: RoutePoint = {
            id: crypto.randomUUID(),
            lat: latlng.lat,
            lng: latlng.lng,
            name: currentWizardActionLabel || `${wizardRouteInsertType} ${count}`,
            type: wizardRouteInsertType,
            featureType: wizardRouteInsertFeatureType,
            width: 1852,
            isTiming: wizardRouteInsertType === 'known_time_gate',
            isPassing: true,
            isSecret: false,
            segmentType: 'straight',
          };
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
        const newPoints = [...prev];
        if (isThreePointBackboneTask && newPoints.length >= 3) {
          alert('This task template uses exactly three route backbone points: SP, MP, and FP. Add extra targets as standalone points instead.');
          return prev;
        }

        const count = newPoints.length;

        if (!isThreePointBackboneTask && count > 0) {
          const lastRoutePointIndex = newPoints.length - 1;
          if (lastRoutePointIndex != null && newPoints[lastRoutePointIndex].type === 'fp') {
            newPoints[lastRoutePointIndex] = { ...newPoints[lastRoutePointIndex], type: 'tp', featureType: 'route_waypoint', name: `WP ${count}` };
          }
        }

        let segmentType: 'straight' | 'curved' = 'straight';
        let controlLat = 0;
        let controlLng = 0;

        if (addCurveMode && count > 0) {
          const prevPoint = newPoints[count - 1];
          segmentType = 'curved';
          const midLat = (prevPoint.lat + latlng.lat) / 2;
          const midLng = (prevPoint.lng + latlng.lng) / 2;
          controlLat = midLat + (latlng.lng - prevPoint.lng) * 0.2;
          controlLng = midLng - (latlng.lat - prevPoint.lat) * 0.2;
        }

        const templatePoint = isThreePointBackboneTask ? THREE_POINT_BACKBONE_TEMPLATE[count] : null;
        const newPoint: RoutePoint = {
          id: crypto.randomUUID(),
          lat: latlng.lat,
          lng: latlng.lng,
          name: templatePoint?.name || (count === 0 ? 'Start' : 'Finish'),
          type: templatePoint?.type || (count === 0 ? 'sp' : 'fp'),
          featureType: templatePoint?.featureType || 'route_waypoint',
          width: 1852,
          isTiming: true,
          isPassing: true,
          isSecret: false,
          segmentType,
          controlLat,
          controlLng
        };
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
        const newGate: Gate = {
          id: crypto.randomUUID(),
          name: `${gateType === 'landing' ? 'L' : 'TO'} Gate ${gates.length + 1}`,
          type: gateType,
          p1: tempGatePoint,
          p2: latlng,
          width: 50
        };
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

      let minDist = Infinity;
      for (let i = 0; i < routePoints.length - 1; i++) {
        const p1 = routePoints[i];
        const p2 = routePoints[i + 1];
        let d = Infinity;

        if (p2.segmentType === 'curved' && p2.controlLat != null && p2.controlLng != null) {
          const steps = 20;
          let prevPoint: LatLng = { lat: p1.lat, lng: p1.lng };
          for (let j = 1; j <= steps; j++) {
            const t = j / steps;
            const invT = 1 - t;
            const lat = (invT * invT * p1.lat) + (2 * invT * t * p2.controlLat) + (t * t * p2.lat);
            const lng = (invT * invT * p1.lng) + (2 * invT * t * p2.controlLng) + (t * t * p2.lng);
            const curr: LatLng = { lat, lng };
            const segDist = getDistanceFromLine(latlng, prevPoint, curr);
            if (segDist < d) d = segDist;
            prevPoint = curr;
          }
        } else {
          d = getDistanceFromLine(latlng, p1, p2);
        }

        if (d < minDist) minDist = d;
      }

      if (minDist > maxObsDist) {
        alert(`Observation markers must be within ${(maxObsDist / 1852).toFixed(2)} NM of the route line.`);
        return;
      }

      setObservationMarkers(prev => [...prev, {
        id: crypto.randomUUID(),
        lat: latlng.lat,
        lng: latlng.lng,
        name: `Obs ${prev.length + 1}`,
        targetName: '',
      }]);
      setIsDirty(true);
      setCurrentWizardActionLabel(null);
      return;
    }

    if (mode === 'add_polygon') {
      setTempPolygonPoints(prev => [...prev, latlng]);
      return;
    }
  }, [mode, routePoints, gates.length, tempGatePoint, maxObsDist, addCurveMode, wizardRouteInsertType, wizardRouteInsertFeatureType, currentWizardActionLabel, isThreePointBackboneTask, isCircleStandaloneTask]);

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
    setIsDirty(true);
    setStandalonePoints(points => points.map(point => {
      if (point.id !== selectedId) return point;
      return { ...point, [field]: value };
    }));
  };

  const updateSelectedGate = (field: keyof Gate, value: any) => {
    setIsDirty(true);
    setGates(gts => gts.map(g => {
      if (g.id !== selectedId) return g;
      return { ...g, [field]: value };
    }));
  };

  const updateSelectedObservation = (field: keyof ObservationMarker, value: any) => {
    setIsDirty(true);
    setObservationMarkers(markers => markers.map(m => {
      if (m.id !== selectedId) return m;
      return { ...m, [field]: value };
    }));
  };

  const updateSelectedPolygon = (field: keyof Polygon, value: any) => {
    setIsDirty(true);
    setPolygons(polys => polys.map(p => {
      if (p.id !== selectedId) return p;
      return { ...p, [field]: value };
    }));
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
    setIsDirty(true);
    if (selectionType === 'point') {
      const newPoints = routePoints.filter(p => p.id !== selectedId);
      if (newPoints.length > 0) {
        newPoints[0] = { ...newPoints[0], type: 'sp', featureType: 'route_waypoint', name: 'SP' };
        newPoints[newPoints.length - 1] = { ...newPoints[newPoints.length - 1], type: 'fp', featureType: 'route_waypoint', name: 'FP' };
      }
      setRoutePoints(newPoints);
    } else if (selectionType === 'standalone_point') {
      setStandalonePoints(standalonePoints.filter(p => p.id !== selectedId));
    } else if (selectionType === 'gate') {
      setGates(gates.filter(g => g.id !== selectedId));
    } else if (selectionType === 'observation') {
      setObservationMarkers(observationMarkers.filter(m => m.id !== selectedId));
    } else if (selectionType === 'polygon') {
      setPolygons(polygons.filter(p => p.id !== selectedId));
    }
    setSelectedId(null);
    setSelectionType(null);
  };

  const movePointOrder = (direction: 'up' | 'down') => {
    setIsDirty(true);
    if (selectionType === 'standalone_point') {
      const idx = standalonePoints.findIndex(p => p.id === selectedId);
      if (idx === -1) return;
      const newPoints = [...standalonePoints];
      if (direction === 'up' && idx > 0) {
        [newPoints[idx], newPoints[idx - 1]] = [newPoints[idx - 1], newPoints[idx]];
      } else if (direction === 'down' && idx < newPoints.length - 1) {
        [newPoints[idx], newPoints[idx + 1]] = [newPoints[idx + 1], newPoints[idx]];
      }
      setStandalonePoints(newPoints);
      return;
    }

    if (selectionType !== 'point') return;
    const idx = routePoints.findIndex(p => p.id === selectedId);
    if (idx === -1) return;

    const newPoints = [...routePoints];
    if (direction === 'up' && idx > 0) {
      [newPoints[idx], newPoints[idx - 1]] = [newPoints[idx - 1], newPoints[idx]];
    } else if (direction === 'down' && idx < newPoints.length - 1) {
      [newPoints[idx], newPoints[idx + 1]] = [newPoints[idx + 1], newPoints[idx]];
    }
    setRoutePoints(newPoints);
  };

  const startWizardStep = useCallback((stepKey: string) => {
    const template = getTaskTemplateById(selectedTaskTemplateId);
    const step = template?.steps.find((item) => item.key === stepKey);
    if (!step) return;

    setSelectedId(null);

    if (step.kind === 'route') {
      setCurrentWizardActionLabel(step.help);
      setMode('add_point');
      return;
    }

    if (step.kind === 'point') {
      setCurrentWizardActionLabel(step.help);
      if (step.placement === 'route_insert') {
        setWizardRouteInsertType(step.pointType ?? null);
        setWizardRouteInsertFeatureType(step.featureType);
        alert(getWizardRouteInsertLabel(step));
        setMode('add_point');
        return;
      }

      if (step.featureType === 'catalogue_turnpoint') {
        setSelectionType(null);
        setMode('add_catalogue_turnpoint');
        return;
      }

      return;
    }

    if (step.kind === 'observation') {
      setCurrentWizardActionLabel(step.help);
      setMode('add_observation');
      return;
    }

    if (step.kind === 'takeoff_gate') {
      setCurrentWizardActionLabel(step.help);
      setMode('add_takeoff');
      return;
    }

    if (step.kind === 'landing_gate') {
      setCurrentWizardActionLabel(step.help);
      setMode('add_landing');
      return;
    }

    if (step.kind === 'polygon') {
      setCurrentWizardActionLabel(step.help);
      setWizardPolygonType(step.polygonType ?? null);
      setTempPolygonPoints([]);
      setMode('add_polygon');
    }
  }, [selectedTaskTemplateId]);

  const validationErrors = useMemo(() => {
    const errors: string[] = [];

    if (!isCircleStandaloneTask) {
      if (routePoints.length < 2) {
        errors.push('Route must have at least 2 backbone points.');
      } else {
        if (routePoints[0].type !== 'sp') errors.push("First route backbone point must be type 'Start'.");
        if (routePoints[routePoints.length - 1].type !== 'fp') errors.push("Last route backbone point must be type 'Finish'.");

        for (let i = 1; i < routePoints.length - 1; i++) {
          if (routePoints[i].type === 'sp') errors.push(`Backbone point ${i + 1} cannot be Start (middle of route).`);
          if (routePoints[i].type === 'fp') errors.push(`Backbone point ${i + 1} cannot be Finish (middle of route).`);
        }
      }
    }

    if (isThreePointBackboneTask && routePoints.length !== 3) {
      errors.push('This task requires exactly three route backbone points: SP, MP, and FP.');
    }

    if (isCircleStandaloneTask && routePoints.length > 0) {
      errors.push('Circle tasks should not use a route backbone. Place all circle markers as standalone points.');
    }

    routePoints.forEach((p, i) => {
      if (p.type === 'secret') {
        if (i === 0 || i === routePoints.length - 1) {
          errors.push(`Secret point "${p.name}" cannot be Start or Finish.`);
        } else {
          const prev = routePoints[i - 1];
          const next = routePoints[i + 1];
          const isCurved = p.segmentType === 'curved' || next.segmentType === 'curved';

          if (!isCurved && !isCollinear(prev, p, next)) {
            errors.push(`Secret point "${p.name}" is not on a straight line between previous and next points.`);
          }
        }
      }
    });

    if (!isCircleStandaloneTask && routePoints.length >= 3) {
      for (let i = 1; i < routePoints.length - 1; i++) {
        const p = routePoints[i];

        if (p.name.startsWith('Curve')) continue;

        const prev = routePoints[i - 1];
        const next = routePoints[i + 1];

        const b1 = getBearing(prev, p);
        const b2 = getBearing(p, next);
        const diff = getAngleDiff(b2, b1);

        const miterFactor = Math.min(1 / Math.cos(toRad(diff / 2)), 5);
        const miterLength = (p.width / 2) * miterFactor;

        const distPrev = getDistance(prev, p);
        const distNext = getDistance(p, next);

        if (miterLength > distPrev) {
          errors.push(`Waypoint "${p.name}" turn is too sharp for the corridor width and the previous leg length (${(distPrev / 1852).toFixed(2)} NM). Rendering may break.`);
        } else if (miterLength > distPrev * 0.7) {
          errors.push(`Waypoint "${p.name}" turn is nearly too sharp for the previous leg. Rendering might be distorted.`);
        }

        if (miterLength > distNext) {
          const msg = `Waypoint "${p.name}" turn is too sharp for the corridor width and the next leg length (${(distNext / 1852).toFixed(2)} NM). Rendering may break.`;
          if (!errors.includes(msg)) errors.push(msg);
        } else if (miterLength > distNext * 0.7) {
          const msg = `Waypoint "${p.name}" turn is nearly too sharp for the next leg. Rendering might be distorted.`;
          if (!errors.includes(msg)) errors.push(msg);
        }
      }
    }

    return errors;
  }, [routePoints, isThreePointBackboneTask, isCircleStandaloneTask]);

  const handleSave = async () => {
    if (!routeName || !routeName.trim()) {
      alert('Please enter a route name before saving.');
      return;
    }

    if (validationErrors.length > 0) {
      if (!confirm('Route has validation errors. Save anyway?')) return;
    }

    const routePathCoordinates = routePoints.map(p => [p.lng, p.lat]);

    const geoJson = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: { featureType: 'route_path' },
          geometry: {
            type: 'LineString',
            coordinates: routePathCoordinates
          }
        },
        ...routePoints.map((p, i) => ({
          type: 'Feature',
          properties: {
            id: p.id,
            name: p.name,
            pointType: p.type,
            featureType: p.featureType || 'route_waypoint',
            segmentType: p.segmentType || 'straight',
            controlLat: p.controlLat,
            controlLng: p.controlLng,
            width: p.width,
            isTiming: p.isTiming,
            isPassing: p.isPassing,
            scoreValue: p.scoreValue ?? undefined,
            sequence: i
          },
          geometry: {
            type: 'Point',
            coordinates: [p.lng, p.lat]
          }
        })),
        ...standalonePoints.map((p, i) => ({
          type: 'Feature',
          properties: {
            id: p.id,
            name: p.name,
            pointType: p.type,
            featureType: p.featureType,
            segmentType: p.segmentType || 'straight',
            width: p.width,
            isTiming: p.isTiming,
            isPassing: p.isPassing,
            scoreValue: p.scoreValue ?? undefined,
            sequence: routePoints.length + i
          },
          geometry: {
            type: 'Point',
            coordinates: [p.lng, p.lat]
          }
        })),
        ...gates.map(g => ({
          type: 'Feature',
          properties: {
            id: g.id,
            name: g.name,
            gateType: g.type,
            featureType: g.type === 'landing' ? 'landing_gate' : 'takeoff_gate',
            width: g.width
          },
          geometry: {
            type: 'LineString',
            coordinates: [
              [g.p1.lng, g.p1.lat],
              [g.p2.lng, g.p2.lat]
            ]
          }
        })),
        ...observationMarkers.map(m => ({
          type: 'Feature',
          properties: {
            id: m.id,
            name: m.name,
            targetName: m.targetName || undefined,
            featureType: 'observation_photo'
          },
          geometry: { type: 'Point', coordinates: [m.lng, m.lat] }
        })),
        ...polygons.map(p => ({
          type: 'Feature',
          properties: {
            id: p.id,
            name: p.name,
            polygonType: p.type,
            featureType: 'zone'
          },
          geometry: {
            type: 'Polygon',
            coordinates: [
              [...p.points.map(pt => [pt.lng, pt.lat]), [p.points[0].lng, p.points[0].lat]]
            ]
          }
        }))
      ]
    };

    const payload: SavePayload = {
      name: routeName,
      route: geoJson,
      settings: {
        showCorridor: showCorridor,
        maxObsDist: maxObsDist,
        hideLabels: hideLabels,
        selectedTaskTemplateId,
      }
    };

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
    setIsDirty(true);
    setRoutePoints(prevPoints => {
      if (prevPoints.length < 2) {
        return prevPoints;
      }

      const reversedPoints = [...prevPoints].reverse();
      const segmentInfo = prevPoints.slice(1).map(p => ({
        segmentType: p.segmentType,
        controlLat: p.controlLat,
        controlLng: p.controlLng
      }));
      const reversedSegmentInfo = segmentInfo.reverse();

      const newPoints = reversedPoints.map((point, index) => {
        const newPoint = { ...point };

        if (index === 0) {
          newPoint.type = 'sp';
          newPoint.name = 'SP';
        } else if (index === reversedPoints.length - 1) {
          newPoint.type = 'fp';
          newPoint.name = 'FP';
        } else if (isThreePointBackboneTask && index === 1) {
          newPoint.type = 'tp';
          newPoint.name = 'MP';
        } else if (newPoint.type !== 'secret') {
          newPoint.type = 'tp';
        }

        if (index > 0) {
          const segment = reversedSegmentInfo[index - 1];
          newPoint.segmentType = segment.segmentType || 'straight';
          newPoint.controlLat = segment.controlLat;
          newPoint.controlLng = segment.controlLng;
        } else {
          newPoint.segmentType = 'straight';
          delete newPoint.controlLat;
          delete newPoint.controlLng;
        }

        return newPoint;
      });

      return renumberPoints(newPoints);
    });
  }, [isThreePointBackboneTask]);

  const renumberPoints = (points: RoutePoint[]) => {
    let wpCounter = 0;
    let secretCounter = 1;

    return points.map((p, index) => {
      const newPoint = { ...p };
      if (index === 0) {
        newPoint.type = 'sp';
        newPoint.name = 'SP';
        wpCounter = 0;
        secretCounter = 1;
      } else if (index === points.length - 1) {
        newPoint.type = 'fp';
        newPoint.name = 'FP';
      } else if (isThreePointBackboneTask && index === 1) {
        newPoint.type = 'tp';
        newPoint.name = 'MP';
      } else if (p.type === 'secret') {
        newPoint.name = `Secret ${wpCounter}.${secretCounter++}`;
      } else {
        wpCounter++;
        newPoint.name = `WP ${wpCounter}`;
        if (newPoint.featureType === 'route_waypoint' || !newPoint.featureType) {
          newPoint.type = 'tp';
        }
        secretCounter = 1;
      }
      return newPoint;
    });
  };

  const handleRenumberWaypoints = useCallback(() => {
    setIsDirty(true);
    setRoutePoints(prev => renumberPoints(prev));
  }, [isThreePointBackboneTask]);

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
          currentWizardActionLabel={currentWizardActionLabel}
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
