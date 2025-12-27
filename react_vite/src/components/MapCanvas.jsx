import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import {
  getBearing,
  getDestinationPoint,
  toRad,
  isPointInPolygon
} from '../utils/geoUtils';
import useMapInit from './map/useMapInit';
import useDragHandlers from './map/useDragHandlers';
import * as Renderers from './map/renderers';

/**
 * MapCanvas Component
 * 
 * This component is responsible for:
 * 1. Initializing the Leaflet map.
 * 2. Rendering all visual elements (Route Points, Gates, Observation Markers, Polygons).
 * 3. Handling direct map interactions like Dragging elements and Clicking to select.
 * 4. Forwarding generic map clicks to the parent (App.jsx) for handling based on the current 'mode'.
 */
export default function MapCanvas({
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
}) {
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

    // --- RENDERER: CORRIDOR ---
    if (showCorridor && routePoints.length > 1) {
      const leftPoints = [];
      const rightPoints = [];

      routePoints.forEach((p, i) => {
        let bearing;
        let miterFactor = 1;

        if (i === 0) {
          bearing = getBearing(p, routePoints[i + 1]);
        } else if (i === routePoints.length - 1) {
          bearing = getBearing(routePoints[i - 1], p);
        } else {
          const b1 = getBearing(routePoints[i - 1], p);
          const b2 = getBearing(p, routePoints[i + 1]);

          let diff = b2 - b1;
          if (diff > 180) diff -= 360;
          if (diff < -180) diff += 360;

          bearing = b1 + diff / 2;
          miterFactor = 1 / Math.cos(toRad(diff / 2));
          miterFactor = Math.min(miterFactor, 5);
        }

        const dist = (p.width / 2) * miterFactor;
        leftPoints.push(getDestinationPoint(p, dist, bearing - 90));
        rightPoints.push(getDestinationPoint(p, dist, bearing + 90));
      });

      const corridorPoly = L.polygon([
        ...leftPoints.map(p => [p.lat, p.lng]),
        ...rightPoints.reverse().map(p => [p.lat, p.lng])
      ], {
        color: '#3b82f6', weight: 1, opacity: 0.5, fillColor: '#3b82f6', fillOpacity: 0.1
      }).addTo(map);

      polylinesRef.current.push(corridorPoly);
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
}
