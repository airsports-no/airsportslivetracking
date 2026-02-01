import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import Toolbar from '../components/Toolbar';
import MapCanvas from '../components/MapCanvas';
import { fetchRoute, saveRoute } from '../api';
import { RouteData, SavePayload } from '../types';
import {
  getDistance,
  getBearing,
  getDestinationPoint,
  isCollinear,
  getDistanceFromLine,
  toRad
} from '../../../utils/geoUtils';
import { RoutePoint, Gate, ObservationMarker, Polygon, LatLng, SelectionType, Mode } from '../../../types';
import { Map } from 'leaflet';
import L from 'leaflet';


/**
 * MAIN COMPONENT
 */
export default function RouteEditor() {
  // --- STATE ---
  const [routePoints, setRoutePoints] = useState<RoutePoint[]>([]);
  const [standalonePoints, setStandalonePoints] = useState<RoutePoint[]>([]);
  const [gates, setGates] = useState<Gate[]>([]);
  const [observationMarkers, setObservationMarkers] = useState<ObservationMarker[]>([]);
  const [polygons, setPolygons] = useState<Polygon[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectionType, setSelectionType] = useState<SelectionType | null>(null);
  const [routeId, setRouteId] = useState<string | null>(null);
  const { routeId: paramRouteId } = useParams<{ routeId: string }>();
  const [routeName, setRouteName] = useState("");
  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Modes: 'view', 'add_point', 'add_landing...', 'add_takeoff...', 'add_observation', 'add_polygon'
  const [mode, setMode] = useState<Mode>('view');
  const [tempGatePoint, setTempGatePoint] = useState<LatLng | null>(null);
  const [tempPolygonPoints, setTempPolygonPoints] = useState<LatLng[]>([]);
  const [showCorridor, setShowCorridor] = useState(false);
  const [addCurveMode, setAddCurveMode] = useState(false);
  const [maxObsDist, setMaxObsDist] = useState(926); // Default 0.5 NM
  const [hideLabels, setHideLabels] = useState(false);
  

  const modeRef = useRef(mode);
  const mapRef = useRef<Map | null>(null);
  const [mapInstance, setMapInstance] = useState<Map | null>(null);
  const handleMapRef = useCallback((map: Map | null) => {
    mapRef.current = map;
    setMapInstance(map);
  }, []);
  const [pendingBounds, setPendingBounds] = useState<L.LatLngBoundsExpression | null>(null);

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  // --- WARN ON UNSAVED CHANGES (Browser Navigation) ---
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

  // --- LOAD ROUTE ---
  const loadRouteData = useCallback((json: any) => {
    try {
      const newPoints: RoutePoint[] = [];
      const newStandalone: RoutePoint[] = [];
      const newGates: Gate[] = [];
      const newObs: ObservationMarker[] = [];
      const newPolys: Polygon[] = [];

      if (json.type === 'FeatureCollection') {
        // Parse Features
        const features = json.features;

        // Filter Points
        const pointFeatures = features.filter((f: any) => f.geometry.type === 'Point' && f.properties.featureType !== 'observation_photo').sort((a: any, b: any) => a.properties.sequence - b.properties.sequence);

        pointFeatures.forEach((f: any) => {
          const pt: RoutePoint = {
            id: f.properties.id || crypto.randomUUID(),
            lat: f.geometry.coordinates[1],
            lng: f.geometry.coordinates[0],
            name: f.properties.name || "Unnamed",
            type: f.properties.pointType || 'tp',
            segmentType: f.properties.segmentType || 'straight',
            controlLat: f.properties.controlLat,
            controlLng: f.properties.controlLng,
            width: f.properties.width || 1852,
            isTiming: f.properties.isTiming || false,
            isPassing: f.properties.isPassing || true,
            radius: f.properties.radius,
            groupId: f.properties.groupId
          };
          if (pt.type === 'free_point' || pt.type === 'circle_center' || pt.type === 'circle_entry') {
            newStandalone.push(pt);
          } else {
            newPoints.push(pt);
          }
        });

        // Filter Gates
        const gateFeatures = features.filter((f: any) => f.geometry.type === 'LineString' && f.properties.gateType);
        gateFeatures.forEach((f: any) => {
          newGates.push({
            id: f.properties.id || crypto.randomUUID(),
            name: f.properties.name || "Gate",
            type: f.properties.gateType,
            p1: { lng: f.geometry.coordinates[0][0], lat: f.geometry.coordinates[0][1] },
            p2: { lng: f.geometry.coordinates[1][0], lat: f.geometry.coordinates[1][1] },
            width: f.properties.width || 50
          });
        });

        // Filter Observation Markers
        const obsFeatures = features.filter((f: any) => f.geometry.type === 'Point' && f.properties.featureType === 'observation_photo');
        obsFeatures.forEach((f: any) => {
          newObs.push({
            id: f.properties.id || crypto.randomUUID(),
            lat: f.geometry.coordinates[1],
            lng: f.geometry.coordinates[0],
            name: f.properties.name || "Obs"
          });
        });

        // Filter Polygons
        const polyFeatures = features.filter((f: any) => f.geometry.type === 'Polygon' && (f.properties.featureType === 'zone' || f.properties.featureType === 'waypoint_polygon'));
        polyFeatures.forEach((f: any) => {
          const coords = f.geometry.coordinates[0]; // Outer ring
          // Remove last point if it duplicates first (GeoJSON standard)
          if (coords.length > 0 && coords[0][0] === coords[coords.length - 1][0] && coords[0][1] === coords[coords.length - 1][1]) {
            coords.pop();
          }
          newPolys.push({
            id: f.properties.id || crypto.randomUUID(),
            name: f.properties.name || "Zone",
            type: f.properties.featureType === 'waypoint_polygon' ? 'waypoint' : (f.properties.polygonType || 'prohibited'),
            points: coords.map((c: any) => ({ lng: c[0], lat: c[1] }))
          });
        });

        setRoutePoints(newPoints);
        setStandalonePoints(newStandalone);
        setGates(newGates);
        setObservationMarkers(newObs);
        setPolygons(newPolys);

        // Zoom to fit imported content
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
      console.error("Error parsing route data", err);
    }
  }, []);

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
      // Only locate user if map is ready and no route is being loaded (new route)
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
          }

          if (data.route && data.name) {
            setRouteName(data.name);
            loadRouteData(data.route);
          } else {
            if (data.name) setRouteName(data.name);
            loadRouteData(data.route);
          }
        })
        .catch(err => console.error(err));
    }
  }, [paramRouteId, loadRouteData]);

  // --- HANDLERS (Defined before Map Logic to be used in deps) ---

  const handleMapClick = useCallback((latlng: LatLng) => {
    if (mode === 'view') {
      setSelectedId(null);
      setSelectionType(null);
      return;
    }

    if (mode === 'add_point') {
      setRoutePoints(prev => {
        const newPoints = [...prev];
        const count = newPoints.length;

        // If extending route, convert previous 'fp' to 'tp'
        if (count > 0) {
          const lastIndex = count - 1;
          if (newPoints[lastIndex].type === 'fp') {
            newPoints[lastIndex] = { ...newPoints[lastIndex], type: 'tp', name: `WP ${count}` };
          }
        }

        let segmentType: "straight" | "curved" = 'straight';
        let controlLat = 0;
        let controlLng = 0;

        if (addCurveMode && count > 0) {
          const prev = newPoints[count - 1];
          segmentType = 'curved';
          // Default control point: Offset from midpoint
          const midLat = (prev.lat + latlng.lat) / 2;
          const midLng = (prev.lng + latlng.lng) / 2;
          controlLat = midLat + (latlng.lng - prev.lng) * 0.2;
          controlLng = midLng - (latlng.lat - prev.lat) * 0.2;
        }

        const newPoint: RoutePoint = {
          id: crypto.randomUUID(),
          lat: latlng.lat,
          lng: latlng.lng,
          name: count === 0 ? 'Start' : 'Finish',
          type: count === 0 ? 'sp' : 'fp',
          width: 1852, // 1 NM
          isTiming: false,
          isPassing: true,
          isSecret: false,
          segmentType,
          controlLat,
          controlLng
        };
        return [...newPoints, newPoint];
      });
      setIsDirty(true);
    }

    if (mode.startsWith('add_landing') || mode.startsWith('add_takeoff')) {
      const gateType = mode.includes('landing') ? 'landing' : 'takeoff';

      if (!tempGatePoint) {
        // First point of the gate
        setTempGatePoint(latlng);
      } else {
        // Second point of the gate
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
      }
    }

    if (mode === 'add_observation') {
      if (routePoints.length < 2) {
        alert("Route must have at least 2 points to define lines.");
        return;
      }

      let minDist = Infinity;
      for (let i = 0; i < routePoints.length - 1; i++) {
        const p1 = routePoints[i];
        const p2 = routePoints[i + 1];
        let d = Infinity;

        if (p2.segmentType === 'curved' && p2.controlLat != null && p2.controlLng != null) {
          // Approximate curve distance
          const steps = 20;
          let prev = p1;
          for (let j = 1; j <= steps; j++) {
            const t = j / steps;
            const invT = 1 - t;
            // Quadratic Bezier formula
            const lat = (invT * invT * p1.lat) + (2 * invT * t * p2.controlLat) + (t * t * p2.lat);
            const lng = (invT * invT * p1.lng) + (2 * invT * t * p2.controlLng) + (t * t * p2.lng);
            const curr = { lat, lng };
            const segDist = getDistanceFromLine(latlng, prev, curr);
            if (segDist < d) d = segDist;
            prev = curr;
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
      }]);
      setIsDirty(true);
    }

    if (mode === 'add_circle') {
      const newPoint: RoutePoint = {
        id: crypto.randomUUID(),
        lat: latlng.lat,
        lng: latlng.lng,
        name: `Circle ${standalonePoints.filter(p => p.type === 'circle_center').length + 1}`,
        type: 'circle_center',
        width: 0,
        isTiming: false,
        isPassing: true,
        segmentType: 'straight',
        radius: 500, // Default 500m
        groupId: crypto.randomUUID()
      };
      setStandalonePoints(prev => [...prev, newPoint]);
      setIsDirty(true);
      setMode('view'); 
    }

    if (mode === 'add_free_point') {
      const newPoint: RoutePoint = {
        id: crypto.randomUUID(),
        lat: latlng.lat,
        lng: latlng.lng,
        name: `FP ${standalonePoints.filter(p => p.type === 'free_point').length + 1}`,
        type: 'free_point',
        width: 0,
        isTiming: false,
        isPassing: true,
        segmentType: 'straight'
      };
      setStandalonePoints(prev => [...prev, newPoint]);
      setIsDirty(true);
    }

    if (mode === 'add_polygon') {
      setTempPolygonPoints(prev => [...prev, latlng]);
    }
  }, [mode, routePoints, standalonePoints, gates.length, tempGatePoint, observationMarkers.length, polygons.length, addCurveMode]);

  const updateSelectedPoint = (field: keyof RoutePoint, value: any) => {
    setIsDirty(true);
    setRoutePoints(points => {
      const index = points.findIndex(p => p.id === selectedId);
      if (index === -1) return points;

      const newPoints = [...points];
      newPoints[index] = { ...newPoints[index], [field]: value };

      // Auto-straighten if changing to secret
      if (field === 'type' && value === 'secret' && index > 0 && index < newPoints.length - 1) {
        const prev = newPoints[index - 1];
        const current = newPoints[index];
        const next = newPoints[index + 1];

        // Skip if connected to a curved segment
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
    setStandalonePoints(points => points.map(p => {
      if (p.id !== selectedId) return p;
      return { ...p, [field]: value };
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
      if (index <= 0) return points; // Cannot curve start point

      const newPoints = [...points];
      const p = newPoints[index];
      if (p.segmentType === 'curved') {
        newPoints[index] = { ...p, segmentType: 'straight' };
      } else {
        const prev = newPoints[index - 1];
        // Initialize control point
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

      // Reset to midpoint offset
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
      const idxInRoute = routePoints.findIndex(p => p.id === selectedId);
      if (idxInRoute !== -1) {
        const newPoints = routePoints.filter(p => p.id !== selectedId);
        if (newPoints.length > 0) {
          if (idxInRoute === 0) {
            newPoints[0] = { ...newPoints[0], type: 'sp', name: 'Start' };
          } else if (idxInRoute === routePoints.length - 1) {
            newPoints[newPoints.length - 1] = { ...newPoints[newPoints.length - 1], type: 'fp', name: 'Finish' };
          }
        }
        setRoutePoints(newPoints);
      } else {
        setStandalonePoints(prev => prev.filter(p => p.id !== selectedId));
      }
    } else if (selectionType === 'observation') {
      setObservationMarkers(observationMarkers.filter(m => m.id !== selectedId));
    } else if (selectionType === 'polygon') {
      setPolygons(polygons.filter(p => p.id !== selectedId));
    } else {
      setGates(gates.filter(g => g.id !== selectedId));
    }
    setSelectedId(null);
    setSelectionType(null);
  };

  const movePointOrder = (direction: "up" | "down") => {
    setIsDirty(true);
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

  // --- VALIDATION LOGIC ---
  const validationErrors = useMemo(() => {
    const errors: string[] = [];
    
    // CIMA: Standalone points (free_point, circle_center) are NOT part of the sequential spine.
    const spine = routePoints.filter(p => p.type !== 'free_point' && p.type !== 'circle_center');

    if (spine.length < 2) {
      errors.push("Route must have at least 2 sequential points (Start and Finish).");
    } else {
      if (spine[0].type !== 'sp') errors.push("First sequential point must be type 'Start'.");
      if (spine[spine.length - 1].type !== 'fp') errors.push("Last sequential point must be type 'Finish'.");

      // Check for Start/Finish in middle
      for (let i = 1; i < spine.length - 1; i++) {
        if (spine[i].type === 'sp') errors.push(`Point "${spine[i].name}" cannot be Start (middle of route).`);
        if (spine[i].type === 'fp') errors.push(`Point "${spine[i].name}" cannot be Finish (middle of route).`);
      }
    }

    // Secret Point Linearity Check
    spine.forEach((p, i) => {
      if (p.type === 'secret') {
        if (i === 0 || i === spine.length - 1) {
          errors.push(`Secret point "${p.name}" cannot be Start or Finish.`);
        } else {
          const prev = spine[i - 1];
          const next = spine[i + 1];
          const isCurved = p.segmentType === 'curved' || next.segmentType === 'curved';

          if (!isCurved && !isCollinear(prev, p, next)) {
            errors.push(`Secret point "${p.name}" is not on a straight line between previous and next points.`);
          }
        }
      }
    });

    // CIMA Structural Integrity Checks
    const circleCenters = routePoints.filter(p => p.type === 'circle_center');
    const circleEntries = routePoints.filter(p => p.type === 'circle_entry');
    if (circleCenters.length > 0 && circleEntries.length === 0) {
      errors.push("Route contains a Circle Center but no Circle Entry point.");
    }

    const speedStarts = routePoints.filter(p => p.type === 'speed_start');
    const speedEnds = routePoints.filter(p => p.type === 'speed_end');
    speedStarts.forEach(s => {
      const match = speedEnds.find(e => e.groupId === s.groupId);
      if (!match) errors.push(`Speed Start "${s.name}" (Group ${s.groupId}) has no matching Speed End.`);
    });

    return errors;
  }, [routePoints]);


  const handleFit = useCallback(() => {
    if (!mapInstance) return;
    const all: LatLng[] = [
      ...routePoints,
      ...standalonePoints,
      ...observationMarkers,
      ...gates.flatMap(g => [g.p1, g.p2]),
      ...polygons.flatMap(p => p.points)
    ];
    if (all.length === 0) return;

    const lats = all.map(p => p.lat);
    const lngs = all.map(p => p.lng);
    const bounds = L.latLngBounds(
      [Math.min(...lats), Math.min(...lngs)],
      [Math.max(...lats), Math.max(...lngs)]
    );
    mapInstance.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 });
  }, [mapInstance, routePoints, standalonePoints, observationMarkers, gates, polygons]);


  // --- SAVE ---
  const handleSave = async () => {
    if (!routeName || !routeName.trim()) {
      alert("Please enter a route name before saving.");
      return;
    }

    if (validationErrors.length > 0) {
      if (!confirm("Route has validation errors. Save anyway?")) return;
    }

    setIsSaving(true);
    const geoJson = {
      type: "FeatureCollection",
      features: [
        // Route Line
        {
          type: "Feature",
          properties: { featureType: "route_path" },
          geometry: {
            type: "LineString",
            coordinates: routePoints.map(p => [p.lng, p.lat])
          }
        },
        // Points (Spine)
        ...routePoints.map((p, i) => ({
          type: "Feature",
          properties: {
            id: p.id,
            name: p.name,
            pointType: p.type,
            featureType: "route_waypoint",
            segmentType: p.segmentType || 'straight',
            controlLat: p.controlLat,
            controlLng: p.controlLng,
            width: p.width,
            isTiming: p.isTiming,
            isPassing: p.isPassing,
            sequence: i,
            radius: p.radius,
            groupId: p.groupId
          },
          geometry: {
            type: "Point",
            coordinates: [p.lng, p.lat]
          }
        })),
        // Standalone CIMA Points
        ...standalonePoints.map((p, i) => ({
          type: "Feature",
          properties: {
            id: p.id,
            name: p.name,
            pointType: p.type,
            featureType: "standalone_waypoint",
            segmentType: 'straight',
            width: p.width,
            isTiming: p.isTiming,
            isPassing: p.isPassing,
            sequence: i + routePoints.length, // Keep a sequence for order tracking
            radius: p.radius,
            groupId: p.groupId
          },
          geometry: {
            type: "Point",
            coordinates: [p.lng, p.lat]
          }
        })),
        // Gates
        ...gates.map(g => ({
          type: "Feature",
          properties: {
            id: g.id,
            name: g.name,
            gateType: g.type,
            featureType: g.type === 'landing' ? 'landing_gate' : 'takeoff_gate',
            width: g.width
          },
          geometry: {
            type: "LineString",
            coordinates: [
              [g.p1.lng, g.p1.lat],
              [g.p2.lng, g.p2.lat]
            ]
          }
        })),
        // Observation Markers
        ...observationMarkers.map(m => ({
          type: "Feature",
          properties: {
            id: m.id,
            name: m.name,
            featureType: "observation_photo"
          },
          geometry: { type: "Point", coordinates: [m.lng, m.lat] }
        }))
        ,
        // Polygons
        ...polygons.map(p => ({
          type: "Feature",
          properties: {
            id: p.id,
            name: p.name,
            polygonType: p.type,
            featureType: p.type === 'waypoint' ? "waypoint_polygon" : "zone"
          },
          geometry: {
            type: "Polygon",
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
        showCorridor:showCorridor,
        maxObsDist:maxObsDist,
        hideLabels:hideLabels
      }
    };

    try {
      const result = await saveRoute(routeId, payload);

      alert("Route saved successfully!");
      setIsDirty(false);
      if (!routeId && result.id) {
        setRouteId(result.id.toString());
        // Optionally update URL
        const editUrl = (document.configuration as any)?.editRouteViewUrl?.(result.id) || `/routeeditor/edit/${result.id}`;
        window.history.pushState({}, '', editUrl);
      }
    } catch (e) {
      console.error(e);
      alert("Error saving route");
    } finally {
      setIsSaving(false);
    }
  };

  const handleReverseRoute = useCallback(() => {
    setIsDirty(true);
    setRoutePoints(prevPoints => {
        if (prevPoints.length < 2) {
            return prevPoints;
        }

        const reversedPoints = [...prevPoints].reverse();
        // Segments are defined on the END point of the segment. The first point has no segment.
        const segmentInfo = prevPoints.slice(1).map(p => ({
            segmentType: p.segmentType,
            controlLat: p.controlLat,
            controlLng: p.controlLng
        }));
        const reversedSegmentInfo = segmentInfo.reverse();

        const newPoints = reversedPoints.map((point, index) => {
            const newPoint = { ...point };

            // Set type and name
            if (index === 0) {
                newPoint.type = 'sp';
                newPoint.name = 'Start';
            } else if (index === reversedPoints.length - 1) {
                newPoint.type = 'fp';
                newPoint.name = 'Finish';
            } else {
                if (newPoint.type !== 'secret') {
                    newPoint.type = 'tp';
                }
            }

            // Set segment info
            if (index > 0) {
                const segment = reversedSegmentInfo[index - 1];
                newPoint.segmentType = segment.segmentType || 'straight';
                newPoint.controlLat = segment.controlLat;
                newPoint.controlLng = segment.controlLng;
            } else {
                // First point has no incoming segment
                newPoint.segmentType = 'straight';
                delete newPoint.controlLat;
                delete newPoint.controlLng;
            }

            return newPoint;
        });

        // Re-number intermediate waypoints to maintain consistency
        let wpCounter = 1;
        const finalPoints = newPoints.map(p => {
            if (p.type === 'tp' && p.name.startsWith('WP')) {
                return { ...p, name: `WP ${wpCounter++}` };
            }
            if (p.type === 'tp') {
              wpCounter++;
            }
            return p;
        });

        return finalPoints;
    });
  }, []);


  return (
    <div className="flex w-full h-[calc(100vh-66px)] bg-base-200 font-sans text-base-content overflow-hidden">

      {/* SIDEBAR */}
      <div className="h-full overflow-y-auto shrink-0 max-w-xs">
        <Sidebar 
          routePoints={routePoints}
          standalonePoints={standalonePoints}
          gates={gates}
          observationMarkers={observationMarkers}
          polygons={polygons}
          selectedId={selectedId}
          selectionType={selectionType}
          onSelect={setSelectedId}
          onSelectType={setSelectionType}
          updateSelectedPoint={updateSelectedPoint}
          updateSelectedStandalonePoint={updateSelectedStandalonePoint}
          updateSelectedGate={updateSelectedGate}
          onUpdateObs={updateSelectedObservation}
          onUpdatePoly={updateSelectedPolygon}
          onDelete={deleteSelected}
          onMovePoint={movePointOrder}
          onFit={handleFit}
          handleSave={handleSave}
          handleReverseRoute={handleReverseRoute}
          showCorridor={showCorridor}
          setShowCorridor={setShowCorridor}
          hideLabels={hideLabels}
          setHideLabels={setHideLabels}
          maxObsDist={maxObsDist}
          setMaxObsDist={setMaxObsDist}
          setSelectedId={setSelectedId}
          setSelectionType={setSelectionType}
          updateSelectedObservation={updateSelectedObservation}
          updateSelectedPolygon={updateSelectedPolygon}
          deleteSelected={deleteSelected}
          movePointOrder={movePointOrder}
          routeName={routeName}
          setRouteName={setRouteName}
          isAuthenticated={document.configuration?.isAuthenticated ?? false}
          isDirty={isDirty}
          validationErrors={validationErrors}
        />
      </div>

      {/* MAIN CONTENT */}
      <div className="flex-1 flex flex-col relative">

        {/* TOOLBAR */}
        <Toolbar
            mode={mode}
            setMode={setMode}
            tempGatePoint={tempGatePoint}
            setTempGatePoint={setTempGatePoint}
            setTempPolygonPoints={setTempPolygonPoints}
        />


        {/* MAP CONTAINER */}
        <MapCanvas 
          ref={handleMapRef}
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
          maxObsDist={maxObsDist}
          hideLabels={hideLabels}
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
        />

            {/* OVERLAY CONTROLS */}
            <div className="absolute bottom-4 left-4 z-[1000] flex flex-col gap-2">
                {mode === 'add_point' && (
                <div className="bg-base-100 p-2 rounded shadow flex items-center gap-2">
                    <input
                    type="checkbox"
                    id="curveMode"
                    className="checkbox checkbox-sm"
                    checked={addCurveMode}
                    onChange={(e) => setAddCurveMode(e.target.checked)}
                    />
                    <label htmlFor="curveMode" className="text-sm font-bold">Add Curved Leg</label>
                </div>
                )}

                {selectedId && selectionType === 'point' && routePoints.findIndex(p => p.id === selectedId) > 0 && (
                <div className="bg-base-100 p-2 rounded shadow flex flex-col gap-2">
                    <button onClick={toggleCurve} className="btn btn-sm btn-link no-underline">
                    {routePoints.find(p => p.id === selectedId)?.segmentType === 'curved' ? 'Make Straight' : 'Make Curved'}
                    </button>
                    {routePoints.find(p => p.id === selectedId)?.segmentType === 'curved' && (
                    <button onClick={resetCurve} className="btn btn-sm btn-link text-neutral no-underline">
                        Reset Curve
                    </button>
                    )}
                </div>
                )}
          </div>
      </div>
  </div>
  );
}