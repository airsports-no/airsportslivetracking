import React, { useEffect, useRef, forwardRef, useState } from 'react';
import L from 'leaflet';
import {
  getBearing,
  getDestinationPoint,
  toRad,
  getQuadraticBezierPoints
} from '../../../utils/geoUtils';
import useMapInit from './map/useMapInit';
import useDragHandlers from './map/useDragHandlers';
import * as Renderers from './map/renderers';
import { RoutePoint, Gate, ObservationMarker, Polygon, LatLng, SelectionType, Mode } from '../../../types';
import { fetchEditableRouteMapSources, fetchGlobalEditableRouteMapSources } from '../api';
import { MapSource } from '../types';

const getAngleDiff = (a: number, b: number) => {
  let diff = a - b;
  while (diff > 180) diff -= 360;
  while (diff < -180) diff += 360;
  return diff;
};

interface MapCanvasProps {
    routeId?: number | null;
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
  routeId,
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
  setRoutePoints,
  setGates,
  setObservationMarkers,
  setPolygons,
  setSelectedId,
  setSelectionType,
  setMode,
  setTempPolygonPoints,
  onMapClick
}, ref) => {
  const mapRef = useMapInit();
  const markersRef = useRef<{[key: string]: L.Layer}>({});
  const polylinesRef = useRef<L.Layer[]>([]);
  const routeLineRef = useRef<L.Polyline | null>(null);
  const baseLayerRefs = useRef<Record<string, L.TileLayer>>({});
  const overlayLayersRef = useRef<Record<string, L.TileLayer>>({});
  const sourceByKeyRef = useRef<Record<string, MapSource>>({});
  const [mapSources, setMapSources] = useState<MapSource[] | null>(null);
  const [selectedBaseLayerKey, setSelectedBaseLayerKey] = useState<string>('osm');
  const [selectedOverlayKey, setSelectedOverlayKey] = useState<string | null>(null);
  const [openAipEnabled, setOpenAipEnabled] = useState<boolean>(false);
  const [mapSelectorCollapsed, setMapSelectorCollapsed] = useState<boolean>(false);
  const didAutoFitSourceRef = useRef(false);
  
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

  useEffect(() => {
    let cancelled = false;

    const loader = routeId
      ? fetchEditableRouteMapSources(routeId)
      : fetchGlobalEditableRouteMapSources();

    loader
      .then((sources) => {
        if (!cancelled) {
          setMapSources(sources);
        }
      })
      .catch((error) => {
        console.error('Failed loading route editor map sources', error);
        if (!cancelled) {
          setMapSources([]);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [routeId]);

  // --- Add Tile Layers and Layer Control ---
  useEffect(() => {
    if (!mapRef.current) return;
    const map = mapRef.current;

    const layersToRemove: L.Layer[] = [];
    map.eachLayer((layer) => {
      if (layer instanceof L.TileLayer) {
        layersToRemove.push(layer);
      }
    });
    layersToRemove.forEach((layer) => map.removeLayer(layer));

    const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    });

    const googleSat = L.tileLayer('https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
      maxZoom: 20,
      subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
      attribution: '&copy; Google'
    });

    const openAip = L.tileLayer('https://api.tiles.openaip.net/api/data/openaip/{z}/{x}/{y}.png?apiKey=3d5d3f82528731731362a23f445951d8', {
      maxZoom: 14,
      minZoom: 4,
      attribution: '<a href="https://www.openaip.net/">OpenAIP Data</a>'
    });

    const externalBaseSources = (mapSources ?? []).filter((source) => source.source_group === 'external_base');
    const optionalOverlaySources = (mapSources ?? []).filter((source) => source.source_group !== 'external_base' && source.key !== 'openaip');

    const nextBaseLayerRefs: Record<string, L.TileLayer> = {
      osm,
      'google-satellite': googleSat,
    };
    const nextOverlayLayerRefs: Record<string, L.TileLayer> = {
      openaip: openAip,
    };
    const nextSourceByKey: Record<string, MapSource> = {
      osm: builtinBaseSources[0],
      'google-satellite': builtinBaseSources[1],
      openaip: {
        key: 'openaip',
        label: 'OpenAIP',
        origin: 'builtin',
        type: 'raster_xyz',
        tile_url: 'https://api.tiles.openaip.net/api/data/openaip/{z}/{x}/{y}.png?apiKey=3d5d3f82528731731362a23f445951d8',
        attribution: 'OpenAIP Data',
        min_zoom: 4,
        max_zoom: 14,
        default_zoom: 10,
        is_overlay: true,
        allow_multiple: true,
        is_always_on_top: true,
        bounds: null,
      },
    };

    externalBaseSources.forEach((source) => {
      nextBaseLayerRefs[source.key] = L.tileLayer(source.tile_url, {
        attribution: source.attribution,
        minNativeZoom: source.min_zoom,
        maxNativeZoom: source.max_zoom,
        minZoom: 0,
        maxZoom: 20,
      });
      nextSourceByKey[source.key] = source;
    });

    optionalOverlaySources.forEach((source) => {
      nextOverlayLayerRefs[source.key] = L.tileLayer(source.tile_url, {
        attribution: source.attribution,
        minNativeZoom: source.min_zoom,
        maxNativeZoom: source.max_zoom,
        minZoom: Math.max(0, source.min_zoom - 1),
        maxZoom: Math.min(20, source.max_zoom + 1),
      });
      nextSourceByKey[source.key] = source;
    });

    baseLayerRefs.current = nextBaseLayerRefs;
    overlayLayersRef.current = nextOverlayLayerRefs;
    sourceByKeyRef.current = nextSourceByKey;

    const desiredBaseKey = nextBaseLayerRefs[selectedBaseLayerKey] ? selectedBaseLayerKey : 'osm';
    nextBaseLayerRefs[desiredBaseKey].addTo(map);
    if (desiredBaseKey !== selectedBaseLayerKey) {
      setSelectedBaseLayerKey(desiredBaseKey);
    }

    if (selectedOverlayKey && nextOverlayLayerRefs[selectedOverlayKey]) {
      nextOverlayLayerRefs[selectedOverlayKey].addTo(map);
    } else if (selectedOverlayKey) {
      setSelectedOverlayKey(null);
    }

    if (openAipEnabled) {
      openAip.addTo(map);
      openAip.bringToFront();
    }

    return () => {
      const cleanupLayers: L.Layer[] = [];
      map.eachLayer((layer) => {
        if (layer instanceof L.TileLayer) {
          cleanupLayers.push(layer);
        }
      });
      cleanupLayers.forEach((layer) => map.removeLayer(layer));
    };
  }, [mapRef, mapSources, routeId, selectedBaseLayerKey, selectedOverlayKey, openAipEnabled]);

  useEffect(() => {
    if (!mapRef.current || !mapSources || routeId || didAutoFitSourceRef.current) return;

    const preferredSource = mapSources.find((source) => source.origin === 'user_upload' && source.bounds);
    if (!preferredSource || !preferredSource.bounds) return;

    const [minLon, minLat, maxLon, maxLat] = preferredSource.bounds;
    mapRef.current.fitBounds([
      [minLat, minLon] as [number, number],
      [maxLat, maxLon] as [number, number],
    ]);
    didAutoFitSourceRef.current = true;
  }, [mapRef, mapSources, routeId]);

  const builtinBaseSources: MapSource[] = [
    {
      key: 'osm',
      label: 'OpenStreetMap',
      origin: 'builtin',
      type: 'raster_xyz',
      tile_url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      attribution: '© OpenStreetMap contributors',
      min_zoom: 0,
      max_zoom: 19,
      default_zoom: 12,
      is_overlay: false,
      allow_multiple: false,
      is_always_on_top: false,
      bounds: null,
    },
    {
      key: 'google-satellite',
      label: 'Google Satellite',
      origin: 'builtin',
      type: 'raster_xyz',
      tile_url: 'https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
      attribution: '© Google',
      min_zoom: 0,
      max_zoom: 20,
      default_zoom: 12,
      is_overlay: false,
      allow_multiple: false,
      is_always_on_top: false,
      bounds: null,
    },
  ];
  const externalBaseSources = (mapSources ?? []).filter((source) => source.source_group === 'external_base');
  const selectableBaseSources = [
    ...builtinBaseSources,
    ...externalBaseSources.filter((source) => !builtinBaseSources.some((builtin) => builtin.key === source.key)),
  ];
  const systemOverlaySources = (mapSources ?? []).filter((source) => source.source_group === 'system_overlay' && source.key !== 'openaip');
  const uploadedOverlaySources = (mapSources ?? []).filter((source) => source.source_group === 'uploaded_overlay');
  const optionalOverlaySources = [...systemOverlaySources, ...uploadedOverlaySources];

  const canExplicitlyAdjustViewport = !routeId && routePoints.length === 0 && gates.length === 0 && observationMarkers.length === 0 && polygons.length === 0;
  const selectedOverlaySource = optionalOverlaySources.find((source) => source.key === selectedOverlayKey) ?? null;
  const canShowZoomToOverlayButton = !!selectedOverlaySource?.bounds;
  const overlayOutOfRange = !!selectedOverlaySource && !!mapRef.current && (mapRef.current.getZoom() < selectedOverlaySource.min_zoom - 1 || mapRef.current.getZoom() > selectedOverlaySource.max_zoom + 1);

  const handleSelectBaseLayer = (baseKey: string) => {
    setSelectedBaseLayerKey(baseKey);
  };

  const handleSelectOverlay = (overlayKey: string | null) => {
    setSelectedOverlayKey(overlayKey);
  };

  const handleToggleOpenAip = () => {
    setOpenAipEnabled((prev) => !prev);
  };

  const handleZoomToSelectedMap = () => {
    if (!mapRef.current || !selectedOverlaySource?.bounds) return;
    const [minLon, minLat, maxLon, maxLat] = selectedOverlaySource.bounds;
    const normalizedDefaultZoom = selectedOverlaySource.default_zoom == null
      ? undefined
      : Math.max(selectedOverlaySource.min_zoom, Math.min(selectedOverlaySource.default_zoom, selectedOverlaySource.max_zoom));
    const center: [number, number] = [
      (minLat + maxLat) / 2,
      (minLon + maxLon) / 2,
    ];
    mapRef.current.setView(center, normalizedDefaultZoom ?? mapRef.current.getZoom());
  };


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
    Renderers.drawRouteLine(
      map, 
      routePoints, 
      routeLineRef, 
      polylinesRef, 
      mode, 
      setRoutePoints, 
      setSelectedId, 
      setSelectionType, 
      hideLabels,
      dragRef,
      handleDragMove,
      handleDragEnd
    );

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
    Renderers.drawPolygons(
      map, 
      polygons, 
      mode, 
      selectedId, 
      selectionType, 
      markersRef, 
      dragRef, 
      handleDragMove, 
      handleDragEnd, 
      setSelectedId, 
      setSelectionType, 
      setMode, 
      hideLabels,
      setPolygons
    );

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
              setPolygons(prev => [...prev, {
                id: crypto.randomUUID(),
                name: `Zone ${prev.length + 1}`,
                type: 'prohibited',
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

  return (
    <>
      <div className="absolute top-4 left-4 z-[1000] w-80 max-w-[calc(100%-2rem)] rounded bg-base-100/95 shadow-lg border border-base-300 overflow-hidden">
        <button
          type="button"
          className="flex w-full items-center justify-between px-3 py-2 text-left text-sm font-semibold text-base-content hover:bg-base-200/70"
          onClick={() => setMapSelectorCollapsed((prev) => !prev)}
        >
          <span>Map selector</span>
          <span className="text-xs text-base-content/70">{mapSelectorCollapsed ? 'Show' : 'Hide'}</span>
        </button>

        {!mapSelectorCollapsed && (
          <div className="max-h-[70vh] overflow-y-auto space-y-3 border-t border-base-300 p-3">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-base-content/70 mb-2">Global base map</div>
              <div className="space-y-1">
                {selectableBaseSources.map((source) => (
                  <label key={source.key} className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="radio"
                      name="route-editor-base-map"
                      className="radio radio-xs"
                      checked={selectedBaseLayerKey === source.key}
                      onChange={() => handleSelectBaseLayer(source.key)}
                    />
                    <span>{source.label}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-base-content/70 mb-2">System overlays</div>
              <div className="space-y-1">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="radio"
                    name="route-editor-overlay-map"
                    className="radio radio-xs"
                    checked={selectedOverlayKey === null}
                    onChange={() => handleSelectOverlay(null)}
                  />
                  <span>None</span>
                </label>
                {systemOverlaySources.map((source) => (
                  <label key={source.key} className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="radio"
                      name="route-editor-overlay-map"
                      className="radio radio-xs"
                      checked={selectedOverlayKey === source.key}
                      onChange={() => handleSelectOverlay(source.key)}
                    />
                    <span>{source.label}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-base-content/70 mb-2">Uploaded overlays</div>
              <div className="space-y-1">
                {uploadedOverlaySources.map((source) => (
                  <label key={source.key} className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="radio"
                      name="route-editor-overlay-map"
                      className="radio radio-xs"
                      checked={selectedOverlayKey === source.key}
                      onChange={() => handleSelectOverlay(source.key)}
                    />
                    <span>{source.label}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-base-content/70 mb-2">Overlay</div>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  className="checkbox checkbox-xs"
                  checked={openAipEnabled}
                  onChange={handleToggleOpenAip}
                />
                <span>OpenAIP</span>
              </label>
            </div>

            {canShowZoomToOverlayButton && (
              <div className="space-y-2 border-t border-base-300 pt-3">
                {overlayOutOfRange && (
                  <div className="rounded bg-base-100/90 px-3 py-2 text-xs text-base-content shadow border border-base-300">
                    Selected overlay is only visible around zoom {selectedOverlaySource!.min_zoom}–{selectedOverlaySource!.max_zoom}.
                  </div>
                )}
                <button type="button" className="btn btn-sm btn-primary w-full" onClick={handleZoomToSelectedMap}>
                  Zoom to selected overlay
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      <div id="map-container" className="w-full h-full bg-slate-200" />
    </>
  );
});

export default MapCanvas;
