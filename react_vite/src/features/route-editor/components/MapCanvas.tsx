import React, { useEffect, useRef, forwardRef } from 'react';
import L from 'leaflet';
import {
  getBearing,
  getDestinationPoint,
  toRad,
  isPointInPolygon,
  getQuadraticBezierPoints
} from '../../../utils/geoUtils';
import useMapInit from './map/useMapInit';
import useDragHandlers from './map/useDragHandlers';
import * as Renderers from './map/renderers';
import { RoutePoint, Gate, ObservationMarker, Polygon, LatLng, SelectionType, Mode } from '../../../types';

const getAngleDiff = (a: number, b: number) => {
  let diff = a - b;
  while (diff > 180) diff -= 360;
  while (diff < -180) diff += 360;
  return diff;
};

interface MapCanvasProps {
    routePoints: RoutePoint[];
    gates: Gate[];
    observationMarkers: ObservationMarker[];
    polygons: Polygon[];
    selectedId: string | null;
    selectionType: SelectionType | null;
    mode: Mode;
    tempGatePoint: LatLng | null;
    tempPolygonPoints: LatLng[];
    showCorridor: boolean;
    maxObsDist: number;
    hideLabels: boolean;
    setRoutePoints: React.Dispatch<React.SetStateAction<RoutePoint[]>>;
    setGates: React.Dispatch<React.SetStateAction<Gate[]>>;
    setObservationMarkers: React.Dispatch<React.SetStateAction<ObservationMarker[]>>;
    setPolygons: React.Dispatch<React.SetStateAction<Polygon[]>>;
    setSelectedId: (id: string | null) => void;
    setSelectionType: (type: SelectionType | null) => void;
    setMode: (mode: Mode) => void;
    setTempPolygonPoints: React.Dispatch<React.SetStateAction<LatLng[]>>;
    onMapClick: (latlng: L.LatLng) => void;
}

const MapCanvas = forwardRef<L.Map, MapCanvasProps>(({
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
  hideLabels,

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
  const markersRef = useRef<{[key: string]: L.Layer}>({});
  const polylinesRef = useRef<L.Layer[]>([]);
  const routeLineRef = useRef<L.Polyline | null>(null);
  const layerControlRef = useRef<L.Control.Layers | null>(null); // Ref for layer control
  
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

  // --- Add Tile Layers and Layer Control ---
  useEffect(() => {
    if (!mapRef.current) return;
    const map = mapRef.current;

    // Remove existing control and layers if the effect re-runs
    if (layerControlRef.current) {
      map.removeControl(layerControlRef.current);
    }
    // Remove the previously added osm layer if any, before adding a new one.
    // This is important because osm.addTo(map) creates a new layer instance each time.
    map.eachLayer((layer) => {
      if ((layer as any)._url && (layer as any)._url.includes('openstreetmap')) {
        map.removeLayer(layer);
      }
    });

    const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    });

    const googleSat = L.tileLayer('https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
      maxZoom: 20,
      subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
      attribution: '&copy; Google'
    });

    const openAip = L.tileLayer('https://api.tiles.openaip.net/api/data/openaip/{z}/{x}/{y}.png?apiKey={apiKey}', {
      maxZoom: 14,
      minZoom: 4,
      attribution: '<a href="https://www.openaip.net/">OpenAIP Data</a>',
      apiKey: '3d5d3f82528731731362a23f445951d8'
    });

    osm.addTo(map);

    const newLayerControl = L.control.layers({
      "OpenStreetMap": osm,
      "Google Satellite": googleSat,
    }, {
      "OpenAIP": openAip
    }).addTo(map);

    layerControlRef.current = newLayerControl;

    return () => {
      if (layerControlRef.current) {
        map.removeControl(layerControlRef.current);
        layerControlRef.current = null;
      }
      // Ensure the osm layer is also removed during cleanup
      map.eachLayer((layer) => {
        if ((layer as any)._url && (layer as any)._url.includes('openstreetmap')) {
          map.removeLayer(layer);
        }
      });
    };
  }, [mapRef.current]);


  // --- 2. Bind Map Click Event ---
  // We attach this separately so it can access the latest 'onMapClick' prop without re-initializing the map
  useEffect(() => {
    if (!mapRef.current) return;
    const map = mapRef.current;

    const handler = (e: L.LeafletMouseEvent) => {
      if (onMapClick) onMapClick(e.latlng);
    };
    
    map.on('click', handler);
    return () => {
        map.off('click', handler);
    }
  }, [onMapClick]);

  // --- 3. Render Map Elements & Handle Interactions ---
  useEffect(() => {
    if (!mapRef.current) return;
    const map = mapRef.current;

    // --- RENDERER: CLEAR LAYERS ---
    Renderers.clearLayers(markersRef, polylinesRef, routeLineRef, map);

    // --- RENDERER: CORRIDOR ---
    if (showCorridor && routePoints.length > 1) {
      const pathPoints: (LatLng & { width: number })[] = [];
      
      // Generate dense path points including curves
      for (let i = 0; i < routePoints.length; i++) {
        const p = routePoints[i];
        if (i === 0) {
          pathPoints.push({ lat: p.lat, lng: p.lng, width: p.width });
          continue;
        }

        const prev = routePoints[i - 1];
        if (p.segmentType === 'curved' && p.controlLat && p.controlLng) {
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

      const leftPoints: (LatLng & {sourceIndex: number})[] = [];
      const rightPoints: (LatLng & {sourceIndex: number})[] = [];
      let lastLeft: LatLng | null = null;
      let lastRight: LatLng | null = null;

      const exclusionZones: { center: LatLng, radius: number, index: number, sharpness: number }[] = [];

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
            const l = getDestinationPoint(p, halfWidth, a) as LatLng & {sourceIndex: number};
            l.sourceIndex = i;
            if (!lastLeft || L.latLng(lastLeft).distanceTo(l) > 0.5) {
              leftPoints.push(l);
              lastLeft = l;
            }
          }
        } else { // Left Inside or Straight
          const l = getDestinationPoint(p, halfWidth * miterFactor, centerBearing - 90) as LatLng & {sourceIndex: number};
          l.sourceIndex = i;
            leftPoints.push(l);
            lastLeft = l;
          
        }

        // Right Side
        if (diff < -1) { // Left Turn -> Right Outside (Round)
          const steps = Math.ceil(Math.abs(diff) / 10);
          for (let s = 0; s <= steps; s++) {
            const a = b1 + 90 + (diff * s / steps);
            const r = getDestinationPoint(p, halfWidth, a) as LatLng & {sourceIndex: number};
            r.sourceIndex = i;
            if (!lastRight || L.latLng(lastRight).distanceTo(r) > 0.5) {
              rightPoints.push(r);
              lastRight = r;
            }
          }
        } else  { // Right Inside or Straight
          const r = getDestinationPoint(p, halfWidth * miterFactor, centerBearing + 90) as LatLng & {sourceIndex: number};
          r.sourceIndex = i;
            rightPoints.push(r);
            lastRight = r;

        }
      });

      const filterPoints = (points: (LatLng & {sourceIndex: number})[]) => {
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
    }

    // --- RENDERER: DRAW ROUTE LINE ---
    Renderers.drawRouteLine(map, routePoints, routeLineRef, polylinesRef, mode, setRoutePoints, setSelectedId, setSelectionType, hideLabels);

    // --- RENDERER: DRAW POINTS ---
    Renderers.drawPoints(map, routePoints, mode, selectedId, markersRef, dragRef, handleDragMove, handleDragEnd, hideLabels);

    // --- RENDERER: DRAW GATES ---
    Renderers.drawGates(map, gates, polylinesRef, setSelectedId, setSelectionType, setMode, hideLabels);

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

      marker.bindTooltip(m.name, { permanent: !hideLabels, direction: 'top', offset: [0, -5], className: 'bg-transparent border-0 shadow-none text-yellow-700 font-bold text-xs' });

      marker.on('click', (e) => {
        L.DomEvent.stopPropagation(e);
        setSelectedId(m.id);
        setSelectionType('observation');
        setMode('view');
      });

      markersRef.current[`obs-${m.id}`] = marker;
    });

    // --- RENDERER: POLYGONS ---
    Renderers.drawPolygons(map, polygons, mode, selectedId, selectionType, markersRef, dragRef, handleDragMove, handleDragEnd, setSelectedId, setSelectionType, setMode, hideLabels);

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
              let type: "prohibited" | "penalty" | "info" | "waypoint" = 'prohibited';

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
    setSelectedId, setSelectionType, setMode, setTempPolygonPoints, hideLabels
  ]);

  return <div id="map-container" className="w-full h-full bg-slate-200" />;
});

export default MapCanvas;
