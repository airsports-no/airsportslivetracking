import type { NavigationTaskCatalogueTarget, RouteData, Waypoint, Contestant } from '../../types';

// Pure route/catalogue-target selection logic extracted out of
// RouteRenderer.tsx so it can be unit-tested without pulling in Leaflet or
// React (see routeSelection.test.ts alongside this file). This is the
// decision logic behind "does the live map show the generic task route or
// the selected contestant's declared route" - keep it framework-free.

export function getUnknownLegHiddenStretchNames(route: RouteData): Set<string> {
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

    if (waypoint.type === 'secret') {
      hiddenStretchNames.add(waypoint.name);
      return;
    }

    if (['tp', 'fp', 'isp', 'ifp', 'sp'].includes(waypoint.type)) {
      onUnknownLegHiddenStretch = false;
    }
  });

  return hiddenStretchNames;
}

export function buildUnknownLegRouteDataFromTargets(targets: NavigationTaskCatalogueTarget[], hiddenStretchNames: Set<string> = new Set()): RouteData | null {
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

// contestanttaskconfiguration.compiled_effective_route_payload's actual_route.waypoints
// (task_compiler.py's _build_unknown_legs_compiled_payload) are raw {name, type, coordinates}
// entries - coordinates in [lng, lat] order, like every other catalogue-target geometry in this
// payload - not full Waypoint objects. Casting them straight through left every waypoint.latitude/
// longitude undefined, which fed Leaflet a polyline of undefined points and crashed
// _projectLatlngs on first render (see routeSelection.test.ts for the regression case).
function waypointFromActualRouteEntry(entry: { name: string; type: string; coordinates: [number, number] }): Waypoint {
  const [longitude, latitude] = entry.coordinates;
  return {
    name: entry.name,
    type: entry.type,
    latitude,
    longitude,
    elevation: 0,
    width: 0,
    gate_line: [],
    time_check: false,
    gate_check: false,
    end_curved: false,
    distance_next: 0,
    distance_previous: 0,
    bearing_next: 0,
    bearing_from_previous: 0,
    is_procedure_turn: false,
  };
}

export function getRenderedRoute(
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
      waypoints: actualWaypoints.map(waypointFromActualRouteEntry),
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

export function getRenderedCatalogueTargets(
  taskCatalogueTargets: NavigationTaskCatalogueTarget[],
  route: RouteData,
  contestants: Record<number, Contestant>,
  selectedContestantId: number | null,
  navTaskDisplaySecrets: boolean,
  displaySecrets: boolean,
  taskSubtype: string | null = null,
): NavigationTaskCatalogueTarget[] {
  if (selectedContestantId === null) {
    // 2.A3's general map shows only the three backbone waypoints: no freeway
    // (catalogue) points until a contestant's declared route is selected.
    if (taskSubtype === 'contract_navigation_time_controls') {
      return [];
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
