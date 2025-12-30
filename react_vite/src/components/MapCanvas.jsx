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

      const exclusionZones = [];

      pathPoints.forEach((p, i) => {
        let b1, b2, diff;
        if (i === 0) {
          b1 = getBearing(p, pathPoints[i + 1]);
          b2 = b1;
          diff = 0;
        } else if (i === pathPoints.length - 1) {
          b1 = getBearing(pathPoints[i - 1], p);
          b2 = b1;
          diff = 0;
        } else {
          b1 = getBearing(pathPoints[i - 1], p);
          b2 = getBearing(p, pathPoints[i + 1]);
          diff = getAngleDiff(b2, b1);
        }

        let miterFactor = 1 / Math.cos(toRad(diff / 2));
        miterFactor = Math.min(miterFactor, 5);
        const miterLength = (p.width / 2) * miterFactor;
        exclusionZones.push({ center: p, radius: miterLength, index: i, sharpness: Math.abs(diff) });

        const centerBearing = b1 + diff / 2;
        const halfWidth = p.width / 2;

        // Left Side
        if (diff > 1) { // Right Turn -> Left Outside (Round)
          const steps = Math.ceil(diff / 10);
          for (let s = 0; s <= steps; s++) {
            const a = b1 - 90 + (diff * s / steps);
            const l = getDestinationPoint(p, halfWidth, a);
            l.sourceIndex = i;
            if (!lastLeft || L.latLng(lastLeft).distanceTo(l) > 0.5) {
              leftPoints.push(l);
              lastLeft = l;
            }
          }
        } else { // Left Inside or Straight
          const l = getDestinationPoint(p, halfWidth * miterFactor, centerBearing - 90);
          l.sourceIndex = i;
            leftPoints.push(l);
            lastLeft = l;
          
        }

        // Right Side
        if (diff < -1) { // Left Turn -> Right Outside (Round)
          const steps = Math.ceil(Math.abs(diff) / 10);
          for (let s = 0; s <= steps; s++) {
            const a = b1 + 90 + (diff * s / steps);
            const r = getDestinationPoint(p, halfWidth, a);
            r.sourceIndex = i;
            if (!lastRight || L.latLng(lastRight).distanceTo(r) > 0.5) {
              rightPoints.push(r);
              lastRight = r;
            }
          }
        } else  { // Right Inside or Straight
          const r = getDestinationPoint(p, halfWidth * miterFactor, centerBearing + 90);
          r.sourceIndex = i;
            rightPoints.push(r);
            lastRight = r;

        }
      });

      const filterPoints = (points) => {
        return points.filter(pt => {
          for (const zone of exclusionZones) {
            if (zone.index === pt.sourceIndex) continue;
            if (L.latLng(pt).distanceTo(zone.center) < zone.radius - 0.1) {
              const ptSharpness = exclusionZones[pt.sourceIndex].sharpness;
              const zoneSharpness = zone.sharpness;
              if (ptSharpness >= zoneSharpness) continue;
              return false;
            }
          }
          return true;
        });
      };

      const finalLeftPoints = filterPoints(leftPoints);
      const finalRightPoints = filterPoints(rightPoints);

      const corridorPoly = L.polygon([
        ...finalLeftPoints.map(p => [p.lat, p.lng]),
        ...finalRightPoints.reverse().map(p => [p.lat, p.lng])
      ], {
        color: '#3b82f6', weight: 1, opacity: 0.5, fillColor: '#3b82f6', fillOpacity: 0.1
      }).addTo(map);

      polylinesRef.current.push(corridorPoly);

      // [...finalLeftPoints, ...finalRightPoints].forEach(p => {
      //   const label = L.marker([p.lat, p.lng], {
      //     icon: L.divIcon({
      //       className: 'bg-transparent border-none',
      //       html: `<span class="text-[10px] font-bold text-red-600 bg-white/70 px-0.5 rounded">${p.sourceIndex}</span>`,
      //       iconSize: [20, 20]
      //     })
      //   }).addTo(map);
      //   polylinesRef.current.push(label);
      // });
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
