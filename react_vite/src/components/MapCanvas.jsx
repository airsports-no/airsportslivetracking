import React, { useEffect, useRef, forwardRef } from 'react';
import L from 'leaflet';
import {
  getBearing,
  getDestinationPoint,
  toRad,
  isPointInPolygon,
  getQuadraticBezierPoints
} from '../utils/geoUtils';
import useMapInit from './map/useMapInit';
import useDragHandlers from './map/useDragHandlers';
import * as Renderers from './map/renderers';

const getAngleDiff = (a, b) => {
  let diff = a - b;
  while (diff > 180) diff -= 360;
  while (diff < -180) diff += 360;
  return diff;
};

/**
 * MapCanvas Component
 * 
 * This component is responsible for:
 * 1. Initializing the Leaflet map.
 * 2. Rendering all visual elements (Route Points, Gates, Observation Markers, Polygons).
 * 3. Handling direct map interactions like Dragging elements and Clicking to select.
 * 4. Forwarding generic map clicks to the parent (App.jsx) for handling based on the current 'mode'.
 */
const MapCanvas = forwardRef(({
  // --- Data Props ---
  routePoints,
  gates,
  observationMarkers,
  polygons,
  selectedId,
  selectionType,
  mode,
  tempGatePoint,
  tempPolygonPoints,
  showCorridor,
  maxObsDist,

  // --- Actions / Setters ---
  setRoutePoints,
  setGates,
  setObservationMarkers,
  setPolygons,
  setSelectedId,
  setSelectionType,
  setMode,
  setTempPolygonPoints,
  onMapClick // Callback for generic map clicks (handled in App.jsx)
}, ref) => {
  const mapRef = useMapInit();
  const markersRef = useRef({}); // Stores references to Leaflet layers by ID
  const polylinesRef = useRef([]); // Stores references to non-keyed lines (like temp lines)
  const routeLineRef = useRef(null); // Reference to the main route polyline
  
  const { handleDragMove, handleDragEnd, dragRef } = useDragHandlers({
    mapRef,
    setRoutePoints,
    setPolygons,
    observationMarkers,
    markersRef,
    routeLineRef,
    setSelectedId,
    setSelectionType,
    setMode,
    maxObsDist
  });

  // --- Expose Map Instance to Parent ---
  useEffect(() => {
    if (mapRef.current && ref) {
      if (typeof ref === 'function') {
        ref(mapRef.current);
      } else {
        ref.current = mapRef.current;
      }
    }
  });

  // --- 2. Bind Map Click Event ---
  // We attach this separately so it can access the latest 'onMapClick' prop without re-initializing the map
  useEffect(() => {
    if (!mapRef.current) return;
    const map = mapRef.current;

    const handler = (e) => {
      if (onMapClick) onMapClick(e.latlng);
    };
    
    map.on('click', handler);
    return () => map.off('click', handler);
  }, [onMapClick]);

  // --- 3. Render Map Elements & Handle Interactions ---
  useEffect(() => {
    if (!mapRef.current) return;
    const map = mapRef.current;

    // --- RENDERER: CLEAR LAYERS ---
    Renderers.clearLayers(markersRef, polylinesRef, routeLineRef, map);

    // --- RENDERER: CORRIDOR ---
    if (showCorridor && routePoints.length > 1) {
      const pathPoints = [];
      
      // Generate dense path points including curves
      for (let i = 0; i < routePoints.length; i++) {
        const p = routePoints[i];
        if (i === 0) {
          pathPoints.push({ lat: p.lat, lng: p.lng, width: p.width });
          continue;
        }

        const prev = routePoints[i - 1];
        if (p.segmentType === 'curved') {
          const curve = getQuadraticBezierPoints(prev, p, { lat: p.controlLat, lng: p.controlLng });
          curve.forEach((cp, idx) => {
            // Avoid duplicate start point
            if (idx === 0 && pathPoints.length > 0) {
              const last = pathPoints[pathPoints.length - 1];
              if (Math.abs(last.lat - cp.lat) < 0.000001 && Math.abs(last.lng - cp.lng) < 0.000001) return;
            }
            const t = idx / (curve.length - 1 || 1);
            const w = prev.width + (p.width - prev.width) * t;
            pathPoints.push({ lat: cp.lat, lng: cp.lng, width: w });
          });
        } else {
          pathPoints.push({ lat: p.lat, lng: p.lng, width: p.width });
        }
      }

      const leftPoints = [];
      const rightPoints = [];
      let lastLeft = null;
      let lastRight = null;
      const minGap = 2; // Minimum distance between boundary points to avoid overlap/bunching

      pathPoints.forEach((p, i) => {
        let bearing;
        let miterFactor = 1;

        if (i === 0) {
          bearing = getBearing(p, pathPoints[i + 1]);
        } else if (i === pathPoints.length - 1) {
          bearing = getBearing(pathPoints[i - 1], p);
        } else {
          const b1 = getBearing(pathPoints[i - 1], p);
          const b2 = getBearing(p, pathPoints[i + 1]);
          let diff = b2 - b1;
          if (diff > 180) diff -= 360;
          if (diff < -180) diff += 360;
          bearing = b1 + diff / 2;
          miterFactor = 1 / Math.cos(toRad(diff / 2));
        }

        miterFactor = Math.min(miterFactor, 5);
        const dist = (p.width / 2) * miterFactor;
        const l = getDestinationPoint(p, dist, bearing - 90);
        const r = getDestinationPoint(p, dist, bearing + 90);

        if (!lastLeft) {
          leftPoints.push(l);
          lastLeft = l;
        } else if (L.latLng(lastLeft).distanceTo(l) > minGap) {
          const moveBearing = getBearing(lastLeft, l);
          if (Math.abs(getAngleDiff(moveBearing, bearing)) < 100) {
            leftPoints.push(l);
            lastLeft = l;
          }
        }

        if (!lastRight) {
          rightPoints.push(r);
          lastRight = r;
        } else if (L.latLng(lastRight).distanceTo(r) > minGap) {
          const moveBearing = getBearing(lastRight, r);
          if (Math.abs(getAngleDiff(moveBearing, bearing)) < 100) {
            rightPoints.push(r);
            lastRight = r;
          }
        }
      });

      const corridorPoly = L.polygon([
        ...leftPoints.map(p => [p.lat, p.lng]),
        ...rightPoints.reverse().map(p => [p.lat, p.lng])
      ], {
        color: '#3b82f6', weight: 1, opacity: 0.5, fillColor: '#3b82f6', fillOpacity: 0.1
      }).addTo(map);

      polylinesRef.current.push(corridorPoly);
    }

    // --- RENDERER: DRAW ROUTE LINE ---
    Renderers.drawRouteLine(map, routePoints, routeLineRef, polylinesRef, mode, setRoutePoints, setSelectedId, setSelectionType);

    // --- RENDERER: DRAW POINTS ---
    Renderers.drawPoints(map, routePoints, mode, selectedId, markersRef, dragRef, handleDragMove, handleDragEnd);

    // --- RENDERER: DRAW GATES ---
    Renderers.drawGates(map, gates, polylinesRef, setSelectedId, setSelectionType, setMode);

    // --- RENDERER: TEMP GATE ---
    if (tempGatePoint) {
      const marker = L.circleMarker([tempGatePoint.lat, tempGatePoint.lng], {
        radius: 4, color: 'black'
      }).addTo(map);
      polylinesRef.current.push(marker);
    }

    // --- RENDERER: OBSERVATION MARKERS ---
    observationMarkers.forEach(m => {
      const marker = L.circleMarker([m.lat, m.lng], {
        radius: 5,
        fillColor: '#eab308',
        color: '#000',
        weight: 1,
        opacity: 1,
        fillOpacity: 1
      }).addTo(map);

      marker.bindTooltip(m.name, { permanent: true, direction: 'top', offset: [0, -5], className: 'bg-transparent border-0 shadow-none text-yellow-700 font-bold text-xs' });

      marker.on('click', (e) => {
        L.DomEvent.stopPropagation(e);
        setSelectedId(m.id);
        setSelectionType('observation');
        setMode('view');
      });

      markersRef.current[`obs-${m.id}`] = marker;
    });

    // --- RENDERER: POLYGONS ---
    Renderers.drawPolygons(map, polygons, mode, selectedId, selectionType, markersRef, dragRef, handleDragMove, handleDragEnd, setSelectedId, setSelectionType, setMode);

    // --- RENDERER: TEMP POLYGON ---
    if (tempPolygonPoints.length > 0) {
      const line = L.polyline(tempPolygonPoints.map(p => [p.lat, p.lng]), {
        color: '#ec4899', weight: 2, dashArray: '5, 5'
      }).addTo(map);
      polylinesRef.current.push(line);

      tempPolygonPoints.forEach((p, i) => {
        const marker = L.circleMarker([p.lat, p.lng], {
          radius: 5, color: '#ec4899', fillColor: 'white', fillOpacity: 1
        }).addTo(map);

        // Click first point to close polygon
        if (i === 0) {
          marker.setStyle({ radius: 7, weight: 3 });
          marker.on('click', (e) => {
            L.DomEvent.stopPropagation(e);
            if (tempPolygonPoints.length >= 3) {
              // Check if polygon contains exactly one waypoint
              const containedPoints = routePoints.filter(p => isPointInPolygon(p, tempPolygonPoints));
              let type = 'prohibited';

              if (containedPoints.length === 1) {
                const wp = containedPoints[0];
                const alreadyCovered = polygons.some(p => p.type === 'waypoint' && isPointInPolygon(wp, p.points));
                if (!alreadyCovered) {
                  type = 'waypoint';
                }
              }

              setPolygons(prev => [...prev, {
                id: crypto.randomUUID(),
                name: `Zone ${prev.length + 1}`,
                type: type,
                points: tempPolygonPoints
              }]);
              setTempPolygonPoints([]);
              setMode('view');
            }
          });
        }
        polylinesRef.current.push(marker);
      });
    }

  }, [
    routePoints, gates, tempGatePoint, showCorridor, observationMarkers, 
    polygons, tempPolygonPoints, selectedId, selectionType, mode,
    setRoutePoints, setGates, setObservationMarkers, setPolygons, 
    setSelectedId, setSelectionType, setMode, setTempPolygonPoints
  ]);

  return <div id="map-container" className="w-full h-full bg-slate-200" />;
});

export default MapCanvas;
