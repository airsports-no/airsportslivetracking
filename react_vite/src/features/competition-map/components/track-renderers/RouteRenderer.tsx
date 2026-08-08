import { useEffect, useRef } from 'react';
import L from 'leaflet';
import type { NavigationTask, Waypoint, Contestant, RouteData, NavigationTaskCatalogueTarget } from '../../types';
import './WaypointLabel.css';

function getUnknownLegHiddenStretchNames(route: RouteData): Set<string> {
  const hiddenStretchNames = new Set<string>();
  let onUnknownLegHiddenStretch = false;

  route.waypoints.forEach((waypoint: Waypoint) => {
    if (waypoint.type === 'ul') {
      onUnknownLegHiddenStretch = true;
      return;
    }

    if (!onUnknownLegHiddenStretch) {
      return;
    }

    if (waypoint.type === 'hidden_gate' || waypoint.type === 'secret') {
      hiddenStretchNames.add(waypoint.name);
      return;
    }

    if (['tp', 'fp', 'isp', 'ifp', 'sp'].includes(waypoint.type)) {
      onUnknownLegHiddenStretch = false;
    }
  });

  return hiddenStretchNames;
}

function buildUnknownLegRouteDataFromTargets(targets: NavigationTaskCatalogueTarget[], hiddenStretchNames: Set<string> = new Set()): RouteData | null {
  const hiddenGateNames = new Set(
    targets
      .filter((target) => target.kind === 'hidden_gate')
      .map((target) => target.name)
  );
  const segmentEntries = new Map<string, NavigationTaskCatalogueTarget[]>();
  targets
    .filter((target) => target.kind === 'catalogue_turnpoint' && target.segment_name)
    .filter((target) => !hiddenGateNames.has(target.name))
    .filter((target) => !hiddenStretchNames.has(target.name))
    .forEach((target) => {
      const key = target.segment_name as string;
      const existing = segmentEntries.get(key) || [];
      existing.push(target);
      segmentEntries.set(key, existing);
    });
  if (segmentEntries.size === 0) return null;

  const orderedSegments = [...segmentEntries.entries()].sort(([a], [b]) => a.localeCompare(b));
  const waypoints: Waypoint[] = [];
  orderedSegments.forEach(([, segmentTargets], segmentIndex) => {
    let previousIncludedPointWasBranch = false;
    segmentTargets.forEach((target, pointIndex) => {
      const [lng, lat] = target.coordinates;
      const isBranchPoint = Boolean(target.trigger_point_id);
      if (pointIndex > 0 && previousIncludedPointWasBranch && !isBranchPoint) {
        return;
      }
      waypoints.push({
        name: target.name,
        latitude: lat,
        longitude: lng,
        elevation: 0,
        width: 0,
        gate_line: [],
        gate_line_extended: [],
        time_check: false,
        gate_check: false,
        end_curved: false,
        type: pointIndex === 0 && segmentIndex > 0 ? 'isp' : 'tp',
        distance_next: 0,
        distance_previous: 0,
        bearing_next: 0,
        bearing_from_previous: 0,
        is_procedure_turn: false,
      });
      previousIncludedPointWasBranch = isBranchPoint;
    });
  });

  return {
    id: -1,
    name: 'Unknown legs visible route',
    use_procedure_turns: false,
    rounded_corners: false,
    corridor_width: 0,
    waypoints,
    takeoff_gates: [],
    landing_gates: [],
    prohibited_set: [],
    photo_set: [],
  };
}

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
    selectedContestantId: number | null,
    options: { labelAllVisible?: boolean } = {}
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
function renderPrecisionRoute(
  map: L.Map,
  route: RouteData,
  navTaskDisplaySecrets: boolean,
  displaySecrets: boolean,
  taskCatalogueTargets: NavigationTaskCatalogueTarget[] = [],
): L.Layer[] {
  const layers: L.Layer[] = [];

  route.waypoints.filter((waypoint: Waypoint) => {
    return waypoint.type === 'sp' && waypoint.gate_line_extended
  }).forEach((gate: Waypoint) => {
    layers.push(L.polyline(gate.gate_line_extended!, {
        color: "blue",
        dashArray: "4 8"
    }).addTo(map));
  });

  const canSeeSecrets = navTaskDisplaySecrets && displaySecrets;
  const isUnknownLegs = taskCatalogueTargets.some((target) => Boolean(target.segment_name)) || route.waypoints.some((waypoint: Waypoint) => waypoint.type === 'ul');
  const hiddenStretchNames = getUnknownLegHiddenStretchNames(route);
  const routeTypeByName = new Map(route.waypoints.map((waypoint: Waypoint) => [waypoint.name, waypoint.type]));

  if (isUnknownLegs) {
    const hiddenGateNames = new Set(
      taskCatalogueTargets
        .filter((target) => target.kind === 'hidden_gate')
        .map((target) => target.name)
    );
    if (canSeeSecrets) {
      const actualTrack: L.LatLngExpression[] = route.waypoints
        .filter((waypoint: Waypoint) => waypoint.type !== 'dummy')
        .map((waypoint: Waypoint) => [waypoint.latitude, waypoint.longitude] as L.LatLngExpression);
      if (actualTrack.length >= 2) {
        layers.push(L.polyline(actualTrack, { color: "blue" }).addTo(map));
      }

      const triggersById = new Map<string, [number, number]>();
      const connectorEndsByTriggerId = new Map<string, [number, number]>();
      const branchTargetsByTriggerId = new Map<string, NavigationTaskCatalogueTarget[]>();

      taskCatalogueTargets.forEach((target) => {
        const [lng, lat] = target.coordinates;
        if (target.kind === 'unknown_leg_trigger' && target.trigger_point_id) {
          triggersById.set(target.trigger_point_id, [lat, lng]);
        }
        if (target.kind === 'unknown_leg_connector_end' && target.trigger_point_id) {
          connectorEndsByTriggerId.set(target.trigger_point_id, [lat, lng]);
        }
        if (target.kind === 'catalogue_turnpoint' && target.trigger_point_id) {
          const existing = branchTargetsByTriggerId.get(target.trigger_point_id) || [];
          existing.push(target);
          branchTargetsByTriggerId.set(target.trigger_point_id, existing);
        }
      });

      branchTargetsByTriggerId.forEach((branchTargets, triggerId) => {
        const triggerPoint = triggersById.get(triggerId);
        if (!triggerPoint) return;
        const orderedBranchTargets = [...branchTargets].sort((a, b) => (a.branch_sequence ?? 0) - (b.branch_sequence ?? 0));
        const branchTrack: L.LatLngExpression[] = [triggerPoint];
        orderedBranchTargets.forEach((target) => {
          const [lng, lat] = target.coordinates;
          branchTrack.push([lat, lng] as L.LatLngExpression);
        });
        if (branchTrack.length >= 2) {
          layers.push(L.polyline(branchTrack, { color: "blue" }).addTo(map));
        }
      });
    } else {
      const segments = new Map<string, NavigationTaskCatalogueTarget[]>();
      taskCatalogueTargets
        .filter((target) => target.kind === 'catalogue_turnpoint' && target.segment_name)
        .filter((target) => !hiddenGateNames.has(target.name))
        .filter((target) => !hiddenStretchNames.has(target.name))
        .forEach((target) => {
          const key = target.segment_name as string;
          const existing = segments.get(key) || [];
          existing.push(target);
          segments.set(key, existing);
        });
      segments.forEach((segmentTargets) => {
        const visibleSegmentTargets = segmentTargets.filter((target) => routeTypeByName.get(target.name) !== 'secret');
        const track: L.LatLngExpression[] = visibleSegmentTargets.map((target) => {
          const [lng, lat] = target.coordinates;
          return [lat, lng] as L.LatLngExpression;
        });
        if (track.length >= 2) {
          layers.push(L.polyline(track, { color: "blue" }).addTo(map));
        }
      });
    }
    return layers;
  }

  const filterWaypoints = () => route.waypoints.filter((waypoint: Waypoint) => {
    return ((waypoint.gate_check || waypoint.time_check) && (canSeeSecrets || waypoint.type !== "secret") && waypoint.type!=="dummy")
  });

  filterWaypoints().forEach((gate: Waypoint) => {
    layers.push(L.polyline(gate.gate_line, {
        color: "blue"
    }).addTo(map));
  });

  const path: L.LatLngExpression[] = route.waypoints
    .filter((waypoint: Waypoint) => waypoint.type !== 'dummy')
    .map((waypoint: Waypoint) => [waypoint.latitude, waypoint.longitude] as L.LatLngExpression);

  if (path.length >= 2) {
    layers.push(L.polyline(path, {
        color: "blue"
    }).addTo(map));
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


function renderCatalogueTargets(map: L.Map, targets: NavigationTaskCatalogueTarget[], showUnknownLegOverlays: boolean, options: { labelCatalogueTurnpoints?: boolean } = {}): L.Layer[] {
  const layers: L.Layer[] = [];
  const hiddenGateNames = new Set(
    targets
      .filter((target) => (target.kind || 'catalogue_turnpoint') === 'hidden_gate')
      .map((target) => target.name)
  );
  const markerStyleByKind: Record<string, { radius: number; color: string; fillColor: string; fillOpacity: number; shape?: 'circle' | 'square' | 'diamond'; html?: string; className?: string }> = {
    catalogue_turnpoint: { radius: 8, color: 'blue', fillColor: 'white', fillOpacity: 0 },
    circle_center_marker: { radius: 7, color: '#7c3aed', fillColor: '#7c3aed', fillOpacity: 0.2 },
    circle_start_marker: { radius: 8, color: '#16a34a', fillColor: 'white', fillOpacity: 0 },
    circle_entry_marker: { radius: 8, color: '#ea580c', fillColor: '#ea580c', fillOpacity: 0.15, html: '▶', className: 'text-xs font-bold text-orange-600' },
    circle_exit_marker: { radius: 8, color: '#dc2626', fillColor: 'white', fillOpacity: 0, shape: 'square' },
    unknown_leg_trigger: { radius: 8, color: '#6b7280', fillColor: '#6b7280', fillOpacity: 0.2, shape: 'diamond' },
    unknown_leg_connector_end: { radius: 7, color: '#9ca3af', fillColor: '#9ca3af', fillOpacity: 0.15 },
    hidden_gate: { radius: 7, color: '#7c3aed', fillColor: '#7c3aed', fillOpacity: 0.18, shape: 'square' },
  };

  targets.forEach((target) => {
    const kind = target.kind || 'catalogue_turnpoint';
    if (!showUnknownLegOverlays && (kind === 'unknown_leg_trigger' || kind === 'unknown_leg_connector_end' || kind === 'hidden_gate')) {
      return;
    }
    if (kind === 'unknown_leg_connector_end') {
      return;
    }
    if (kind === 'catalogue_turnpoint' && (((target as any).is_unknown_leg_trigger) || hiddenGateNames.has(target.name))) {
      return;
    }

    const [lng, lat] = target.coordinates;
    const style = markerStyleByKind[kind] || markerStyleByKind.catalogue_turnpoint;
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
    } else if (style.shape === 'diamond') {
      const marker = L.polygon(
        [
          [lat - 0.00042, lng],
          [lat, lng + 0.00042],
          [lat + 0.00042, lng],
          [lat, lng - 0.00042],
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

    if (kind !== 'catalogue_turnpoint' || options.labelCatalogueTurnpoints) {
      (layer as any).bindTooltip(target.name, {
        permanent: true,
        direction: 'right',
        offset: [8, 0],
        className: 'waypoint-label'
      });
    }
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

function getRenderedRoute(
  route: RouteData,
  taskCatalogueTargets: NavigationTaskCatalogueTarget[],
  contestants: Record<number, Contestant>,
  selectedContestantId: number | null,
  navTaskDisplaySecrets: boolean,
  displaySecrets: boolean,
): RouteData {
  const isUnknownLegsTask = taskCatalogueTargets.some((target) => Boolean(target.segment_name)) || route.waypoints.some((waypoint: Waypoint) => waypoint.type === 'ul');
  const canSeeSecrets = navTaskDisplaySecrets && displaySecrets;
  const hiddenStretchNames = getUnknownLegHiddenStretchNames(route);

  if (isUnknownLegsTask && !canSeeSecrets) {
    const visibleRoute = buildUnknownLegRouteDataFromTargets(taskCatalogueTargets, hiddenStretchNames);
    if (visibleRoute) {
      return visibleRoute;
    }
  }

  if (selectedContestantId === null) {
    return route;
  }

  const contestant = contestants[selectedContestantId];
  const payload = contestant?.compiled_effective_route_payload || {};
  const actualRoute = payload.actual_route;
  const actualWaypoints = Array.isArray(actualRoute?.waypoints) ? actualRoute.waypoints : [];
  if (actualWaypoints.length > 0) {
    return {
      ...route,
      waypoints: actualWaypoints as Waypoint[],
    };
  }

  const effectiveWaypoints = payload.effective_waypoints;
  if (!Array.isArray(effectiveWaypoints) || effectiveWaypoints.length === 0) {
    return route;
  }

  return {
    ...route,
    waypoints: effectiveWaypoints as Waypoint[],
  };
}

function getRenderedCatalogueTargets(
  taskCatalogueTargets: NavigationTaskCatalogueTarget[],
  route: RouteData,
  contestants: Record<number, Contestant>,
  selectedContestantId: number | null,
  navTaskDisplaySecrets: boolean,
  displaySecrets: boolean,
): NavigationTaskCatalogueTarget[] {
  const canSeeSecrets = navTaskDisplaySecrets && displaySecrets;
  const isUnknownLegsTask = taskCatalogueTargets.some((target) => Boolean(target.segment_name));
  const routeTypeByName = new Map(route.waypoints.map((waypoint: Waypoint) => [waypoint.name, waypoint.type]));
  if (selectedContestantId === null) {
    if (isUnknownLegsTask) {
      return taskCatalogueTargets;
    }
    return taskCatalogueTargets;
  }

  const contestant = contestants[selectedContestantId];
  const payload = contestant?.compiled_effective_route_payload || {};
  const effectiveWaypoints = Array.isArray(payload.effective_waypoints) ? payload.effective_waypoints : [];
  const actualRoute = payload.actual_route;
  const actualRouteWaypoints = Array.isArray(actualRoute?.waypoints) ? actualRoute.waypoints : [];
  const isUnknownLegsSplit = payload.map_rendering_mode === 'unknown_legs_split';

  if (isUnknownLegsSplit) {
    return taskCatalogueTargets;
  }

  const shape = actualRouteWaypoints.length > 0
    ? payload.map_rendering_mode === 'unknown_legs_split'
      ? payload.segments
      : null
    : null;

  if (actualRouteWaypoints.length > 0 && shape) {
    return taskCatalogueTargets;
  }

  if (actualRouteWaypoints.length > 0 && Array.isArray(taskCatalogueTargets) && taskCatalogueTargets.length > 0) {
    return taskCatalogueTargets;
  }

  // Selected-contestant mode should prefer the contestant's declaration-backed
  // effective route geometry over the generic task-level catalogue overlay.
  // This keeps 2.A3 / 2.A6 / 2.B2 live-map rendering aligned with the
  // declaration-backed route instead of showing the full authored catalogue.
  if (effectiveWaypoints.length > 0) {
    return [];
  }

  return taskCatalogueTargets;
}

export default function RouteRenderer({ map, route, taskCatalogueTargets, taskConfig, taskType, navTaskDisplaySecrets, displaySecrets, contestants, selectedContestantId, isInitialLoad, onMapFit }: Props) {
  const layersRef = useRef<L.Layer[]>([]);

  useEffect(() => {
    if (!map || !route || !taskType) return;

    const canSeeSecrets = navTaskDisplaySecrets && displaySecrets;

    const renderedRoute = getRenderedRoute(
      route,
      taskCatalogueTargets || [],
      contestants,
      selectedContestantId,
      navTaskDisplaySecrets,
      displaySecrets,
    );
    const renderedCatalogueTargets = getRenderedCatalogueTargets(
      taskCatalogueTargets || [],
      renderedRoute,
      contestants,
      selectedContestantId,
      navTaskDisplaySecrets,
      displaySecrets,
    );

    // Clear previous layers
    layersRef.current.forEach(layer => layer.remove());
    layersRef.current = [];

    let layers: L.Layer[] = [];
    const routeGeometryTargets = taskCatalogueTargets || [];

    if (taskType.includes("poker")) {
        layers = layers.concat(renderPokerRoute(map, renderedRoute));
    } else if (taskType.includes("precision")) {
      layers = layers.concat(renderPrecisionRoute(map, renderedRoute, navTaskDisplaySecrets, displaySecrets, routeGeometryTargets));
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
    if (renderedCatalogueTargets.length > 0) {
      const showUnknownLegOverlays = canSeeSecrets;
      const isUnknownLegsTask = (taskCatalogueTargets || []).some((target) => Boolean(target.segment_name));
      layers = layers.concat(renderCatalogueTargets(map, renderedCatalogueTargets, showUnknownLegOverlays, {
        labelCatalogueTurnpoints: isUnknownLegsTask,
      }));
      const circleTargets = renderedCatalogueTargets.filter((target) => target.kind?.startsWith('circle_'));
      if (circleTargets.length > 0) {
        layers = layers.concat(renderCircleTaskGeometry(map, circleTargets, taskConfig));
      }
    }
    
    const waypointsToLabel = renderedRoute.waypoints.filter((w: Waypoint) => {
        const isUnknownLegsTask = (taskCatalogueTargets || []).some((target) => Boolean(target.segment_name));
        const isUnknownLeg = w.type === "ul";
        const isHiddenUnknownLegSecret = w.type === 'hidden_gate' || w.type === 'secret';
        if (isUnknownLegsTask) {
            return false;
        }
        const canSeeSecrets = navTaskDisplaySecrets && displaySecrets;
        const showUnknownLegOverlays = canSeeSecrets;
        if (isUnknownLegsTask && (isUnknownLeg || isHiddenUnknownLegSecret)) {
            return false;
        }
        return (w.gate_check || w.time_check) && ((canSeeSecrets && (showUnknownLegOverlays || !isUnknownLeg)) || (w.type !== "secret" && !isUnknownLeg)) && w.type !== "dummy";
    });
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
