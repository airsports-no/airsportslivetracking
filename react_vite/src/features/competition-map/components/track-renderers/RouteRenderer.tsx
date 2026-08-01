import { useEffect, useRef } from 'react';
import L from 'leaflet';
import type { NavigationTask, Waypoint, Contestant, RouteData, NavigationTaskCatalogueTarget } from '../../types';
import './WaypointLabel.css';

function formatTime(dt: Date): string {
  const hh = String(dt.getHours()).padStart(2, '0');
  const mm = String(dt.getMinutes()).padStart(2, '0');
  const ss = String(dt.getSeconds()).padStart(2, '0');
  return `${hh}:${mm}:${ss}`;
}

function renderWaypointLabels(
    map: L.Map,
    waypoints: Waypoint[],
    contestants: Record<number, Contestant>,
    selectedContestantId: number | null
): L.Layer[] {
    const layers: L.Layer[] = [];
    const emptyIcon = L.divIcon({
        className: 'leaflet-div-icon-empty',
        html: '',
        iconSize: [0, 0],
        iconAnchor: [0, 0],
    });

    waypoints.forEach((waypoint: Waypoint) => {
        let label = waypoint.name; // Initialize label with waypoint name

        // Logic to add expected gate time
        if (selectedContestantId !== null && contestants[selectedContestantId]?.gate_times && contestants[selectedContestantId].gate_times![waypoint.name]) {
            const expectedTime = new Date(contestants[selectedContestantId].gate_times![waypoint.name]);
            label = `${waypoint.name} ${formatTime(expectedTime)}`;
        }

        const anyWaypoint = waypoint as any;
        let position: L.LatLngExpression = [waypoint.latitude, waypoint.longitude]; // Fallback position
        let tooltipDirection: L.TooltipOptions['direction'] = 'top'; // Fallback direction
        let tooltipOffset: L.PointTuple = [0, -10]; // Fallback offset

        const X_OFFSET = 0;
        const Y_OFFSET = 10;

        if (anyWaypoint.outer_corner_position && anyWaypoint.outer_corner_position.length >= 3) {
            position = anyWaypoint.outer_corner_position[0];
            const horizontalMultiplier = anyWaypoint.outer_corner_position[1]; // e.g., +1 or -1
            const verticalMultiplier = anyWaypoint.outer_corner_position[2];   // e.g., +1 or -1

            if(horizontalMultiplier > 0) tooltipDirection = 'right';
            if(horizontalMultiplier < 0) tooltipDirection = 'left';

            const offsetX = horizontalMultiplier * X_OFFSET;
            const offsetY = verticalMultiplier * Y_OFFSET;

            tooltipOffset = [offsetX, offsetY];
        }

        const tooltipOptions: L.TooltipOptions = {
            permanent: true,
            direction: tooltipDirection,
            offset: tooltipOffset,
            className: 'waypoint-label'
        };

        const marker = L.marker(position, {
            icon: emptyIcon, // Use a completely transparent icon
        }).addTo(map);

        marker.bindTooltip(label, tooltipOptions);

        layers.push(marker);
    });
    return layers;
}

interface Props {
  map: L.Map | null;
  route: RouteData | null;
  taskCatalogueTargets?: NavigationTaskCatalogueTarget[];
  taskConfig?: Record<string, any>;
  taskType: string[] | null;
  navTaskDisplaySecrets: boolean;
  displaySecrets: boolean; // User preference
  contestants: Record<number, Contestant>; // Add this
  selectedContestantId: number | null; // Add this
  isInitialLoad: boolean; // New prop
  onMapFit: (fitted: boolean) => void; // New prop
}

// From precisionRenderer.js
function renderPrecisionRoute(map: L.Map, route: RouteData, navTaskDisplaySecrets: boolean, displaySecrets: boolean): L.Layer[] {
  const layers: L.Layer[] = [];

  route.waypoints.filter((waypoint: Waypoint) => {
    return waypoint.type === 'sp' && waypoint.gate_line_extended
  }).forEach((gate: Waypoint) => {
    layers.push(L.polyline(gate.gate_line_extended!, {
        color: "blue",
        dashArray: "4 8"
    }).addTo(map));
  });

  const filterWaypoints = () => route.waypoints.filter((waypoint: Waypoint) => {
    return ((waypoint.gate_check || waypoint.time_check) && ((navTaskDisplaySecrets && displaySecrets) || waypoint.type !== "secret") && waypoint.type!=="dummy")
  });

  filterWaypoints().forEach((gate: Waypoint) => {
    layers.push(L.polyline(gate.gate_line, {
        color: "blue"
    }).addTo(map));
  });

  const tracks: L.LatLngExpression[][] = [];
  let currentTrack: L.LatLngExpression[] = [];
  const typesToIgnore = ["to", "ldg", "ildg", "dummy"];
  
  route.waypoints.forEach((waypoint: Waypoint) => {
    if (waypoint.type === 'isp') { // This type is not in the Waypoint type, assuming it's a string from old code.
        tracks.push(currentTrack);
        currentTrack = [];
    }
    if (!typesToIgnore.includes(waypoint.type)) {
        if (waypoint.is_procedure_turn) {
            const procedureTurnPoints = (waypoint as any).procedure_turn_points;
            if (Array.isArray(procedureTurnPoints) && procedureTurnPoints.length > 0) {
                currentTrack.push(...procedureTurnPoints);
            } else {
                currentTrack.push([waypoint.latitude, waypoint.longitude]);
            }
        } else {
            currentTrack.push([waypoint.latitude, waypoint.longitude]);
        }
    }
  });
  tracks.push(currentTrack);

  for (const track of tracks) {
    const routePolyline = L.polyline(track, {
        color: "blue"
    }).addTo(map);
    layers.push(routePolyline);
  }

  return layers;
}

// From airsportsRenderer.js
function renderAirsportsRoute(map: L.Map, route: RouteData, isAnr: boolean, navTaskDisplaySecrets: boolean, displaySecrets: boolean): L.Layer[] {
    const layers: L.Layer[] = [];
    
    if (route.corridor_polygon) {
        const polygon = route.corridor_polygon.map((p: any) => [p.lat, p.lng] as [number, number]);
        // Use L.polygon instead of L.polyline to ensure the corridor is closed
        layers.push(L.polygon(polygon, { color: "blue", fill: false, weight: 2 }).addTo(map));
    }

    const filterWaypoints = () => {
        if (isAnr) {
            return route.waypoints.filter((w: Waypoint) => w.type === 'sp' || w.type === 'fp');
        }
        return route.waypoints.filter((w: Waypoint) => ((w.gate_check || w.time_check) && ((navTaskDisplaySecrets && displaySecrets) || w.type !== "secret") && w.type!=="dummy"));
    }

    filterWaypoints().forEach((gate: Waypoint) => {
        const isSpFp = isAnr && (gate.type === 'sp' || gate.type === 'fp');
        layers.push(L.polyline(gate.gate_line, { 
            color: isSpFp ? "red" : "blue",
            weight: isSpFp ? 5 : 3
        }).addTo(map));
    });

    return layers;
}

// From landingRenderer.js
function renderLandingRoute(map: L.Map, route: RouteData): L.Layer[] {
    const layers: L.Layer[] = [];
    for(const gate of route.landing_gates) {
        layers.push(L.polyline(gate.gate_line, {
            color: "blue"
        }).addTo(map));
    }
    return layers;
}


// From pokerRenderer.js
function renderPokerRoute(map: L.Map, route: RouteData): L.Layer[] {
    const layers: L.Layer[] = [];
    
    // 1. Draw circles for waypoints
    route.waypoints.forEach((waypoint: Waypoint) => {
        if (waypoint.type !== 'dummy') {
            // width is in NM, convert half-width to meters for Leaflet circle radius
            const radiusMeters = (waypoint.width / 2) * 1852;
            layers.push(L.circle([waypoint.latitude, waypoint.longitude], {
                radius: radiusMeters,
                color: "blue",
                weight: 2,
                fillOpacity: 0.1
            }).addTo(map));
        }
    });

    // 2. Draw the route line
    const path: L.LatLngExpression[] = route.waypoints
        .filter(wp => wp.type !== 'dummy')
        .map(wp => [wp.latitude, wp.longitude]);
    
    if (path.length > 1) {
        layers.push(L.polyline(path, { color: "blue", weight: 2, opacity: 0.5 }).addTo(map));
    }

    return layers;
}


function renderCatalogueTargets(map: L.Map, targets: NavigationTaskCatalogueTarget[]): L.Layer[] {
  const layers: L.Layer[] = [];
  const markerStyleByKind: Record<string, { radius: number; color: string; fillColor: string; fillOpacity: number; shape?: 'circle' | 'square'; html?: string; className?: string }> = {
    catalogue_turnpoint: { radius: 8, color: 'blue', fillColor: 'white', fillOpacity: 0 },
    circle_center_marker: { radius: 7, color: '#7c3aed', fillColor: '#7c3aed', fillOpacity: 0.2 },
    circle_start_marker: { radius: 8, color: '#16a34a', fillColor: 'white', fillOpacity: 0 },
    circle_entry_marker: { radius: 8, color: '#ea580c', fillColor: '#ea580c', fillOpacity: 0.15, html: '▶', className: 'text-xs font-bold text-orange-600' },
    circle_exit_marker: { radius: 8, color: '#dc2626', fillColor: 'white', fillOpacity: 0, shape: 'square' },
  };

  targets.forEach((target) => {
    const [lng, lat] = target.coordinates;
    const style = markerStyleByKind[target.kind || 'catalogue_turnpoint'] || markerStyleByKind.catalogue_turnpoint;
    let layer: L.Layer;

    if (style.html) {
      const marker = L.marker([lat, lng], {
        icon: L.divIcon({
          className: 'leaflet-div-icon-empty',
          html: `<div class="${style.className}">${style.html}</div>`,
          iconSize: [18, 18],
          iconAnchor: [9, 9],
        }),
      }).addTo(map);
      layer = marker;
    } else if (style.shape === 'square') {
      const marker = L.rectangle(
        [
          [lat - 0.00035, lng - 0.00035],
          [lat + 0.00035, lng + 0.00035],
        ],
        {
          color: style.color,
          weight: 2,
          fillOpacity: style.fillOpacity,
          fillColor: style.fillColor,
        }
      ).addTo(map);
      layer = marker;
    } else {
      const marker = L.circleMarker([lat, lng], {
        radius: style.radius,
        color: style.color,
        weight: 2,
        fillColor: style.fillColor,
        fillOpacity: style.fillOpacity,
      }).addTo(map);
      layer = marker;
    }

    (layer as any).bindTooltip(target.name, {
      permanent: true,
      direction: 'right',
      offset: [8, 0],
      className: 'waypoint-label'
    });
    layers.push(layer);
  });

  return layers;
}

function renderCircleTaskGeometry(map: L.Map, targets: NavigationTaskCatalogueTarget[], taskConfig?: Record<string, any>): L.Layer[] {
  const layers: L.Layer[] = [];
  const byKind = new Map((targets || []).map((target) => [target.kind, target]));
  const center = byKind.get('circle_center_marker');
  const start = byKind.get('circle_start_marker');
  const entry = byKind.get('circle_entry_marker');
  const exit = byKind.get('circle_exit_marker');

  if (!center) {
    return layers;
  }

  const [centerLng, centerLat] = center.coordinates;
  const minRadiusM = Number(taskConfig?.circle_radius_min_m ?? 200);
  const maxRadiusM = Number(taskConfig?.circle_radius_max_m ?? 750);

  const innerBoundary = L.circle([centerLat, centerLng], {
    radius: minRadiusM,
    color: '#16a34a',
    weight: 2,
    dashArray: '6 6',
    fill: false,
  }).addTo(map);
  const outerBoundary = L.circle([centerLat, centerLng], {
    radius: maxRadiusM,
    color: '#dc2626',
    weight: 2,
    dashArray: '10 6',
    fill: false,
  }).addTo(map);
  layers.push(innerBoundary, outerBoundary);

  const segmentStyle = { color: '#2563eb', weight: 3, dashArray: '8 6' };
  const spokeStyle = { color: '#7c3aed', weight: 2, dashArray: '4 4' };
  if (start && entry) {
    const [startLng, startLat] = start.coordinates;
    const [entryLng, entryLat] = entry.coordinates;
    layers.push(L.polyline([[startLat, startLng], [entryLat, entryLng]], segmentStyle).addTo(map));
  }
  if (entry) {
    const [entryLng, entryLat] = entry.coordinates;
    layers.push(L.polyline([[entryLat, entryLng], [centerLat, centerLng]], spokeStyle).addTo(map));
  }
  if (exit) {
    const [exitLng, exitLat] = exit.coordinates;
    layers.push(L.polyline([[centerLat, centerLng], [exitLat, exitLng]], spokeStyle).addTo(map));
  }

  return layers;
}

function getRenderedRoute(route: RouteData, contestants: Record<number, Contestant>, selectedContestantId: number | null): RouteData {
  if (selectedContestantId === null) {
    return route;
  }

  const contestant = contestants[selectedContestantId];
  const effectiveWaypoints = contestant?.compiled_effective_route_payload?.effective_waypoints;
  if (!Array.isArray(effectiveWaypoints) || effectiveWaypoints.length === 0) {
    return route;
  }

  return {
    ...route,
    waypoints: effectiveWaypoints as Waypoint[],
  };
}

export default function RouteRenderer({ map, route, taskCatalogueTargets, taskConfig, taskType, navTaskDisplaySecrets, displaySecrets, contestants, selectedContestantId, isInitialLoad, onMapFit }: Props) {
  const layersRef = useRef<L.Layer[]>([]);

  useEffect(() => {
    if (!map || !route || !taskType) return;

    const renderedRoute = getRenderedRoute(route, contestants, selectedContestantId);

    // Clear previous layers
    layersRef.current.forEach(layer => layer.remove());
    layersRef.current = [];

    let layers: L.Layer[] = [];

    if (taskType.includes("poker")) {
        layers = layers.concat(renderPokerRoute(map, renderedRoute));
    } else if (taskType.includes("precision")) {
      layers = layers.concat(renderPrecisionRoute(map, renderedRoute, navTaskDisplaySecrets, displaySecrets));
    }
    if (taskType.includes("airsports") || taskType.includes("airsportchallenge")) {
      layers = layers.concat(renderAirsportsRoute(map, renderedRoute, false, navTaskDisplaySecrets, displaySecrets));
    }
    if (taskType.includes("anr_corridor")) {
      layers = layers.concat(renderAirsportsRoute(map, renderedRoute, true, navTaskDisplaySecrets, displaySecrets));
    }
    if (taskType.includes("landing")) {
      layers = layers.concat(renderLandingRoute(map, renderedRoute));
    }
    if (selectedContestantId === null && taskCatalogueTargets && taskCatalogueTargets.length > 0) {
      layers = layers.concat(renderCatalogueTargets(map, taskCatalogueTargets));
      const circleTargets = taskCatalogueTargets.filter((target) => target.kind?.startsWith('circle_'));
      if (circleTargets.length > 0) {
        layers = layers.concat(renderCircleTaskGeometry(map, circleTargets, taskConfig));
      }
    }
    
    const waypointsToLabel = renderedRoute.waypoints.filter((w: Waypoint) => 
        (w.gate_check || w.time_check) && 
        ((navTaskDisplaySecrets && displaySecrets) || w.type !== "secret") && 
        w.type !== "dummy"
    );
    layers = layers.concat(renderWaypointLabels(map, waypointsToLabel, contestants, selectedContestantId));

    layersRef.current = layers;

    const ZOOM_THRESHOLD = 9;
    const handleZoom = () => {
        if (map.getZoom() < ZOOM_THRESHOLD) {
            map.getContainer().classList.add('hide-waypoint-labels');
        } else {
            map.getContainer().classList.remove('hide-waypoint-labels');
        }
    };

    map.on('zoomend', handleZoom);
    handleZoom(); // Initial check

    if (layers.length > 0) {
        const bounds = new L.FeatureGroup(layers).getBounds();
        if (isInitialLoad && bounds.isValid()) { // Only fit bounds on initial load
            map.fitBounds(bounds, { padding: [50, 50] });
            onMapFit(true); // Signal that initial fit has occurred
        }
    }


    return () => {
      layersRef.current.forEach(layer => layer.remove());
      layersRef.current = [];
      map.off('zoomend', handleZoom);
      map.getContainer().classList.remove('hide-waypoint-labels');
    };
  }, [map, route, taskCatalogueTargets, taskType, navTaskDisplaySecrets, displaySecrets, contestants, selectedContestantId, isInitialLoad, onMapFit]);

  return null;
}
