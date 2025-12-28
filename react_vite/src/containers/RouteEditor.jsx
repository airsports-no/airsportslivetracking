import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import Toolbar from '../components/Toolbar';
import MapCanvas from '../components/MapCanvas';
import {
  getDistance,
  getBearing,
  getDestinationPoint,
  isCollinear,
  getDistanceFromLine,
  toRad
} from '../utils/geoUtils';


/**
 * Helper to get CSRF token
 */
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

/**
 * MAIN COMPONENT
 */
export default function App() {
  // --- STATE ---
  const [routePoints, setRoutePoints] = useState([]);
  const [gates, setGates] = useState([]); // { id, name, type, p1: {lat,lng}, p2: {lat,lng} }
  const [observationMarkers, setObservationMarkers] = useState([]); // { id, lat, lng, name, notes }
  const [polygons, setPolygons] = useState([]); // { id, name, type, points: [{lat,lng}] }
  const [selectedId, setSelectedId] = useState(null);
  const [selectionType, setSelectionType] = useState(null); // 'point' | 'gate' | 'observation'
  const [routeId, setRouteId] = useState(null);
  const { routeId: paramRouteId } = useParams();
  const [routeName, setRouteName] = useState("");
  const [isDirty, setIsDirty] = useState(false);

  // Modes: 'view', 'add_point', 'add_landing...', 'add_takeoff...', 'add_observation', 'add_polygon'
  const [mode, setMode] = useState('view');
  const [tempGatePoint, setTempGatePoint] = useState(null); // Stores p1 while waiting for p2
  const [tempPolygonPoints, setTempPolygonPoints] = useState([]);
  const [showCorridor, setShowCorridor] = useState(false);
  const [addCurveMode, setAddCurveMode] = useState(false);
  const [maxObsDist, setMaxObsDist] = useState(926); // Default 0.5 NM

  const modeRef = useRef(mode);
  const [mapInstance, setMapInstance] = useState(null);
  const [pendingBounds, setPendingBounds] = useState(null);

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  // --- WARN ON UNSAVED CHANGES (Browser Navigation) ---
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isDirty]);

  // --- LOAD ROUTE ---
  const loadRouteData = useCallback((json) => {
    try {
      const newPoints = [];
      const newGates = [];
      const newObs = [];
      const newPolys = [];

      if (json.type === 'FeatureCollection') {
        // Parse Features
        const features = json.features;

        // Filter Points
        const pointFeatures = features.filter(f => f.geometry.type === 'Point' && f.properties.featureType !== 'observation_photo').sort((a, b) => a.properties.sequence - b.properties.sequence);

        pointFeatures.forEach(f => {
          newPoints.push({
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
            isPassing: f.properties.isPassing || true
          });
        });

        // Filter Gates
        const gateFeatures = features.filter(f => f.geometry.type === 'LineString' && f.properties.gateType);
        gateFeatures.forEach(f => {
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
        const obsFeatures = features.filter(f => f.geometry.type === 'Point' && f.properties.featureType === 'observation_photo');
        obsFeatures.forEach(f => {
          newObs.push({
            id: f.properties.id || crypto.randomUUID(),
            lat: f.geometry.coordinates[1],
            lng: f.geometry.coordinates[0],
            name: f.properties.name || "Obs"
          });
        });

        // Filter Polygons
        const polyFeatures = features.filter(f => f.geometry.type === 'Polygon' && (f.properties.featureType === 'zone' || f.properties.featureType === 'waypoint_polygon'));
        polyFeatures.forEach(f => {
          const coords = f.geometry.coordinates[0]; // Outer ring
          // Remove last point if it duplicates first (GeoJSON standard)
          if (coords.length > 0 && coords[0][0] === coords[coords.length - 1][0] && coords[0][1] === coords[coords.length - 1][1]) {
            coords.pop();
          }
          newPolys.push({
            id: f.properties.id || crypto.randomUUID(),
            name: f.properties.name || "Zone",
            type: f.properties.featureType === 'waypoint_polygon' ? 'waypoint' : (f.properties.polygonType || 'prohibited'),
            points: coords.map(c => ({ lng: c[0], lat: c[1] }))
          });
        });

        setRoutePoints(newPoints);
        setGates(newGates);
        setObservationMarkers(newObs);
        setPolygons(newPolys);

        // Zoom to fit imported content
        let minLat = Infinity;
        let maxLat = -Infinity;
        let minLng = Infinity;
        let maxLng = -Infinity;
        let hasPoints = false;

        const extend = (lat, lng) => {
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
        let map = mapInstance;
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
    if (paramRouteId) {
      setRouteId(paramRouteId);
      fetch(document.configuration.editableRouteUrl(paramRouteId))
        .then(res => {
          if (!res.ok) throw new Error("Failed to load route");
          return res.json();
        })
        .then(data => {
          if (data.route && data.name) {
            setRouteName(data.name);
            loadRouteData(data.route);
          } else {
            if (data.name) setRouteName(data.name);
            loadRouteData(data);
          }
        })
        .catch(err => console.error(err));
    }
  }, [paramRouteId, loadRouteData]);

  // --- HANDLERS (Defined before Map Logic to be used in deps) ---

  const handleMapClick = useCallback((latlng) => {
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

        let segmentType = 'straight';
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

        const newPoint = {
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
        const newGate = {
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

    if (mode === 'add_polygon') {
      setTempPolygonPoints(prev => [...prev, latlng]);
    }
  }, [mode, routePoints, gates.length, tempGatePoint, observationMarkers.length, polygons.length, addCurveMode]);

  const updateSelectedPoint = (field, value) => {
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

  const updateSelectedGate = (field, value) => {
    setIsDirty(true);
    setGates(gts => gts.map(g => {
      if (g.id !== selectedId) return g;
      return { ...g, [field]: value };
    }));
  };

  const updateSelectedObservation = (field, value) => {
    setIsDirty(true);
    setObservationMarkers(markers => markers.map(m => {
      if (m.id !== selectedId) return m;
      return { ...m, [field]: value };
    }));
  };

  const updateSelectedPolygon = (field, value) => {
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
      const index = routePoints.findIndex(p => p.id === selectedId);
      const newPoints = routePoints.filter(p => p.id !== selectedId);

      if (newPoints.length > 0) {
        if (index === 0) {
          newPoints[0] = { ...newPoints[0], type: 'sp', name: 'Start' };
        } else if (index === routePoints.length - 1) {
          newPoints[newPoints.length - 1] = { ...newPoints[newPoints.length - 1], type: 'fp', name: 'Finish' };
        }
      }
      setRoutePoints(newPoints);
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

  const movePointOrder = (direction) => {
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
    const errors = [];

    if (routePoints.length < 2) {
      errors.push("Route must have at least 2 points.");
    } else {
      if (routePoints[0].type !== 'sp') errors.push("First point must be type 'Start'.");
      if (routePoints[routePoints.length - 1].type !== 'fp') errors.push("Last point must be type 'Finish'.");

      // Check for Start/Finish in middle
      for (let i = 1; i < routePoints.length - 1; i++) {
        if (routePoints[i].type === 'sp') errors.push(`Point ${i + 1} cannot be Start (middle of route).`);
        if (routePoints[i].type === 'fp') errors.push(`Point ${i + 1} cannot be Finish (middle of route).`);
      }
    }

    // Secret Point Linearity Check
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

    return errors;
  }, [routePoints]);


  // --- SAVE ---
  const handleSave = async () => {
    if (!routeName || !routeName.trim()) {
      alert("Please enter a route name before saving.");
      return;
    }

    if (validationErrors.length > 0) {
      if (!confirm("Route has validation errors. Save anyway?")) return;
    }

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
        // Points
        ...routePoints.map((p, i) => ({
          type: "Feature",
          properties: {
            id: p.id,
            name: p.name,
            pointType: p.type, // Renamed to avoid conflict with GeoJSON type
            featureType: "route_waypoint",
            segmentType: p.segmentType || 'straight',
            controlLat: p.controlLat,
            controlLng: p.controlLng,
            width: p.width,
            isTiming: p.isTiming,
            isPassing: p.isPassing,
            sequence: i
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

    const payload = {
      name: routeName,
      route: geoJson
    };

    try {
      let url = document.configuration.EDITABLE_ROUTES_URL;
      let method = 'POST';

      if (routeId) {
        url = document.configuration.editableRouteUrl(routeId);
        method = 'PUT';
      }

      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify(payload)
      });

      if (response.ok) {
        const result = await response.json();
        alert("Route saved successfully!");
        setIsDirty(false);
        if (!routeId && result.id) {
          setRouteId(result.id);
          // Optionally update URL
          window.history.pushState({}, '', document.configuration.editRouteViewUrl(result.id));
        }
      } else {
        alert("Error saving route");
      }
    } catch (e) {
      console.error(e);
      alert("Error saving route");
    }
  };

  return (
    <div className="flex h-screen w-full bg-gray-100 font-sans text-gray-800 overflow-hidden">

      {/* SIDEBAR */}
      <Sidebar
        routePoints={routePoints}
        gates={gates}
        observationMarkers={observationMarkers}
        polygons={polygons}
        selectedId={selectedId}
        selectionType={selectionType}
        validationErrors={validationErrors}
        showCorridor={showCorridor}
        setShowCorridor={setShowCorridor}
        setSelectedId={setSelectedId}
        setSelectionType={setSelectionType}
        updateSelectedPoint={updateSelectedPoint}
        updateSelectedGate={updateSelectedGate}
        updateSelectedObservation={updateSelectedObservation}
        updateSelectedPolygon={updateSelectedPolygon}
        deleteSelected={deleteSelected}
        movePointOrder={movePointOrder}
        handleSave={handleSave}
        maxObsDist={maxObsDist}
        setMaxObsDist={setMaxObsDist}
        routeName={routeName}
        setRouteName={(name) => {
          setRouteName(name);
          setIsDirty(true);
        }}
      />

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

        <div className="absolute top-4 right-4 z-[1000]">
          <Link
            to="/"
            onClick={(e) => {
              if (isDirty && !confirm("Route has unsaved changes. Leave anyway?")) {
                e.preventDefault();
              }
            }}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 shadow">
            Back to list
          </Link>
        </div>

        {/* MAP CONTAINER */}
        <MapCanvas
          ref={setMapInstance}
          routePoints={routePoints}
          gates={gates}
          observationMarkers={observationMarkers}
          polygons={polygons}
          selectedId={selectedId}
          selectionType={selectionType}
          mode={mode}
          tempGatePoint={tempGatePoint}
          tempPolygonPoints={tempPolygonPoints}
          showCorridor={showCorridor}
          setRoutePoints={setRoutePoints}
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

        {/* OVERLAY CONTROLS */}
        <div className="absolute bottom-4 left-4 z-[1000] flex flex-col gap-2">
          {mode === 'add_point' && (
            <div className="bg-white p-2 rounded shadow flex items-center gap-2">
              <input
                type="checkbox"
                id="curveMode"
                checked={addCurveMode}
                onChange={(e) => setAddCurveMode(e.target.checked)}
              />
              <label htmlFor="curveMode" className="text-sm font-bold">Add Curved Leg</label>
            </div>
          )}

          {selectedId && selectionType === 'point' && routePoints.findIndex(p => p.id === selectedId) > 0 && (
            <div className="bg-white p-2 rounded shadow flex flex-col gap-2">
              <button onClick={toggleCurve} className="text-sm font-bold text-blue-600 hover:underline">
                {routePoints.find(p => p.id === selectedId)?.segmentType === 'curved' ? 'Make Straight' : 'Make Curved'}
              </button>
              {routePoints.find(p => p.id === selectedId)?.segmentType === 'curved' && (
                <button onClick={resetCurve} className="text-sm font-bold text-gray-600 hover:underline">
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
